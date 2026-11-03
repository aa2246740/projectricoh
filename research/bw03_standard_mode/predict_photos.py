"""DNG predictions through the existing 04 calibration and UnitModel.

The new entry runs through the generic colour path. The legacy model's
slot-03 shortcut is deliberately not used for the Standard candidate.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
import json
import numpy as np
from PIL import Image, ImageDraw, ImageOps

FRAMES=[1316,1451,*range(1453,1459),*range(1468,1474)]
ANCHORS=[1319,1320,1452]
CAP=r.ROOT/'captures/a12-50/2026-10-24/stage2l-daily-R8051312-1473'
paths=[]
for folder in ('research/module_adapt','research/color_table_fit','research/color_calibration',
               'research/hue_ring','research/stage2d_verification','research/chart_session_20261024'):
    paths.extend(p for p in (r.ROOT/folder).glob('*.py'))
for n in FRAMES+ANCHORS:
    paths.extend(CAP/f'R805{n:04d}.{ext}' for ext in ('JPG','DNG'))
    paths.append(r.ROOT/f'research/daily_bugs_20261024/local/per_frame/R805{n:04d}.json')
for name in ('SHA256SUMS','copy_manifest.json'):
    p=CAP/name
    if p.exists():paths.append(p)
r.freeze.add(paths)

sys.path.insert(0,str(r.ROOT/'research/module_adapt'))
import support as s
s.HERE,s.LOCAL=r.HERE,r.LOCAL
from unit_model import UnitModel
import calibrate
M=UnitModel('50mm',iso=200)
# The colour fitter only accepts its canonical sign/complement encoding.
# Native B&W row 28 instead contains literal zero 2x2 chroma matrices.
# Decode that exact native sentinel as (0,0); retain every other check.
decode_colour_word=M.fs.decode_word
M.fs.decode_word=lambda word: (0,0) if bytes(word)==bytes(4) else decode_colour_word(word)
src=r.module('bwstd_photo_src','firmware/stage2l_switch/tools/deep_sources.py')
_,old_surface=src.surface_bank()
surface=(r.LOCAL/'candidate/recipe_bank_reference.bin').read_bytes()
base=r.ROOT/'research/gr4_nega_returns_r1/local/candidate/DEEPTBL_50mm_gr4_posi_nega_r1.DAT'
old=src.parse(base.read_bytes(),old_surface)
new=src.parse((r.LOCAL/'candidate/DEEPTBL_50mm_bw03_standard.DAT').read_bytes(),surface)
daily=src.parse((r.ROOT/'research/stage2l_leica_0708/local/DEEPTBL_v6_leica.DAT').read_bytes(),old_surface)
assert old[3]['written'][:2]==daily[3]['written'][:2]
M.base.entries={f'{e["slot"]:02d}':e for e in old}
M.base.entries['standard03']=new[3]
M.base.entries['reboot04']=new[0]
CAL=json.loads((r.ROOT/'research/refit_50mm_r7/local/folds/full/calibration.json').read_text())
assert CAL['selector_bytes_04']['raw13']==[3,4,3,3,3,3,3,3,3,3,2,2,2]
DNG=r.module('bwstd_dng','research/color_table_fit/dng_scene.py')
session=r.module('bwstd_tiff_patch','research/chart_session_20261024/session_runtime.py')
session.patch_tiff(DNG.analyze_capture().Tiff)
AR=r.module('bwstd_meta','research/hue_ring/analyze_ring.py')
session.patch_tiff(AR.s2d().Tiff)
r.freeze.add(r.ROOT/p for p in s.INPUTS)


def stats(v):
    v=np.asarray(v,float)
    return dict(n=int(v.size),median=float(np.median(v)),p90=float(np.percentile(v,90)),
                max=float(np.max(v)),mean=float(np.mean(v)))


def sample(d,mapping,rgb,centers,side):
    dx,dy=np.meshgrid(np.arange(-side//2,side//2),np.arange(-side//2,side//2))
    xs=centers[:,0,None]+dx.ravel();ys=centers[:,1,None]+dy.ravel()
    cy,cx=mapping.pixels(ys,xs)
    y0,x0,_,_=d.crop_window();ry,rx=cy+y0,cx+x0
    pixels=d.normalised_at(ry,rx);cfa=d.cfa_at(ry,rx)
    raw=np.column_stack([np.sum(np.where(cfa==k,pixels,0),axis=1)/np.sum(cfa==k,axis=1) for k in range(3)])
    sd=np.column_stack([np.sqrt(np.sum(np.where(cfa==k,(pixels-raw[:,k,None])**2,0),axis=1)/
                                    np.sum(cfa==k,axis=1)) for k in range(3)])
    maximum=np.column_stack([np.max(np.where(cfa==k,pixels,-1),axis=1) for k in range(3)])
    wbraw=raw/d.as_shot_neutral
    result=dict(raw=raw,raw_wb=wbraw,raw_sd=sd,raw_max=maximum,
                x=calibrate.apply_calibration(wbraw,CAL))
    if rgb is not None:
        blocks=rgb[ys,xs].astype(float)
        result.update(jpeg=blocks.mean(1),jpeg_sd=blocks.std(1))
    return result


def render(d,mapping,orientation,stem):
    w,h=mapping.Wj,mapping.Hj
    out=np.empty((h//4,w//4,3),np.uint8)
    after=np.empty_like(out)
    # Four by four CFA means make a quarter-size scene prediction. They
    # do not model demosaic, noise reduction or the spatial sharpening kernel.
    for y in range(0,h//4,32):
        yy,xx=np.meshgrid(np.arange(y,min(y+32,h//4))*4+2,np.arange(w//4)*4+2,indexing='ij')
        centers=np.column_stack([xx.ravel(),yy.ravel()])
        values=sample(d,mapping,None,centers,4)
        for canvas,slot in ((out,'standard03'),(after,'04')):
            pred=M.predict(slot,values['x']).reshape(xx.shape+(3,))
            canvas[y:y+xx.shape[0]]=np.rint(pred).clip(0,255).astype(np.uint8)
    folder=r.LOCAL/'predicted';folder.mkdir(exist_ok=True)
    files=[]
    for name,canvas in (('new03',out),('post_power_cycle04',after)):
        path=folder/(stem+'_'+name+'.JPG')
        im=Image.fromarray(canvas)
        # Keep the source orientation in the JPEG; image dimensions remain
        # in the sensor's stored orientation, as in the input camera JPEG.
        exif=Image.Exif();exif[274]=orientation
        im.save(path,quality=95,subsampling=0,exif=exif)
        files.append(str(path.relative_to(r.HERE)))
    return files


checks=[];pooled_dl=[];pooled_de=[];pooled_actual_chroma=[]
for number in FRAMES+ANCHORS:
    stem=f'R805{number:04d}';jp,dp=CAP/(stem+'.JPG'),CAP/(stem+'.DNG')
    meta=AR.read_meta(jp,dp,None)
    d=DNG.Dng(dp)
    with Image.open(jp) as im:
        rgb=np.asarray(im.convert('RGB'));orientation=im.getexif().get(274,1)
    h,w=rgb.shape[:2]
    mapping=DNG.RawMap(d,(w,h),orientation)
    xx,yy=np.meshgrid(np.linspace(48,w-49,40).astype(int),np.linspace(48,h-49,28).astype(int))
    centers=np.column_stack([xx.ravel(),yy.ravel()])
    a=sample(d,mapping,rgb,centers,12)
    valid=((a['raw_max']<.98).all(1)&(a['raw']>.0005).all(1)&
           (a['jpeg']>3).all(1)&(a['jpeg']<252).all(1)&
           (a['jpeg_sd'].max(1)<10)&(a['raw_sd'].max(1)<.025))
    assert valid.sum()>=20
    x,actual=a['x'][valid],a['jpeg'][valid]
    slot='standard03' if number in FRAMES else '04'
    pred=M.predict(slot,x);legacy=M.predict('03',x)
    lab=M.fs.lab_from_codes(pred);actual_lab=M.fs.lab_from_codes(actual)
    dl=abs(lab[:,0]-actual_lab[:,0]);de=M.de(pred,actual)
    reset=M.predict('reboot04',x)
    # The stock entry must follow the very same branch as actual Standard.
    reset_error=float(np.max(abs(reset-M.predict('04',x))))
    assert reset_error<1e-10,reset_error
    assert np.array_equal(np.rint(reset),np.rint(M.predict('04',x)))
    cast=np.ptp(pred,axis=1)
    result=dict(frame=stem,when=meta.get('when'),iso=meta['iso'],selector=meta['selector'],
        n_grid=len(valid),n_valid=int(valid.sum()),prediction_slot=slot,
        abs_dL=stats(dl),de00=stats(de),max_rgb_channel_spread=float(cast.max()),
        actual_lab_chroma=stats(np.linalg.norm(actual_lab[:,1:],axis=1)),
        new_vs_legacy_max_code=float(np.max(abs(pred-legacy))) if number in FRAMES else None,
        reset_vs_04_max_code=reset_error,mapping=mapping.describe(),
        raw_sha256=r.freeze.digest(dp),jpeg_sha256=r.freeze.digest(jp),
        calibration_iso=200,frame_iso_calibrated=meta['iso']==200,
        calibration_extrapolation_fraction=float(np.mean(np.any((a['raw_wb'][valid]<CAL['raw_wb_min'])|
            (a['raw_wb'][valid]>CAL['raw_wb_max']),axis=1))))
    if number in FRAMES:
        assert meta['selector']==3
        assert result['new_vs_legacy_max_code']<1e-10 and result['abs_dL']['median']<1
        assert cast.max()<1e-10
        result['predicted_jpegs']=render(d,mapping,orientation,stem)
        pooled_dl.extend(dl);pooled_de.extend(de)
        pooled_actual_chroma.extend(np.linalg.norm(actual_lab[:,1:],axis=1))
    a.update(valid=valid,predicted=pred,actual_selected=actual)
    folder=r.LOCAL/'samples';folder.mkdir(exist_ok=True)
    np.savez_compressed(folder/(stem+'.npz'),**a)
    r.dump('per_frame/'+stem+'.json',result)
    checks.append(result)
    print(stem,meta['iso'],int(valid.sum()),'|dL|',round(result['abs_dL']['median'],4),
          'dE00',round(result['de00']['median'],4),flush=True)

# Dense neutral ramp and chromatic inputs verify the actual generic-colour
# computation, not just a slot-03 grayscale special case.
ramp=np.repeat(np.arange(4096,dtype=float)[:,None],3,axis=1)
rng=np.random.default_rng(20261025)
dense=np.vstack([ramp,rng.uniform(0,4095,(30000,3))])
newrgb=M.predict('standard03',dense);oldrgb=M.predict('03',dense)
old_ramp=M.predict('03',ramp);new_ramp=M.predict('standard03',ramp)
ramp_check=dict(samples=len(dense),new_vs_old_max_code=float(np.max(abs(newrgb-oldrgb))),
    max_chroma_code=float(np.ptp(newrgb,axis=1).max()),
    reset_vs_04_max_code=float(np.max(abs(M.predict('reboot04',dense)-M.predict('04',dense)))))
assert max(ramp_check[k] for k in ('new_vs_old_max_code','max_chroma_code','reset_vs_04_max_code'))<1e-10
r.dump('tone_ramps.json',dict(input=ramp[:,0],legacy03=old_ramp[:,0],standard03=new_ramp[:,0],
    stock04=M.predict('04',ramp),checks=ramp_check))

# ISO100 bypasses both recipe row-5 curves, retaining the zero-chroma rows.
j=r.Image('jlaunch3')
entries={k:v for k,v in M.base.entries.items()}
for key in ('03','standard03'):
    e=dict(entries[key]);rows=list(e['written'])
    rows[0]=j.read(0x2012F40C+13*62,62);rows[1]=j.read(0x2012FF78+13*33,33)
    e['written']=tuple(rows);M.base.entries[key]=e
iso100=dict(new_vs_old_max_code=float(np.max(abs(M.predict('standard03',dense)-M.predict('03',dense)))),
    max_chroma_code=float(np.ptp(M.predict('standard03',dense),axis=1).max()),
    hc_curve_bypassed=True,new_iso100_camera_acceptance=False)
M.base.entries=entries
summary=dict(frames=len(FRAMES),anchors=len(ANCHORS),flat_patches=len(pooled_dl),
    pooled_abs_dL=stats(pooled_dl),pooled_de00=stats(pooled_de),
    actual_lab_chroma=stats(pooled_actual_chroma),
    per_frame_median_abs_dL=stats([v['abs_dL']['median'] for v in checks[:len(FRAMES)]]),
    all_frames_median_abs_dL_under_1=all(v['abs_dL']['median']<1 for v in checks[:len(FRAMES)]),
    generic_colour_path=True,curves_equal_to_photographed_03=True,
    model_adapter='Only literal native all-zero colour words decode as (0,0); all other words retain original decoder.',
    dense_checks=ramp_check,iso100=iso100,
    calibration_sha256=r.freeze.digest(r.ROOT/'research/refit_50mm_r7/local/folds/full/calibration.json'),
    calibration_scope='Existing ISO200 04 calibration borrowed for ISO800/1600/3200 scene prediction; no frame refit.',
    predicted_jpegs='14 quarter-size (1072x712 stored) CFA-mean scene predictions, plus 14 reset04 predictions; no spatial ISP model.',
    camera_acceptance=False)
r.dump('photo_summary.json',summary)
r.dump('photo_frames.json',checks)
r.freeze.add(r.ROOT/p for p in s.INPUTS)
r.freeze.verify()
print(json.dumps(summary,ensure_ascii=False))
