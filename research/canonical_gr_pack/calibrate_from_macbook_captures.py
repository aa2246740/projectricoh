#!/usr/bin/env python3
"""Measure four original GXR RAW+JPEG chart pairs, offline and without camera I/O.

python3 -I -B research/canonical_gr_pack/calibrate_from_macbook_captures.py \
    --manifest research/canonical_gr_pack/capture_manifest.json

Alternatively --captures /absolute/local/folder finds T1.DNG/T1.JPG .. T4.
Updates research JSON only. It never creates firmware, writes a card or changes
native source tables. Four shots measure one GXR setting, not 15 control axes,
an unknown GR sensor, a GRD IV renderer, grain or sharpness.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, ROOT, PIPE, safe_path, output_path, load, save, sha, module, record
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.cluster.vq import kmeans2
from scipy.interpolate import PchipInterpolator

tiff = module('capture_tiff', PIPE / 'reference_tiff_frozen.py')
colour = module('capture_colour', PIPE / 'colour_math_frozen.py')
pmath = module('capture_pipeline', PIPE / 'pipeline_math.py')


def homography(src, dst):
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    if src.shape != dst.shape or src.shape[1] != 2 or len(src) < 4:
        raise ValueError('Four or more corresponding 2D points required')
    rows, rhs = [], []
    for (x, y), (u, v) in zip(src, dst):
        rows += [[x,y,1,0,0,0,-u*x,-u*y], [0,0,0,x,y,1,-v*x,-v*y]]
        rhs += [u,v]
    solution = np.linalg.lstsq(rows, rhs, rcond=None)[0]
    h = np.r_[solution, 1.].reshape(3, 3)
    if not np.all(np.isfinite(h)) or abs(np.linalg.det(h)) < 1e-9:
        raise ValueError('Degenerate chart geometry')
    return h


def transform(h, points):
    a = np.c_[np.asarray(points, float), np.ones(len(points))] @ h.T
    if np.any(np.abs(a[:,2]) < 1e-8):
        raise ValueError('Homography crosses infinity')
    return a[:,:2] / a[:,2:]


def auto_grid(rgb, previous_grid=None):
    """Locate a near-frontal 8x6 chart from uniform patch interiors.

    Alignment uses edges and regular geometry, never nominal patch colour as a
    sensor calibration target. Strong perspective or clutter fails explicitly;
    a manifest can supply the photographed grid's TL,TR,BR,BL outer corners.
    """
    height, width = rgb.shape[:2]
    scale = min(1., 1200 / max(height, width))
    small = np.asarray(Image.fromarray(rgb).resize((round(width*scale), round(height*scale))), float) / 255
    gx = np.max(np.abs(np.diff(small, axis=1)), axis=2)
    gy = np.max(np.abs(np.diff(small, axis=0)), axis=2)
    edge = np.zeros(small.shape[:2], bool)
    edge[:,:-1] |= gx > .025
    edge[:-1,:] |= gy > .025
    edge = ndimage.binary_dilation(edge, iterations=2)
    labels, _ = ndimage.label(~edge)
    components = []
    for label_id, slices in enumerate(ndimage.find_objects(labels), 1):
        if slices is None:
            continue
        ys, xs = slices
        bh, bw = ys.stop-ys.start, xs.stop-xs.start
        area = int(np.sum(labels[slices] == label_id))
        if (bw < small.shape[1]*.035 or bh < small.shape[0]*.04 or
            bw > small.shape[1]*.22 or bh > small.shape[0]*.28 or
            area < bw*bh*.72):
            continue
        components.append(((xs.start+xs.stop)/2, (ys.start+ys.stop)/2, area))
    if len(components) < 40:
        raise ValueError(f'Auto registration found {len(components)} patch interiors, need >=40; supply grid_corners_xy in manifest')
    a = np.asarray(components)
    median_area = np.median(a[:,2])
    a = a[(a[:,2] > median_area*.4) & (a[:,2] < median_area*2.5)]
    if len(a) < 40:
        raise ValueError('Ambiguous patch sizes; supply grid_corners_xy')
    cols, _ = kmeans2(a[:,0], np.quantile(a[:,0], np.linspace(0,1,8)), minit='matrix', iter=30)
    rows, _ = kmeans2(a[:,1], np.quantile(a[:,1], np.linspace(0,1,6)), minit='matrix', iter=30)
    cols, rows = np.sort(cols), np.sort(rows)
    ci = np.argmin(abs(a[:,0,None]-cols), axis=1)
    ri = np.argmin(abs(a[:,1,None]-rows), axis=1)
    unique = {(int(r),int(c)) for r,c in zip(ri,ci)}
    if len(unique) < 40:
        raise ValueError('Could not identify an 8x6 grid; supply grid_corners_xy')
    centers = np.c_[ci+.5,ri+.5]
    h = homography(centers, a[:,:2]/scale)
    residual = np.linalg.norm(transform(h, centers)-a[:,:2]/scale, axis=1)
    pitch = min(np.median(np.diff(cols)), np.median(np.diff(rows))) / scale
    registration_method = 'uniform-interior components and 8x6 homography'
    if np.percentile(residual,90) > pitch*.10 and previous_grid is not None:
        # Adjacent pages share the same tripod/screen geometry. A missing row
        # or column of detectable uniform interiors must not shift k-means IDs.
        normalized = transform(np.linalg.inv(previous_grid),a[:,:2]/scale)
        ids = np.rint(normalized-.5).astype(int)
        use = (ids[:,0]>=0)&(ids[:,0]<8)&(ids[:,1]>=0)&(ids[:,1]<6)
        trial_centers = ids[use]+.5
        trial_unique = {tuple(v) for v in ids[use]}
        if len(trial_unique)>=40:
            trial = homography(trial_centers,a[use,:2]/scale)
            trial_residual = np.linalg.norm(transform(trial,trial_centers)-a[use,:2]/scale,axis=1)
            if np.percentile(trial_residual,90) < np.percentile(residual,90):
                h,residual = trial,trial_residual
                unique = trial_unique
                registration_method = 'uniform-interior components, previous-page cell IDs and independently refitted homography'
    if np.percentile(residual,90) > pitch*.10:
        raise ValueError('Registration residual exceeds 10% of patch pitch; supply grid_corners_xy')
    corners = transform(h, [[0,0],[8,0],[8,6],[0,6]])
    return h, {'method':registration_method,
               'components':len(a), 'grid_cells_identified':len(unique),
               'p90_center_residual_px':float(np.percentile(residual,90)),
               'grid_corners_xy':corners.tolist(),'homography':h.tolist()}


def polygon_pixels(quad, width, height):
    q = np.asarray(quad, float)
    if q.shape != (4,2) or not np.all(np.isfinite(q)):
        raise ValueError('Four finite polygon corners required')
    if np.any(q[:,0] < 0) or np.any(q[:,1] < 0) or np.any(q[:,0] >= width) or np.any(q[:,1] >= height):
        raise ValueError('Chart ROI lies outside the image')
    x0,y0 = np.floor(q.min(axis=0)).astype(int)
    x1,y1 = np.ceil(q.max(axis=0)).astype(int)
    if x1-x0 < 12 or y1-y0 < 12:
        raise ValueError('Patch ROI is too small, minimum 12x12 pixels')
    xx,yy = np.meshgrid(np.arange(x0,x1),np.arange(y0,y1))
    p = np.stack([xx+.5,yy+.5], axis=-1)
    v = np.roll(q,-1,axis=0)-q
    rel = p[...,None,:]-q
    cross = v[:,0]*rel[...,1]-v[:,1]*rel[...,0]
    mask = np.all(cross >= -1e-8,axis=-1) | np.all(cross <= 1e-8,axis=-1)
    if mask.sum() < 144:
        raise ValueError('Patch support contains too few pixels')
    return x0,y0,x1,y1,mask


def validate_dng(t):
    d = tiff.raw_ifd(t)
    v = lambda k: d[k]['value']
    width,height = v(256)[0],v(257)[0]
    if width*height > 50_000_000 or min(width,height) < 96:
        raise ValueError('Unsupported RAW dimensions')
    if v(259) != [1] or v(258) != [12] or d.get(277,{}).get('value',[1]) != [1]:
        raise ValueError('This GXR path supports only single-sample, uncompressed 12-bit Bayer DNG')
    if d.get(33421,{}).get('value') != [2,2] or sorted(d[33422]['raw']) != [0,1,1,2]:
        raise ValueError('Unsupported CFA pattern')
    if sum(v(279)) != width*height*3//2 or any(o+n > len(t.data) for o,n in zip(v(273),v(279))):
        raise ValueError('RAW strip boundaries/length invalid')
    return d


def extract_pair(pair, page, outdir, previous_grid=None):
    dp,jp = safe_path(pair['dng']),safe_path(pair['jpeg'])
    for p in [dp,jp]:
        if p.stat().st_size > 300_000_000:
            raise ValueError('Capture exceeds bounded file size')
    t = tiff.Tiff(dp.read_bytes())
    d = validate_dng(t)
    raw,d = tiff.unpack_raw(t)
    root = t.ifd(t.root)
    if root.get(274,{}).get('value',[1]) != [1]:
        raise ValueError('Capture must have Orientation=1; do not rotate only the JPEG')
    opened = Image.open(jp)
    if opened.getexif().get(274,1) != 1:
        raise ValueError('JPEG orientation differs from RAW coordinate convention')
    rgb = np.asarray(opened.convert('RGB'))
    ox,oy,cw,ch = tiff.crop_info(d)
    if rgb.shape[:2] != (ch,cw) or min(ox,oy) < 0 or oy+ch > raw.shape[0] or ox+cw > raw.shape[1]:
        raise ValueError('JPEG dimensions must equal the original DNG DefaultCrop')
    if 'grid_corners_xy' in pair:
        h = homography([[0,0],[8,0],[8,6],[0,6]],pair['grid_corners_xy'])
        registration = {'method':'explicit photographed-grid corners, not nominal browser pixels',
                        'grid_corners_xy':pair['grid_corners_xy']}
    else:
        h,registration = auto_grid(rgb,previous_grid)
    black = np.asarray(d.get(50714,{}).get('value',[0]), float)
    white = float(d[50717]['value'][0])
    if black.size not in [1,4] or white <= np.max(black):
        raise ValueError('Unsupported black/white levels')
    if 50715 in d or 50716 in d:
        raise ValueError('BlackLevelDeltaH/V requires a separate raw normalization implementation')
    pattern = np.frombuffer(d[33422]['raw'],np.uint8).reshape(2,2)
    results = []
    preview = Image.fromarray(rgb)
    draw = ImageDraw.Draw(preview)
    for patch in page['patches']:
        r,c = patch['row'],patch['col']
        quad = transform(h,[[c+.3,r+.3],[c+.7,r+.3],[c+.7,r+.7],[c+.3,r+.7]])
        x0,y0,x1,y1,mask = polygon_pixels(quad,cw,ch)
        pixels = rgb[y0:y1,x0:x1][mask].astype(float)/255
        ry,rx = np.nonzero(mask)
        ry,rx = ry+y0+oy,rx+x0+ox
        channel = pattern[ry%2,rx%2]
        samples = raw[ry,rx].astype(float)
        # BlackLevelRepeatDim=2x2 uses absolute stored CFA phase.
        b = np.full(len(samples),black[0]) if black.size == 1 else black.reshape(2,2)[ry%2,rx%2]
        normalized = (samples-b)/(white-b)
        camera = np.array([normalized[channel==k].mean() for k in range(3)])
        counts = [int(np.sum(channel==k)) for k in range(3)]
        if min(counts) < 32:
            raise ValueError('Insufficient CFA samples in ROI')
        reasons = []
        clip_fraction = float(np.mean((normalized >= .995) | (normalized < -.01)))
        if clip_fraction > .01: reasons.append('raw_clipping')
        if camera.max() < .002: reasons.append('below_noise_floor')
        # A high standard deviation indicates reflections, patch overlap or bands.
        if np.max(pixels.std(axis=0)) > .08: reasons.append('nonuniform_or_bad_registration')
        encoded = pixels.mean(axis=0)
        linear = colour.srgb_decode(pixels).mean(axis=0)
        item = {'page':page['id'], 'patch_id':patch['id'], 'group':patch['group'],
                'row':r, 'col':c, 'jpeg_quad_xy':quad.tolist(), 'raw_crop_origin_xy':[ox,oy],
                'camera_RGB':camera.tolist(), 'CFA_samples_RGB':counts,
                'jpeg_encoded_mean':encoded.tolist(), 'jpeg_linear_mean':linear.tolist(),
                'jpeg_pixel_std':pixels.std(axis=0).tolist(),
                'raw_clip_fraction':clip_fraction, 'valid':not reasons, 'excluded_reasons':reasons,
                'nominal_display_colour_used_as_sensor_truth':False}
        results.append(item)
        draw.line([tuple(v) for v in np.vstack([quad,quad[0]])],fill='lime' if not reasons else 'red',width=3)
        draw.text(tuple(quad[0]),patch['id'],fill='white',stroke_width=1,stroke_fill='black')
    if sum(p['valid'] for p in results) < 46:
        raise ValueError(f"{page['id']}: fewer than 46/48 usable patches; JSON pack will not be updated")
    preview.thumbnail((1400,1000))
    preview.save(output_path(outdir/(page['id']+'-ROIs.jpg')),quality=90)
    metadata = tiff.exif_summary(t)
    try:
        jm = tiff.exif_summary(tiff.jpeg_exif(jp.read_bytes()))
    except ValueError:
        jm = None
    if jm:
        for key in ['iso','exposure','f_number','datetime']:
            if metadata.get(key) is not None and jm.get(key) is not None and metadata[key] != jm[key]:
                raise ValueError(f'RAW/JPEG exposure mismatch: {key}')
    return results, {'page':page['id'], 'dng_sha256':sha(dp.read_bytes()), 'jpeg_sha256':sha(jp.read_bytes()),
                     'registration':registration, 'metadata':metadata, 'jpeg_metadata':jm,
                     'tags':t.tags(), 'valid_count':sum(p['valid'] for p in results)}


def matrix_at(tags, temperature):
    temps = {17:2856.,21:6504.,23:5003.,20:5503.}
    t1,t2 = temps[tags.get(50778,[17])[0]],temps[tags.get(50779,[21])[0]]
    alpha = np.clip((1/temperature-1/t1)/(1/t2-1/t1),0,1) if t1 != t2 else 0.
    cm1 = np.asarray(tags[50721],float).reshape(3,3)
    cm2 = np.asarray(tags.get(50722,tags[50721]),float).reshape(3,3)
    valid_cal = tags.get(50931,'') == tags.get(50932,'')
    cc1 = np.asarray(tags.get(50723,np.eye(3).ravel()) if valid_cal else np.eye(3),float).reshape(3,3)
    cc2 = np.asarray(tags.get(50724,np.eye(3).ravel()) if valid_cal else np.eye(3),float).reshape(3,3)
    return np.diag(tags.get(50727,[1,1,1])) @ ((1-alpha)*cc1+alpha*cc2) @ ((1-alpha)*cm1+alpha*cm2)


def isotonic(y, weights=None):
    weights = np.ones(len(y)) if weights is None else np.asarray(weights,float)
    blocks = []
    for i,(value,weight) in enumerate(zip(y,weights)):
        blocks.append([i,i+1,float(value)*weight,float(weight)])
        while len(blocks)>1 and blocks[-2][2]/blocks[-2][3] > blocks[-1][2]/blocks[-1][3]:
            b = blocks.pop(); a = blocks.pop()
            blocks.append([a[0],b[1],a[2]+b[2],a[3]+b[3]])
    result = np.empty(len(y))
    for start,end,total,weight in blocks:
        result[start:end] = total/weight
    return result


def monotone_fit(x,y):
    x,y = np.asarray(x,float),np.asarray(y,float)
    order = np.argsort(x,kind='stable');x,y = x[order],y[order]
    ux,inv = np.unique(x,return_inverse=True)
    counts = np.bincount(inv)
    means = np.bincount(inv,weights=y)/counts
    if len(ux) < 10 or ux[-1]-ux[0] < .2:
        raise ValueError('Insufficient neutral ramp dynamic range')
    uy = isotonic(means,counts)
    interior = (ux > 0) & (ux < 1)
    xx = np.r_[0.,ux[interior],1.]
    yy = isotonic(np.r_[0.,np.clip(uy[interior],0,1),1.])
    return PchipInterpolator(xx,yy), [float(ux[0]),float(ux[-1])]


def de_summary(pred,target):
    d = colour.delta_e00(colour.rgb_lab(np.clip(pred,0,1)),colour.rgb_lab(np.clip(target,0,1)))
    return {'count':len(d), 'median':float(np.median(d)), 'p90':float(np.percentile(d,90)), 'maximum':float(np.max(d))}


def fit_models(patches, captures, deep, allow_wb_drift=False):
    tags = captures[0]['tags']
    quality_flags=[]
    neutrals=np.array([c['tags'][50728] for c in captures],float)
    wb_relative_drift=float(np.max(np.abs(neutrals/neutrals[0]-1)))
    if wb_relative_drift>1e-5:
        if not allow_wb_drift:
            raise ValueError('DNG WB changed across pages; use --allow-wb-drift-diagnostic to retain a flagged exploratory fit')
        quality_flags.append('WB_DRIFT: final AsShotNeutral differs across pages; pooled JPEG correction is exploratory only')
    for other in captures[1:]:
        for k in [50721,50722,50727]:
            if k in tags and not np.allclose(tags[k],other['tags'].get(k,[]),atol=1e-6,rtol=1e-5):
                raise ValueError('DNG colour matrices or WB changed between the four shots')
    A,desc = colour.dng_camera_to_xyz(tags)
    white = np.asarray(desc['scene_white_xyz_y1'])
    temperature = float(desc['cct_K_approx'])
    grtags = {int(k):v for k,v in deep['reference_DNG']['tags'].items()}
    mg,mr = matrix_at(tags,temperature),matrix_at(grtags,temperature)
    bridge = mr @ np.linalg.inv(mg)
    nr,ng = mr@white,mg@white
    exposure = ng[1]/nr[1]
    gr_wb = nr[1]/nr
    camera = np.array([p['camera_RGB'] for p in patches])
    jpeg = np.array([p['jpeg_encoded_mean'] for p in patches])
    mapped = (camera@bridge.T)*exposure*gr_wb
    valid = np.array([p['valid'] for p in patches])
    train = valid & np.array([p['page'] != 'T4' for p in patches])
    hold = valid & ~train
    neutral = train & np.array([p['group']=='neutral' for p in patches])
    if neutral.sum() < 20 or train.sum()<120 or hold.sum()<46:
        raise ValueError('Insufficient neutral/training/held-out support')
    colors = load(PIPE/'arm_color_math_verification.json')['models']['gr3']
    variants = deep['modern_reference_variants']
    models = {}
    luma = np.array([77,150,29])/256
    for key,mode in [('positive','PositiveFilm'),('negative','NegativeFilm'),('standard','Standard')]:
        v = variants[mode]
        native_name = {'positive':'Positive Film','negative':'Negative Film','standard':'Standard'}[key]
        front = np.asarray(colors[native_name]['front'],float)/256
        signal = np.clip(mapped@front.T,0,1)
        source = np.asarray(v['curve256_u16LE']['values'])/16384
        target = np.stack([np.interp(signal[:,k]*4095,np.arange(256)*16,source) for k in range(3)],axis=1)
        # Fit an encoded-output correction. This is an explicit placement
        # hypothesis, never silently installed as the native pre-tone curve.
        curve,domain = monotone_fit(jpeg[neutral]@luma,target[neutral]@luma)
        base = curve(np.clip(jpeg,0,1))
        design = np.c_[base[:,0]-base[:,2],base[:,1]-base[:,2]]
        coeff = np.linalg.solve(design[train].T@design[train]+np.eye(2)*.02,
                                design[train].T@(target[train]-base[train,2,None]))
        matrix = np.stack([coeff[0],coeff[1],1-coeff[0]-coeff[1]],axis=1)
        pred = np.clip(base@matrix.T,0,1)
        try:
            matrix_option = pmath.project_matrix(matrix)
            chroma_option = pmath.project_chroma_similarity(matrix)
        except ValueError as error:
            matrix_option = chroma_option = None
            quantization_error = str(error)
        else:
            quantization_error = None
        encoded256 = np.rint(np.clip(curve(np.arange(256)*16/4095),0,1)*16384).astype(int)
        models[key] = {'source_native_variant':mode, 'source_gain':v['runtime_gain'],
            'reference_status':'PARTIAL_NATIVE_GRIII_MODEL, NOT_ACCEPTED_FULL_RENDERER',
            'target_equation':'GammaTuning(clamp(front_Q8/256 * WB_common * E_tags * B_DNG * raw))',
            'omitted_target_stages':['MultiAxial pixel math','local tone','spatial processing'],
            'correction_domain':'CURRENT_ENCODED_GXR_JPEG_OUTPUT; actual ISP placement is unproven',
            'correction_curve256_u16LE':record(encoded256,'H','<'),
            'type26_refined_output_correction_candidate':pmath.project_curve(encoded256.tolist(),8),
            'supported_encoded_luma_range':domain,
            'extrapolation':'Endpoint-constrained monotone prior outside measured range; not measured support',
            'post_correction_matrix_float':matrix.tolist(),
            'type28_full_matrix_alternative':matrix_option,
            'type28_chroma_only_alternative':chroma_option,
            'color_options_mutually_exclusive':True,'quantization_failure':quantization_error,
            'train_metrics_to_partial_model':de_summary(pred[train],target[train]),
            'T4_heldout_metrics_to_partial_model':de_summary(pred[hold],target[hold]),
            'metrics_are_NOT_real_GR_matching_acceptance':True,
            'per_patch_target_RGB':target.tolist(), 'per_patch_predicted_RGB':pred.tolist(),
            'native_tables_replaced':False,'deployable':False}
    return {'method':'Four shots at one fixed base setting; 144 nominal training patches, 48 T4 internal holdout',
            'patch_counts':{'all':len(patches),'valid':int(valid.sum()),'training':int(train.sum()),'T4_holdout':int(hold.sum())},
            'bridge':{'B_gxr_to_gr':bridge.tolist(),'common_white_xyz':white.tolist(),
                'temperature_K_approx':temperature, 'tag_normalization_exposure':float(exposure),
                'GR_WB_for_common_white':gr_wb.tolist(),
                'source':'Native DNG ColorMatrix tags from both cameras, not an Adobe DCP',
                'estimated_from_screen_nominal_colors':False,
                'measured_cross_sensor_mapping':False,
                'identifiability':'GXR-only captures do not identify the true GR sensor mapping; DNG bridge is frozen'},
            'models':models, 'full_GXR_control_response_identified':False,
            'sharpness_grain_and_monochrome_channel_weights_identified':False,
            'GRD_IV_full_color_target_supported':False,
            'quality_flags':quality_flags,
            'per_page_AsShotNeutral':neutrals.tolist(), 'maximum_relative_WB_drift':wb_relative_drift,
            'precision_calibration_accepted':False,
            'on_camera_acceptance':False}


def atomic_pack_update(deep, canonical, outdir, run_id, result):
    summary = {'state':'DIAGNOSTIC_FIT_WITH_WB_DRIFT' if result['quality_flags'] else 'SCREEN_RESPONSE_FIT_TO_PARTIAL_NATIVE_MODEL', 'run_id':run_id,
               'run_report':str((outdir/'calibration.json').relative_to(HERE)),
               'capture_pair_count':4, 'patch_count':192, 'true_sensor_bridge_measured':False,
               'native_tables_preserved':True, 'on_camera_look_validation':False,
               'quality_flags':result['quality_flags'], 'input_kind':load(outdir/'calibration.json')['input_kind']}
    deep['calibration'] = copy.deepcopy(summary)
    deep['calibration']['screen_transfer_models'] = result
    canonical['calibration'] = copy.deepcopy(summary)
    deep['status'] = canonical['status'] = 'SCREEN_DIAGNOSTIC_NATIVE_RESEARCH_CANDIDATE'
    for slot in canonical['slots']:
        key = str(slot['slot']).zfill(2)
        supported = {1:'positive',2:'negative',4:'standard'}.get(slot['slot'])
        info = {'run_id':run_id, 'model':supported,
                'state':'DIAGNOSTIC_CANDIDATE_ONLY' if supported else 'SHARED_BASE_RESPONSE_ONLY',
                'selected_native_variant_calibrated':False,
                'note':'Slot01 positive diagnostics target GRIII variant1A; selected exact GRD IV variant1B remains uncalibrated' if slot['slot']==1 else
                       'No automatic claim of hardware matching or calibration of unobserved controls'}
        deep['slots'][key]['screen_calibration'] = info
        slot['screen_calibration'] = copy.deepcopy(info)
        slot['calibration_status'] = info['state']
    targets = [(HERE/'deep_isp_tables.json',deep),(HERE/'canonical_16_slots.json',canonical)]
    originals = {p:p.read_bytes() for p,_ in targets}
    for p,data in targets:
        save(outdir/(p.stem+'-proposed.json'),data)
    replaced = []
    try:
        for p,data in targets:
            if p.read_bytes() != originals[p]:
                raise ValueError('Concurrent pack modification detected; no overwrite allowed')
            temporary = output_path(HERE/(p.name+'.pending'))
            temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
            temporary.replace(p)
            replaced.append(p)
    except Exception:
        for p in replaced:
            p.write_bytes(originals[p])
        raise
    save(HERE/'calibration_current.json',{'run_id':run_id,
        'deep_sha256':sha((HERE/'deep_isp_tables.json').read_bytes()),
        'canonical_sha256':sha((HERE/'canonical_16_slots.json').read_bytes()),
        'camera_acceptance':False})


def run(manifest, update=True, allow_wb_drift=False):
    if set(p['page'] for p in manifest['pairs']) != {'T1','T2','T3','T4'} or len(manifest['pairs']) != 4:
        raise ValueError('Exactly one original DNG+JPEG pair for each T1,T2,T3,T4 is required')
    snapshot = load(HERE/'source_snapshot.json')
    for item in snapshot['inputs']:
        if sha(safe_path(item['path']).read_bytes()) != item['sha256']:
            raise ValueError('Research dependency drifted; rebuild/review before calibration: '+item['path'])
    captures_identity = []
    for p in sorted(manifest['pairs'],key=lambda p:p['page']):
        captures_identity.append({**p,'dng_sha256':sha(safe_path(p['dng']).read_bytes()),
                                  'jpeg_sha256':sha(safe_path(p['jpeg']).read_bytes())})
    identity = {'captures':captures_identity,'source_snapshot_sha256':sha((HERE/'source_snapshot.json').read_bytes()),
                'script_sha256':sha(Path(__file__).read_bytes()),'setup':manifest.get('setup'),
                'allow_wb_drift_diagnostic':allow_wb_drift}
    run_id = sha(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode())[:20]
    outdir = output_path(HERE/'calibration'/run_id)
    outdir.mkdir(parents=True,exist_ok=True)
    chart = load(ROOT/'research/color_references/screen_chart.json')
    pages = {p['id']:p for p in chart['pages']}
    patches,captures = [],[]
    previous_grid=None
    for pair in sorted(manifest['pairs'],key=lambda p:p['page']):
        data,metadata = extract_pair(pair,pages[pair['page']],outdir,previous_grid)
        patches.extend(data);captures.append(metadata)
        previous_grid=homography([[0,0],[8,0],[8,6],[0,6]],metadata['registration']['grid_corners_xy'])
    save(outdir/'measurements.json',{'run_id':run_id,'input_kind':manifest.get('input_kind'),
         'patches':patches,'captures':[{k:v for k,v in c.items() if k!='tags'} for c in captures],
         'fit_attempted':False,'pack_updated':False})
    setup = manifest.get('setup',{})
    inferred = [c['metadata'].get('display13') for c in captures]
    if any(v is not None and v != [5]*13 for v in inferred):
        raise ValueError('Actual MakerNote controls disagree with the required neutral base')
    if setup.get('base_color_controls') != [5]*13 and inferred != [[5]*13]*4:
        raise ValueError('Requires the neutral Color base with all 13 controls=5; supply/verify setup, not a brand slot')
    for c in captures:
        m = c['metadata']
        if m.get('image_mode') not in [None,4]:
            raise ValueError('Capture metadata is not native color Setting1=04')
        model = m.get('model','')
        if isinstance(model,list):model = ''.join(map(str,model))
        if model and 'GXR' not in model:
            raise ValueError('Only the declared GXR capture path is supported')
    for key in ['iso','exposure','f_number']:
        values = [c['metadata'].get(key) for c in captures]
        if any(v is not None for v in values) and any(v != values[0] for v in values):
            raise ValueError('Fixed exposure changed between T pages: '+key)
    deep,canonical = load(HERE/'deep_isp_tables.json'),load(HERE/'canonical_16_slots.json')
    result = fit_models(patches,captures,deep,allow_wb_drift)
    report = {'schema':'four-shot-native-model-calibration-v1','run_id':run_id,'identity':identity,
              'input_kind':manifest.get('input_kind','USER_CAPTURES_NOT_YET_VISUALLY_ACCEPTED'),
              'patches':patches,'captures':[{k:v for k,v in c.items() if k!='tags'} for c in captures],
              'result':result,'real_GR_pair_validation_passed':False,'deployable':False}
    save(outdir/'calibration.json',report)
    save(outdir/'measurements.json',{'run_id':run_id,'input_kind':manifest.get('input_kind'),
         'patches':patches,'captures':[{k:v for k,v in c.items() if k!='tags'} for c in captures],
         'fit_attempted':True,'fit_report':'calibration.json','quality_flags':result['quality_flags']})
    if update:
        atomic_pack_update(deep,canonical,outdir,run_id,result)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--manifest',type=Path)
    group.add_argument('--captures',type=Path)
    parser.add_argument('--measure-only',action='store_true',help='Extract and fit without updating pack JSON')
    parser.add_argument('--allow-wb-drift-diagnostic',action='store_true',help='Retain a flagged exploratory fit when recorded final WB changes; never claims precision calibration')
    args = parser.parse_args()
    if args.manifest:
        mp = safe_path(args.manifest);manifest = load(mp)
        for p in manifest['pairs']:
            for key in ['dng','jpeg']:
                p[key] = str(safe_path(mp.parent/p[key]))
    else:
        directory = safe_path(args.captures)
        def named(page,extensions):
            options = [directory/(page+e) for e in extensions]
            found = [p for p in options if p.is_file()]
            if len(found)!=1:raise ValueError(f'Need one {page} file with suffix in {extensions}')
            return str(found[0])
        manifest = {'pairs':[{'page':f'T{i}','dng':named(f'T{i}',['.DNG','.dng']),
                    'jpeg':named(f'T{i}',['.JPG','.jpg','.JPEG','.jpeg'])} for i in range(1,5)]}
    try:
        report = run(manifest,not args.measure_only,args.allow_wb_drift_diagnostic)
    except (ValueError,KeyError,OSError,StopIteration) as error:
        parser.exit(2,f'Calibration stopped; native pack was not deliberately replaced: {error}\n')
    print(json.dumps({'run_id':report['run_id'],**report['result']['patch_counts'],
                      'pack_updated':not args.measure_only,'real_GR_look_acceptance':False},ensure_ascii=False))


if __name__ == '__main__':
    main()
