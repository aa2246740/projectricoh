#!/usr/bin/env python3
"""Read-only DNG/JPEG chart-v2 analysis. See ANALYZER_USAGE.md for the manifest."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import base64
import csv
import html
import json
import math
import traceback
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from analyzer_runtime import (HERE, ROOT, Chain, Provenance, dump, input_path,
                              mount_guard, require, run_path, sha, write_sums)
import analyzer_geometry as geometry

SLOTS = ('01', '02', '03', '04', '05', '06')
UNITS = ('a12-50', 'a12-28', 'mount-a12')


def normalize_unit(value):
    if value is None:
        return None
    aliases = {'50mm': 'a12-50', '28mm': 'a12-28', 'mount': 'mount-a12',
               'a12_50': 'a12-50', 'a12_28': 'a12-28', 'mount_a12': 'mount-a12'}
    return aliases.get(str(value).lower(), str(value).lower())


def pair_inventory(folder):
    pairs, errors, bystem = [], [], {}
    # Only the supplied directory; no traversal into another worker or a mounted card.
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() not in ('.jpg', '.jpeg', '.dng'):
            continue
        p = input_path(p)
        require(p.is_file(), f'输入不是普通文件: {p}')
        key = p.stem.upper()
        bystem.setdefault(key, {}).setdefault('dng' if p.suffix.lower() == '.dng' else 'jpeg', []).append(p)
    for stem, group in sorted(bystem.items()):
        if len(group.get('jpeg', [])) != 1 or len(group.get('dng', [])) != 1:
            errors.append({'frame': stem, 'error': 'DNG/JPEG 缺失或有大小写/扩展名歧义',
                           'files': [str(p) for ps in group.values() for p in ps]})
        else:
            pairs.append({'frame': stem, 'jpeg': group['jpeg'][0], 'dng': group['dng'][0]})
    require(pairs or errors, '输入目录没有 DNG/JPEG')
    return pairs, errors


def manifest_entries(path, pairs):
    if path is None:
        return {}, {}
    value = json.loads(path.read_text())
    require(value.get('schema') == 'chart-v2-manifest/1', 'manifest schema 必须为 chart-v2-manifest/1')
    require(value.get('evidence_kind', 'camera') in ('camera', 'synthetic'), 'evidence_kind 无效')
    frames = value.get('frames', {})
    if isinstance(frames, list):
        require(all(isinstance(f, dict) and 'frame' in f for f in frames), 'frames 列表缺少 frame')
        keys = [f['frame'].upper() for f in frames]
        require(len(keys) == len(set(keys)), 'manifest frame 重复')
        frames = {f['frame'].upper(): {k: v for k, v in f.items() if k != 'frame'} for f in frames}
    require(isinstance(frames, dict), 'frames 必须是按文件 stem 索引的对象，或列表')
    result = {}
    for key, entry in frames.items():
        key = str(key).upper()
        require(Path(key).name == key and '.' not in key, 'manifest frame 用不含扩展名的文件编号')
        require(key not in result and isinstance(entry, dict), 'manifest frame 重复或记录无效')
        result[key] = dict(entry)
    inventory = {f['frame'] for f in pairs}
    excludes = value.get('exclude', [])
    require(isinstance(excludes, list) and all(isinstance(k, str) for k in excludes), 'exclude 必须是文件编号列表')
    excludes = {k.upper() for k in excludes}
    require(excludes <= inventory, 'exclude 中有不在完整配对里的文件编号')
    for block in value.get('ranges', []):
        first, last = str(block['first']).upper(), str(block['last']).upper()
        require(first in inventory and last in inventory, 'range 首尾文件不在输入配对中')
        unit = normalize_unit(block.get('unit'))
        require(unit in UNITS, 'range unit 无效')
        require(first <= last, 'range 的 first 必须早于或等于 last')
        seq = sorted(k for k in inventory if first <= k <= last and k not in excludes)
        if block.get('shoot_list'):
            require(len(seq) == (19 if unit == 'a12-50' else 9), 'shoot_list range 张数与 19/9 张不符')
            schedule = [('04', 'white', 0)] + [('04', 'screen', p) for p in range(1, 7)]
            if unit == 'a12-50':
                schedule += [(s, 'screen', p) for s in ('01', '02', '03', '05', '06') for p in (1, 4)]
            schedule += [('04', 'drift', 1), ('04', 'physical', None)]
            for k, (slot, purpose, page) in zip(seq, schedule):
                entry = {'unit': unit, 'slot': slot, 'purpose': purpose, 'expected_page': page,
                         'assignment': 'manifest-shoot-list-order'}
                entry.update(result.get(k, {})); result[k] = entry
        else:
            for k in seq:
                entry = {k2: v for k2, v in block.items() if k2 not in ('first', 'last', 'shoot_list')}
                entry.update(result.get(k, {})); result[k] = entry
    for key in excludes:
        result.setdefault(key, {})['purpose'] = 'trial'
    for key, entry in result.items():
        require(key in inventory, f'manifest 文件不在输入完整配对中: {key}')
        if 'slot' in entry:
            entry['slot'] = str(entry['slot']).zfill(2)
            require(entry['slot'] in SLOTS, '只支持配方槽 01 至 06')
        if 'unit' in entry:
            entry['unit'] = normalize_unit(entry['unit'])
            require(entry['unit'] in UNITS, 'unit 应为 a12-50/a12-28/mount-a12')
        require(entry.get('purpose', 'auto') in ('auto', 'screen', 'white', 'physical', 'drift', 'trial'),
                'purpose 无效')
        if entry.get('expected_page') is not None:
            require(type(entry['expected_page']) is int and entry['expected_page'] in range(7), 'expected_page 无效')
    return result, value


def lens_meta(path):
    with Image.open(path) as im:
        e = im.getexif()
        ex = e.get_ifd(34665)
        def plain(v):
            if isinstance(v, bytes):
                return v.decode('utf-8', 'replace').strip('\0 ')
            return str(v).strip('\0 ') if v is not None else None
        return {'model': plain(e.get(272)), 'lens_model': plain(ex.get(42036)),
                'focal_length_mm': float(ex[37386]) if ex.get(37386) is not None else None}


def unit_from_lens(lens):
    s = (lens or '').upper()
    if 'MOUNT' in s and 'A12' in s:
        return 'mount-a12'
    if 'A12' in s and '50MM' in s.replace(' ', ''):
        return 'a12-50'
    if 'A12' in s and '28MM' in s.replace(' ', ''):
        return 'a12-28'
    return None


def metadata(chain, pair, entry):
    m, errors = chain.measure.metadata(chain.ar, pair['jpeg'], pair['dng'])
    m.update(lens_meta(pair['jpeg']))
    inferred = unit_from_lens(m.get('lens_model'))
    declared = entry.get('unit')
    if inferred and declared and inferred != declared:
        errors.append(f'LensModel 单元 {inferred} 与 manifest {declared} 冲突')
    unit = declared or inferred
    slot = entry.get('slot') or ('03' if m.get('selector') == 3 else None)
    if slot and m.get('selector') != (3 if slot == '03' else 1):
        errors.append(f'选择器 {m.get("selector")} 与 manifest 槽 {slot} 的原生模式冲突')
    m.update({'unit': unit, 'unit_from_lens': inferred,
              'unit_assignment': 'manifest' if declared else 'LensModel' if inferred else 'unknown',
              'slot': slot, 'slot_assignment': 'manifest' if entry.get('slot') else
              'selector=3 implies native monochrome; inferred 03' if slot else
              'unknown: selector=1 cannot distinguish 01/02/04/05/06',
              'selector_bytes': {'0x28': m.get('selector'), '0x26': m.get('wb_record_0x26')},
              'aperture_note': entry.get('aperture_note'), 'lens_note': entry.get('lens_note')})
    return m, errors


def trimmed_median(x, trim=.1):
    x = np.asarray(x, float)
    lo, hi = np.quantile(x, (trim, 1-trim), axis=0)
    return np.array([np.median(x[:, c][(x[:, c] >= lo[c]) & (x[:, c] <= hi[c])])
                     for c in range(x.shape[1])])


def spatial_metrics(block, mask):
    """Heuristics in camera-pixel coordinates; retain numbers, not a physical diagnosis."""
    block = np.asarray(block, float)
    h, w = mask.shape
    yy, xx = np.indices((h, w))
    A = np.stack([np.ones_like(xx), xx/max(w, 1), yy/max(h, 1)], -1)
    coef = np.linalg.lstsq(A[mask], block[mask], rcond=None)[0]
    residual = np.where(mask[..., None], block - A @ coef, 0.)
    win = np.outer(np.hanning(h), np.hanning(w))*mask
    nwin = max(float(win.sum()), 1.)
    fft = np.abs(np.fft.fft2(residual*win[..., None], axes=(0, 1)))
    fy, fx = np.fft.fftfreq(h)[:, None], np.fft.fftfreq(w)[None, :]
    high = np.hypot(fx, fy) >= .10
    powers = fft[high]**2
    peak = float(np.max(powers)) if powers.size else 0.
    ratio = peak/max(float(np.median(powers)) if powers.size else 0., 1e-8)
    amp = 2*math.sqrt(peak)/nwin
    y = residual @ [.299, .587, .114]
    count = mask.sum(axis=1)
    rows = y.sum(axis=1)/np.maximum(count, 1)
    keep = count > max(4, w*.35)
    rows = rows[keep]
    if len(rows) >= 12:
        smooth = ndimage.gaussian_filter1d(rows, 1.2)
        f = np.abs(np.fft.rfft((rows-rows.mean())*np.hanning(len(rows))))
        hz = np.fft.rfftfreq(len(rows))
        # Sub-ROI broad waves are retained as a separate bright-band indicator.
        good = (hz >= .018) & (hz <= .16)
        band_amp = 2*float(f[good].max())/max(float(np.hanning(len(rows)).sum()), 1.) if good.any() else 0.
        band_range = float(np.percentile(smooth, 95)-np.percentile(smooth, 5))
        positive = float(np.percentile(smooth, 95))
    else:
        band_amp = band_range = positive = 0.
    flags = []
    if ratio > 25. and amp > 1.5:
        flags.append('moire-suspect')
    if band_amp > 1.8 and len(rows) >= 12:
        flags.append('flicker-banding-suspect')
    if band_range > 6. and positive > 3.:
        flags.append('bright-band-suspect')
    return {'moire_peak_ratio': ratio, 'moire_amplitude_codes': amp,
            'row_band_amplitude_codes': band_amp, 'row_band_range_codes': band_range,
            'row_bright_p95_codes': positive, 'flags': flags,
            'interpretation': 'image-structure heuristics, not proof of display PWM or sensor moire'}


def native_stats(ds, region, dm):
    stats = ds.stats(region)
    ys, xs = dm.roi_pixels(ds.map, region)
    cy, cx, _, _ = ds.dng.crop_window()
    v = ds.dng.normalised_at(ys+cy, xs+cx)
    col = ds.dng.cfa_at(ys+cy, xs+cx)
    med = []
    for c in range(3):
        s = v[col == c]
        require(len(s) >= 8 and np.isfinite(s).all(), 'RAW ROI 通道缺样本或非有限')
        low, high = np.quantile(s, (.1, .9))
        med.append(float(np.median(s[(s >= low) & (s <= high)])))
    stats['mean_cam'], stats['cam'] = stats['cam'], med
    stats['estimator'] = 'per-CFA-channel 10%-90% trimmed median; unbalanced native RGB'
    return stats


def sample_roi(rgb, region, ds, chain):
    ya, yb, xa, xb, mask, _ = region
    block = np.asarray(rgb[ya:yb, xa:xb], float)
    require(mask.sum() >= 48, '色块 ROI 少于 48 个 JPEG 像素')
    values = block[mask]
    quality = spatial_metrics(block, mask)
    raw_region = {'mask': mask, 'origin_yx': [ya, xa]}
    raw = native_stats(ds, raw_region, chain.dng)
    flags = list(quality['flags'])
    if raw['clip_frac'] > .001:
        flags.append('raw-saturation')
    clip = float(np.mean(np.any((values <= 2) | (values >= 253), axis=1)))
    if clip > .01:
        flags.append('jpeg-clipping')
    return {'jpeg_rgb': trimmed_median(values).tolist(), 'spatial_sd': values.std(axis=0).tolist(),
            'raw_rgb': raw['cam'], 'raw': raw, 'quality': quality, 'flags': flags,
            'jpeg_clip_fraction': clip, 'roi_camera_bbox': [xa, ya, xb, yb], 'jpeg_sample_count': int(mask.sum())}


def registration_ok(ds):
    v = ds.verify or {}
    return bool(v.get('ok') and v.get('after_offset', {'ok': True}).get('ok'))


def chart_patches(rgb, geo, page, layout, ds, chain):
    result = []
    for spec in layout['patches']:
        if spec['page'] != page:
            continue
        rect = spec['roi_bbox_px']
        corners = np.array([[rect[0], rect[1]], [rect[2], rect[1]],
                            [rect[2], rect[3]], [rect[0], rect[3]]])
        poly = chain.ar.apply_h(geo['H'], corners)
        in_frame = bool(np.all((poly[:, 0] >= 1) & (poly[:, 0] < rgb.shape[1]-1)
                               & (poly[:, 1] >= 1) & (poly[:, 1] < rgb.shape[0]-1)))
        q = {'patch_id': spec['id'], 'sample_key': spec['sample_key'], 'class': spec['category'],
             'page': page, 'nominal_p3_8bit': spec['p3_8bit'], 'nominal_lab_d65': spec['lab_d65'],
             'roi_polygon': poly.tolist(), 'chart_roi_bbox': rect}
        try:
            require(in_frame, 'ROI 部分落在画外')
            roi = chain.ar.roi_mask(geo, rect, rgb.shape)
            require(roi is not None, 'ROI 没有有效面积')
            q.update(sample_roi(rgb, roi, ds, chain))
        except ValueError as e:
            q.update({'raw_rgb': None, 'jpeg_rgb': None, 'spatial_sd': None, 'flags': ['invalid-roi'], 'error': str(e)})
        if not registration_ok(ds):
            q['flags'].append('raw-jpeg-registration-failed')
        q['valid'] = not q['flags']
        result.append(q)
    return result


def physical_patches(rgb, ds, chain):
    # analyze_2e owns lattice geometry. DngScene owns RAW/JPEG registration and
    # native CFA samples, so no second coordinate convention or raw decoder is introduced.
    cy, cx, hh, ww = ds.dng.crop_window()
    pattern = ds.dng.crop_cfa_phase()
    require(pattern.shape == (2,2), 'DIOPTIX 点阵适配只支持 2x2 Bayer CFA')
    asn = np.asarray(ds.dng.as_shot_neutral)
    require(asn.shape == (3,) and np.all(asn > 0), 'DIOPTIX 缺少有效 AsShotNeutral')
    # Preserve analyze_2e's WB-luminance definition, while taking CFA phase,
    # linearization and spatial black levels from DngScene for each module.
    Y = np.zeros((hh//2,ww//2))
    for dy,dx in np.ndindex(2,2):
        c = int(pattern[dy,dx])
        y = cy+dy+2*np.arange(hh//2)
        x = cx+dx+2*np.arange(ww//2)
        v = ds.dng.normalised_at(y[:,None],x[None,:])
        Y += [.25,.5,.25][c] * v / (asn[c]*np.count_nonzero(pattern == c))
    half, geo = chain.physical.detect_lattice(Y)
    centres = half*2 + [1.,1.]
    # Map RAW crop coordinates back to JPEG, including the verified integer shift.
    # Inverse of RawMap.points is a homography for the supported orthogonal maps.
    probes = np.array([[0, 0], [rgb.shape[1], 0], [rgb.shape[1], rgb.shape[0]], [0, rgb.shape[0]]], float)
    rx, ry = ds.map.points(probes[:, 0], probes[:, 1])
    raw_to_jpg = chain.ar.dlt(np.column_stack([rx, ry]), probes)
    centres = chain.ar.apply_h(raw_to_jpg, centres)
    grid = centres.reshape(4, 6, 2)
    pitch = min(float(np.median(np.linalg.norm(np.diff(grid, axis=1), axis=2))),
                float(np.median(np.linalg.norm(np.diff(grid, axis=0), axis=2))))
    half = max(4, int(round(.16*pitch)))
    result = []
    for i, ((x, y), label) in enumerate(zip(centres, chain.physical.LABELS)):
        x0, x1, y0, y1 = round(x-half), round(x+half), round(y-half), round(y+half)
        require(x0 >= 0 and y0 >= 0 and x1 < rgb.shape[1] and y1 < rgb.shape[0], '实体卡 ROI 落在画外')
        mask = np.ones((y1-y0, x1-x0), bool)
        q = sample_roi(rgb, (y0, y1, x0, x1, mask, None), ds, chain)
        q.update({'patch_id': label, 'sample_key': label, 'class': 'gray' if label.startswith('D') else 'physical',
                  'page': None, 'name': chain.physical.NAMES[label],
                  'roi_polygon': [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]})
        if not registration_ok(ds):
            q['flags'].append('raw-jpeg-registration-failed')
        q['valid'] = not q['flags']; result.append(q)
    greys = np.array([p['raw_rgb'] for p in result[-6:]])/np.asarray(ds.dng.as_shot_neutral)
    luminance = greys @ [.25, .5, .25]
    require(np.all(np.diff(luminance) < 0), 'DIOPTIX RAW 灰阶未从白到黑递减，拒绝错误朝向')
    neutral_dev = float(np.max(abs(greys[:5, [0, 2]]/greys[:5, 1, None]-1)))
    require(neutral_dev <= .15, 'DIOPTIX 底行 RAW 不是中性灰阶')
    geo.update({'method': 'analyze_2e.detect_lattice on native RAW luminance',
                'orientation_check': 'D1..D6 RAW ramp decreasing; D1..D5 neutral',
                'raw_grey_max_channel_deviation': neutral_dev, 'pitch_px': pitch})
    return result, geo


def overlay(rgb, patches, caption, dest):
    im = Image.fromarray(rgb).convert('RGB')
    scale = min(1., 960/im.width)
    im = im.resize((round(im.width*scale), round(im.height*scale)))
    draw = ImageDraw.Draw(im)
    for p in patches:
        poly = [(x*scale, y*scale) for x, y in p.get('roi_polygon', [])]
        if not poly:
            continue
        color = '#20ec87' if p['valid'] else '#ff5252'
        draw.line(poly+[poly[0]], fill=color, width=2)
        draw.text(poly[0], str(p['patch_id']), fill=color)
    draw.rectangle((0,0,im.width,24), fill='#151b24')
    draw.text((8,5), caption, fill='white')
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, quality=87)


def analyze_pair(pair, entry, layout, chain, out):
    for k in ('jpeg', 'dng'):
        chain.p.add(pair[k])
    meta, errors = metadata(chain, pair, entry)
    frame = {'frame': pair['frame'], 'id': pair['frame'], 'paths': {k: str(pair[k]) for k in ('jpeg','dng')},
             'hashes': {'JPEG': sha(pair['jpeg']), 'DNG': sha(pair['dng'])},
             'meta': meta, 'metadata_errors': errors, 'manifest': entry,
             'unit': meta['unit'], 'slot': meta['slot'], 'purpose': entry.get('purpose', 'auto')}
    with Image.open(pair['jpeg']) as im:
        rgb = np.asarray(im.convert('RGB'))
    ds = chain.dng.DngScene(pair['dng'], pair['jpeg'], jpeg_rgb=rgb, verify=True)
    require(ds.map.Wc == rgb.shape[1] and ds.map.Hc == rgb.shape[0], 'DNG/JPEG 几何尺寸不一致')
    purpose = entry.get('purpose', 'auto')
    if purpose == 'physical':
        patches, geo = physical_patches(rgb, ds, chain)
        ident = {'page': None, 'confidence': 'raw-lattice-and-grey-ramp'}; kind = 'physical'
    else:
        try:
            geo, ident = geometry.locate(rgb, layout, chain.ar)
            kind = 'screen'
        except ValueError as e:
            first_error = str(e)
            try:
                geo, ident = geometry.locate_white(rgb, layout, chain.ar)
                kind = 'white'
                geo['screen_detection_failure'] = first_error
            except ValueError as white_error:
                try:
                    patches, geo = physical_patches(rgb, ds, chain)
                    geo['screen_detection_failure'] = first_error
                    ident = {'page': None, 'confidence': 'raw-lattice-and-grey-ramp'}; kind = 'physical'
                except (ValueError, IndexError, np.linalg.LinAlgError) as physical_error:
                    raise ValueError(f'无法分类: chart={first_error}; white={white_error}; DIOPTIX={physical_error}')
        if kind != 'physical':
            patches = chart_patches(rgb, geo, ident['page'], layout, ds, chain)
    expected = entry.get('expected_page')
    if expected is not None and expected != ident['page']:
        errors.append(f'manifest 期望页 {expected}，实际识别页 {ident["page"]}')
    if purpose in ('physical', 'white', 'screen', 'drift'):
        expected_kind = 'screen' if purpose == 'drift' else purpose
        if expected_kind != kind:
            errors.append(f'manifest 用途 {purpose} 与实际 {kind} 冲突')
    for p in patches:
        if errors:
            p['flags'].append('frame-metadata-or-manifest-error'); p['valid'] = False
        if p['raw_rgb'] is not None:
            p['raw_wb'] = (np.asarray(p['raw_rgb'])/np.asarray(meta['asn'])).tolist()
            p['xyz_camera'] = ds.xyz(p['raw_rgb'], ds.white_as_shot)[0].tolist()
    frame.update({'kind': kind, 'page': ident['page'], 'identification': ident,
                  'geometry': {k: v for k,v in geo.items() if k != 'Hinv'},
                  'patches': patches, 'raw_jpeg_registration': ds.verify, 'dng_white': ds.white_as_shot_info,
                  'raw_definition': '(linearized DN-black)/(white-black), native CFA RGB, no WB, no demosaic',
                  'sampling': '10%-90% trimmed median; spatial_sd is untrimmed JPEG RGB population SD in 8-bit codes',
                  'status': 'ok' if not errors and registration_ok(ds) else 'quality-failed',
                  'valid_patches': sum(p['valid'] for p in patches)})
    thumb = out/'overlays'/f'{pair["frame"]}.jpg'
    overlay(rgb, patches, f'{pair["frame"]}  {kind}  page={ident["page"]}  slot={meta["slot"]}', thumb)
    frame['overlay'] = str(thumb.relative_to(out))
    return frame


def write_csv(out, frames):
    columns = ('frame','page','patch_id','class','raw_rgb','jpeg_rgb','valid','spatial_sd',
               'sample_key','unit','slot','iso','shutter_s','aperture','white_balance','selector_bytes','flags')
    with (out/'patches.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns); w.writeheader()
        for frame in frames:
            m = frame['meta']
            for p in frame.get('patches', []):
                row = {k: p.get(k) for k in columns[:8]}
                row.update({'frame': frame['frame'], 'sample_key': p['sample_key'], 'unit': frame['unit'],
                            'slot': frame['slot'], 'iso': m.get('iso'), 'shutter_s': m.get('t'), 'aperture': m.get('f'),
                            'white_balance': {'exif': m.get('wb_exif'), 'record_0x26': m.get('wb_record_0x26'), 'asn': m.get('asn')},
                            'selector_bytes': m.get('selector_bytes'), 'flags': p['flags']})
                for k, v in row.items():
                    if isinstance(v, (list, dict)):
                        row[k] = json.dumps(v, ensure_ascii=False, separators=(',', ':'))
                    elif isinstance(v, bool):
                        row[k] = 'true' if v else 'false'
                w.writerow(row)


def write_quality_html(out, frames, errors, scoring, stability):
    cards = []
    for f in frames:
        im = base64.b64encode((out/f['overlay']).read_bytes()).decode()
        flags = {}
        for p in f['patches']:
            for flag in p['flags']:
                flags[flag] = flags.get(flag,0)+1
        page = f'第 {f["page"]} 页' if f['kind']=='screen' else '白页' if f['kind']=='white' else 'DIOPTIX 实体卡'
        cards.append(f'<article><h2>{html.escape(f["frame"])} · {page}</h2>'
                     f'<p>单元 {f["unit"] or "未识别"}，配方 {f["slot"] or "未指派"}，有效色块 {f["valid_patches"]}/{len(f["patches"])}</p>'
                     f'<p>{html.escape(str(flags))}</p><img alt="取样框，绿为有效、红为排除" src="data:image/jpeg;base64,{im}"></article>')
    slotrows = []
    for slot, result in scoring.get('slots', {}).items():
        sim = result['similarity']['value']
        median = result['measured_vs_target']['median']
        slotrows.append(f'<tr><td>{slot}</td><td>{result["measured_vs_target"]["n"]}</td>'
                        f'<td>{f"{median:.3f}" if median is not None else "无有效样本"}</td>'
                        f'<td>{"原厂控制" if slot=="04" else f"{sim:.1%}" if sim is not None else "分母不足"}</td></tr>')
    status_names = {'within-thresholds':'门限内', 'drift-detected':'检测到漂移',
                    'nonuniformity-suspect':'跨位置差异偏大', 'unknown':'数据不足',
                    'unknown-incomplete':'页数或锚点不足', 'unknown-metadata-change':'曝光或白平衡变化'}
    stability_rows = []
    for unit in sorted(set(stability.get('drift',{})) | set(stability.get('uniformity',{}))):
        drift = stability.get('drift',{}).get(unit,{})
        uniform = stability.get('uniformity',{}).get(unit,{})
        d = status_names.get(drift.get('status'),'未测量')
        ev = drift.get('median_raw_EV')
        if ev is not None:
            d += f'，{ev:+.3f} EV'
        u = status_names.get(uniform.get('status'),'未测量')
        stability_rows.append(f'<tr><td>{html.escape(unit)}</td><td>{d}</td><td>{u}</td></tr>')
    synthetic = frames and all(f.get('evidence_kind')=='synthetic' for f in frames)
    evidence = '<p class="note">合成自检数据，不能当作新版色卡的相机实拍验收。</p>' if synthetic else ''
    bad = sum(not p['valid'] for f in frames for p in f['patches'])
    score_status = {'ok':'完整','partial':'页数不完整','unassigned':'缺少配方或单元归属','error':'存在评分错误'}.get(scoring.get('status'),'未知')
    error_text = ''.join(f'<li>{html.escape(str(e.get("frame")))}：{html.escape(e.get("error",""))}</li>'
                         for e in errors+scoring.get('errors',[]))
    content = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>chart-v2 检测质量</title>'
       '<style>body{font:15px system-ui;margin:24px auto;max-width:1000px;padding:0 16px;color:#18212c;background:#f5f6f8}'
       'article{padding:16px;margin:20px 0;background:white;border:1px solid #ccd3dd}img{width:100%;height:auto}'
       'table{border-collapse:collapse;background:white}td,th{padding:8px 16px;border:1px solid #c6ced8}'
       'pre{white-space:pre-wrap;overflow-wrap:anywhere}h1{font-size:24px}h2{font-size:18px}'
       'details{margin:24px 0}summary{cursor:pointer}.note{padding:12px;background:#fff2d5}</style>'
       f'<h1>chart-v2 检测质量</h1>{evidence}<p>{len(frames)} 帧已解析，{len(errors)} 帧失败，{bad} 块被排除。绿色框有效，红色框排除。</p>'
       '<p>结构检测只标记疑似摩尔纹、条纹和亮带。白页与跨页锚点结果包含镜头暗角、视角、曝光和屏幕响应，不能单独证明屏幕均匀性。</p>'
       f'<h2>50mm 配方评分</h2><p>评分状态：{score_status}。相似度是相对同页 04 的目标差距消除比例；负数表示变差。</p>'
       '<table><tr><th>槽</th><th>有效块</th><th>中位 ΔE00</th><th>实测相似度</th></tr>'+''.join(slotrows)+'</table>'
       '<h2>漂移与跨页一致性</h2><table><tr><th>单元</th><th>首尾漂移</th><th>跨页锚点</th></tr>'+''.join(stability_rows)+'</table>'
       + ('<h2>需要处理的错误</h2><ul>'+error_text+'</ul>' if error_text else '')
       + ''.join(cards)+'<details><summary>查看完整诊断数值和错误</summary><pre>'+html.escape(json.dumps({'scoring_status': scoring.get('status'), 'score_errors': scoring.get('errors'),
                                     'drift': stability.get('drift'), 'uniformity': stability.get('uniformity'),
                                     'frame_errors': errors}, ensure_ascii=False, indent=2))+'</pre></details></html>')
    (out/'quality.html').write_text(content)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True, help='只扫描此目录的同名 DNG+JPEG 配对')
    ap.add_argument('--manifest', help='chart-v2-manifest/1 JSON；槽号无法从 EXIF 完整自动恢复')
    ap.add_argument('--out', required=True, help='新的 research/chart_v2/local/runs/<name>')
    ap.add_argument('--targets', help='可选 closedloop-targets/1，延用原有严格 DNG 目标绑定')
    ap.add_argument('--table', help='可选被测 noprobe DEEPTBL0.DAT；默认与原 measure.py 一致')
    args = ap.parse_args(argv)
    guard = mount_guard()
    folder = input_path(args.input); require(folder.is_dir(), 'input 不是目录')
    out = run_path(args.out)
    pairs, errors = pair_inventory(folder)
    manifest = input_path(args.manifest) if args.manifest else None
    entries, config = manifest_entries(manifest, pairs)
    p = Provenance(); p.sealed()
    for code in sorted(HERE.glob('analy*.py')):
        p.add(code)
    if manifest:
        p.add(manifest)
    out.mkdir(parents=True)
    layout = json.loads((HERE/'patches.json').read_text())
    chain = Chain(out, p)
    frames = []
    for error in errors:
        dump(out/'frames'/f'{error["frame"]}.json', {'status':'error', **error})
    for pair in pairs:
        try:
            f = analyze_pair(pair, entries.get(pair['frame'], {}), layout, chain, out)
            f['evidence_kind'] = config.get('evidence_kind', 'camera')
            frames.append(f)
            print(f'{pair["frame"]}: {f["kind"]} page={f["page"]} slot={f["slot"]} valid={f["valid_patches"]}/{len(f["patches"])}', flush=True)
        except Exception as e:
            error = {'frame': pair['frame'], 'error': f'{type(e).__name__}: {e}',
                     'traceback': traceback.format_exc(), 'paths': {k:str(pair[k]) for k in ('jpeg','dng')}}
            errors.append(error)
            dump(out/'frames'/f'{pair["frame"]}.json', {'status':'error', **error})
            print(f'{pair["frame"]}: ERROR {type(e).__name__}: {e}', flush=True)
    from analyzer_scoring import score_all, stability_report
    scoring = score_all(frames, chain, out, args.targets, args.table)
    stability = stability_report(frames, chain)
    for frame in frames:
        dump(out/'frames'/f'{frame["frame"]}.json', frame)
    write_csv(out, frames)
    dump(out/'scores.json', scoring); dump(out/'stability.json', stability)
    extraction_pass = not errors and all(f['status']=='ok' for f in frames)
    checks = {'pass': extraction_pass and all(p['valid'] for f in frames for p in f['patches']),
              'extraction_pass': extraction_pass,
              'frames': len(frames), 'frame_errors': errors, 'mount': guard,
              'quality_thresholds': {'moire_peak_ratio':25, 'moire_amplitude_codes':1.5,
                  'row_band_amplitude_codes':1.8, 'bright_band_range_codes':6., 'raw_saturation_level':.98,
                  'raw_saturation_fraction':.001, 'jpeg_clip_fraction':.01, 'minimum_jpeg_roi_pixels':48},
              'score_status': scoring['status'], 'evidence_kind': config.get('evidence_kind', 'camera'),
              'new_chart_camera_frames': [f['frame'] for f in frames if f['evidence_kind']=='camera' and f['kind'] in ('screen','white')],
              'new_chart_camera_acceptance': 'not-assessed'}
    checks['scoring_required_manifest_fields'] = ['unit', 'slot']
    checks['unassigned_frames'] = [f['frame'] for f in frames if f['unit'] is None or f['slot'] is None]
    dump(out/'quality.json', checks)
    write_quality_html(out, frames, errors, scoring, stability)
    dump(out/'provenance.json', p.finish())
    write_sums(out)
    print(json.dumps({'out': str(out), 'frames':len(frames), 'failed':len(errors), 'scoring':scoring['status']}, ensure_ascii=False))
    return 0 if checks['extraction_pass'] and scoring['status'] != 'error' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        raise SystemExit(2)
