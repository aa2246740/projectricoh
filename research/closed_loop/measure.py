#!/usr/bin/env python3
"""Measure paired camera DNG/JPEG frames. All numeric output stays in local/."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import hashlib
import json
import math
import numpy as np
from PIL import Image
from common import ROOT, LOCAL, helper, read, dump, require, input_path, output_path, sha, mount_guard, Provenance
from model import Engine, DEFAULT_TABLE
from targets import Targets

SLOTS = ('04', '01', '02', '03', '05', '06')
CHARTS = {'hue-ring': 'hue-ring', 'physical': 'physical'}
PHYSICAL_NAMES = ('深肤色', '浅肤色', '天空蓝', '叶绿', '蓝紫花色', '蓝绿色',
                  '橙色', '紫蓝', '中红', '紫色', '黄绿', '橙黄',
                  '蓝色', '绿色', '红色', '黄色', '品红', '青色',
                  '白色', '浅灰', '中浅灰', '中灰', '深灰', '黑色')


def stats(e):
    e = np.asarray(e, float)
    require(np.isfinite(e).all(), '色差包含非有限值')
    if not len(e):
        return {'n': 0, 'median': None, 'p90': None, 'max': None,
                'share_under_1': None, 'share_under_2': None, 'share_under_3': None}
    return {'n': len(e), 'median': float(np.median(e)), 'p90': float(np.percentile(e, 90)),
            'max': float(e.max()), **{f'share_under_{k}': float(np.mean(e < k)) for k in (1, 2, 3)}}


def similarity(errors, baseline_errors, floor=.25):
    a, b = stats(errors), stats(baseline_errors)
    if not a['n'] or not b['n'] or b['median'] < floor:
        return {'value': None, 'reason': '04 到目标的中位色差不足 0.25，分母不稳定', 'baseline': b}
    return {'value': 1-a['median']/b['median'], 'baseline': b,
            'definition': '1 - median(slot to its target) / median(matched 04 to its own target)',
            'is_absolute_original_camera_similarity': False}


def validate_manifest(manifest):
    require(manifest.get('schema') == 'closedloop-frames/1', '帧清单 schema 应为 closedloop-frames/1')
    require(manifest.get('evidence_kind', 'camera') in ('camera', 'synthetic'), 'evidence_kind 错误')
    frames = manifest.get('frames')
    require(isinstance(frames, list) and frames, 'frames 不能为空')
    ids = set()
    dry = manifest.get('diagnostic_only', False)
    for f in frames:
        require(not set(f) - {'id', 'set', 'slot', 'chart', 'jpeg', 'dng', 'baseline', 'table'}, '帧清单有未知字段')
        require(isinstance(f.get('id'), str) and f['id'] and f['id'] not in ids, '帧 id 必须唯一')
        ids.add(f['id'])
        require(f.get('slot') in SLOTS or dry and f.get('slot') in ('07', '08'), '槽位错误')
        require(f.get('chart') in CHARTS and isinstance(f.get('set'), str) and f['set'], 'chart 或 set 错误')
        require(f.get('jpeg'), '帧缺少 jpeg')
    for f in frames:
        base = next((b for b in frames if b['id'] == f.get('baseline')), None)
        require(base is not None and base['slot'] == '04' and base['set'] == f['set'] and base['chart'] == f['chart'],
                f'{f["id"]}: 必须指定同 set、同 chart 的 04 baseline')
    return frames


def pair_paths(frame):
    jpg = input_path(frame['jpeg'])
    require(jpg.suffix.lower() in ('.jpg', '.jpeg') and jpg.is_file(), '缺少 JPEG')
    choices = [p for p in (jpg.with_suffix('.DNG'), jpg.with_suffix('.dng')) if p.is_file()]
    require(bool(choices) and all(p.samefile(choices[0]) for p in choices), '缺少相邻 DNG 或大小写配对有歧义')
    if frame.get('dng'):
        require(input_path(frame['dng']).samefile(choices[0]), 'DNG 必须是相邻同名文件')
    return jpg, choices[0]


def metadata(ar, jpg, dng):
    jm, dm = ar.read_meta(jpg, None, None), ar.read_meta(jpg, dng, None)
    errors = [f'{kind}: {meta[k]}' for kind, meta in (('JPEG', jm), ('DNG', dm))
              for k in ('exif_error', 'makernote_error') if k in meta]
    keys = ('program', 'exposure_mode', 't', 'f', 'iso', 'wb_exif', 'selector', 'wb_record_0x26', 'raw13', 'when')
    errors += [f'JPEG/DNG {k} 不一致' for k in keys if jm.get(k) != dm.get(k)]
    return dm, errors


def metadata_checks(frames):
    errors, warnings = [], []
    ref = frames[0]['meta']
    for f in frames:
        m = f['meta']; tag = f['id']
        errors.extend(f'{tag}: {v}' for v in f.get('metadata_errors', []))
        for k, v in (('program', 1), ('exposure_mode', 1), ('wb_exif', 1), ('wb_record_0x26', 5)):
            if m.get(k) != v:
                errors.append(f'{tag}: {k}={m.get(k)}，要求 {v}')
        for k in ('iso', 't', 'f'):
            value = m.get(k)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                errors.append(f'{tag}: {k} 缺失或无效')
            elif value != ref.get(k):
                errors.append(f'{tag}: {k} 在组内变化')
        if m.get('iso') != 200:
            warnings.append(f'{tag}: ISO={m.get("iso")}，正式回拟要求 ISO 200'
                            + ('；ISO 800 未标定，仍报告实拍到目标' if m.get('iso') == 800 else ''))
        a, b = m.get('asn'), ref.get('asn')
        if a is None or b is None or len(a) != 3 or len(b) != 3 or not np.allclose(a, b, rtol=1e-6, atol=1e-6):
            errors.append(f'{tag}: AsShotNeutral 缺失或改变')
        expected = 3 if f['slot'] == '03' else 1
        if m.get('selector') != expected:
            errors.append(f'{tag}: 原生模式 {m.get("selector")} 与槽位应有的 {expected} 不符')
    return {'pass': not errors, 'errors': errors, 'warnings': warnings,
            'slot_assignment': '清单人工标记；EXIF 不记录配方槽号，原生模式只区分彩色和黑白'}


def physical_orientation_checks(sampled, slot):
    """The RAW neutral ramp determines orientation; styled JPEG order is advisory."""
    physical = helper('physical')
    try:
        checks = physical.orientation_checks(sampled, True)
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc
    by = {q['label']: q for q in sampled}
    grey = np.asarray([by[f'D{k}']['camera_rgb_wb'] for k in range(1, 6)], float)
    require(np.isfinite(grey).all() and np.all(grey > 0), 'RAW 灰块无效')
    deviation = float(np.max(abs(grey[:, [0, 2]] / grey[:, 1, None] - 1)))
    checks['raw_grey_rgb_over_g_max_dev'] = deviation
    checks['raw_grey_neutral_limit'] = .15
    require(deviation <= .15, f'RAW 底行不是中性灰阶：最大通道偏差 {deviation:.4f}')
    checks['authority'] = 'own DNG neutral ramp; DNG/JPEG registration checked separately'
    checks['warnings'] = []
    if slot == '03':
        return checks
    b_row = [by[f'C{k}']['lab'][2] for k in range(1, 7)]
    a1, a2 = by['A1'], by['A2']
    checks.update({'third_row_b_max_is_C4_yellow': int(np.argmax(b_row)) == 3,
                   'third_row_b_min_is_C1_blue': int(np.argmin(b_row)) == 0,
                   'A1_is_dark_skin': bool(a1['lab'][1] > 5 and a1['lab'][2] > 3 and a1['L']+5 < a2['L']),
                   'grey_row_max_C': max(by[f'D{k}']['C'] for k in range(1, 7))})
    failed = [k for k, value in checks.items() if k.startswith(('third', 'A1')) and not value]
    require(slot != '04' or not failed, f'orientation check failed: {checks}')
    if failed:
        checks['warnings'].append('风格化 JPEG 色序与原厂不同；RAW 朝向通过：' + ', '.join(failed))
    return checks


def extract(frame, p, seed=None):
    jpg, dng = pair_paths(frame)
    p.add(jpg); p.add(dng)
    code_digest = sha(Path(__file__)) + sha(p.add(LOCAL / 'vendor_manifest.json'))
    seed_digest = '' if seed is None else hashlib.sha256(np.asarray(seed).tobytes()).hexdigest()
    key = hashlib.sha256((sha(jpg)+sha(dng)+code_digest+seed_digest+frame['chart']).encode()).hexdigest()
    cache = LOCAL / 'frame_cache' / (key + '.json')
    if cache.exists():
        result = read(cache)
        result.update(frame)
        return result
    ar = helper('ar')
    meta, errors = metadata(ar, jpg, dng)
    with Image.open(jpg) as im:
        rgb = np.asarray(im.convert('RGB'))
    ds = helper('dng').DngScene(dng, jpg, jpeg_rgb=rgb, verify=True)
    require(ds.map.Wc == rgb.shape[1] and ds.map.Hc == rgb.shape[0], 'DNG/JPEG 几何尺寸不一致')
    if not ds.verify or not ds.verify.get('ok'):
        errors.append('DNG/JPEG 配准未通过')
    patches = []
    if frame['chart'] == 'hue-ring':
        lay = ar.load_layout()
        try:
            geo = ar.locate_screen(rgb, lay)
            method = 'original_checker_corners'
        except ValueError:
            geo = helper('geo').locate(ar, rgb, lay, seed)
            method = 'blur_robust_checker_border'
        sampled = ar.sample_frame(rgb, geo, lay, 40, None)
        for q, spec in zip(sampled, lay['patches']):
            require(q['ok'], f'{frame["id"]}: 色块在画外')
            x0, y0, x1, y1 = spec['bbox_px']
            ya, yb, xa, xb, mask, inner = ar.roi_mask(geo, [x0+40, y0+40, x1-40, y1-40], rgb.shape)
            raw = ds.stats({'mask': mask, 'origin_yx': [ya, xa]})
            flags = ar.flag_patch(q, argparse.Namespace(moire_ratio=20., moire_amp=1.5, edge_sd=12.))
            patches.append({'label': str(spec['id']), 'name': spec['name'], 'ring': spec['ring'],
                            'gray': spec['group'] == 'gray', 'rgb': q['rgb_trim'], 'raw': raw,
                            'flags': flags, 'roi': inner})
        geometry = {k: v for k, v in geo.items() if k != 'Hinv'}
        geometry['method'] = method
    else:
        a = helper('physical')
        old_cap = a.CAP
        try:
            a.CAP = jpg.parent
            sampled, geometry, _ = a.sample(jpg.stem)
            geometry['orientation_checks'] = physical_orientation_checks(sampled, frame['slot'])
        finally:
            a.CAP = old_cap
        for i, q in enumerate(sampled):
            raw = ds.stats({'rect': q['roi']})
            block = rgb[q['roi'][1]:q['roi'][3], q['roi'][0]:q['roi'][2]]
            clipped = np.mean(np.any((block <= 2) | (block >= 253), axis=-1))
            flags = ['jpeg-clip'] if clipped > .01 else []
            patches.append({'label': q['label'], 'name': PHYSICAL_NAMES[i], 'gray': q['label'].startswith('D'),
                            'rgb': q['jpeg_rgb'], 'raw': raw, 'flags': flags, 'roi': q['roi']})
    raw_cam, xyz = [], []
    for q in patches:
        raw = q['raw']
        require(np.isfinite(raw['cam']).all(), 'DNG 色块无效')
        if raw['clip_frac'] > .001:
            q['flags'].append('raw-clip')
        raw_cam.append(raw['cam'])
        xyz.append(ds.xyz(raw['cam'], ds.white_as_shot)[0])
    raw_cam = np.asarray(raw_cam)
    result = {**frame, 'jpeg': str(jpg), 'dng': str(dng), 'meta': meta, 'metadata_errors': errors,
              'hashes': {'JPEG': sha(jpg), 'DNG': sha(dng)}, 'patches': patches,
              'rgb': [q['rgb'] for q in patches], 'raw_cam': raw_cam,
              'raw_wb': raw_cam / np.asarray(meta['asn']), 'xyz_camera': np.asarray(xyz),
              'geometry': geometry, 'raw_jpeg_registration': ds.verify,
              'dng_white': ds.white_as_shot_info}
    dump(cache, result)
    return result


def plain_colour(lab):
    L, a, b = np.asarray(lab)
    c = np.hypot(a, b)
    if c < 7:
        return '黑色' if L < 18 else '深灰' if L < 40 else '白色' if L > 90 else '灰色'
    h = np.degrees(np.arctan2(b, a)) % 360
    names = ('红色', '橙红', '橙黄', '黄色', '黄绿', '绿色', '青绿', '青色', '蓝色', '紫蓝', '紫色', '品红')
    return ('深' if L < 35 else '浅' if L > 75 else '') + names[int((h+15)//30) % 12]


def score_record(engine, targets, frame, baseline):
    require([q['label'] for q in frame['patches']] == [q['label'] for q in baseline['patches']], '色块标签不一致')
    bx, bad = engine.invert04(np.asarray(baseline['rgb']), np.asarray(baseline['raw_wb']))
    ratio = np.asarray(frame['raw_wb']) / np.maximum(np.asarray(baseline['raw_wb']), 1e-9)
    x = bx * ratio
    pred = engine.predict(frame['slot'], x)
    stock_rgb = engine.predict('04', x)
    lab_target, definition = targets.render(frame, baseline, x, stock_rgb)
    base_target, base_definition = targets.render({**baseline, 'slot': frame['slot']}, baseline, bx,
                                   engine.predict('04', bx))
    fs = engine.fs
    observed = fs.lab_from_codes(frame['rgb'])
    de = fs.delta_e00(observed, lab_target)
    base_de = fs.delta_e00(fs.lab_from_codes(baseline['rgb']), base_target)
    model_de = fs.delta_e00(observed, fs.lab_from_codes(pred))
    valid = np.array([not q['flags'] and not b['flags'] for q, b in zip(frame['patches'], baseline['patches'])])
    valid &= ~bad & np.all(np.asarray(baseline['raw_wb']) > 1e-6, axis=1)
    unsupported = sorted(set(definition.get('unsupported_patches', [])) |
                         set(base_definition.get('unsupported_patches', [])))
    valid[unsupported] = False
    for i in np.flatnonzero(bad):
        frame['patches'][i]['flags'].append('04-inverse-out-of-support')
    scene_lab = fs.xyz_to_lab(np.maximum(np.asarray(frame['xyz_camera']), 0))
    h = np.degrees(np.arctan2(scene_lab[:, 2], scene_lab[:, 1])) % 360
    input04_lab = fs.lab_from_codes(stock_rgb)
    sensitivity = []
    if frame['slot'] in ('01', '02'):
        for ev in (-.3, 0., .3):
            factor = 2**ev
            if ev:
                tt, _ = targets.render(frame, baseline, x*factor, engine.predict('04', x*factor), anchor_ev=ev)
                bt, _ = targets.render({**baseline, 'slot': frame['slot']}, baseline,
                                      bx*factor, engine.predict('04', bx*factor), anchor_ev=ev)
            else:
                tt, bt = lab_target, base_target
            sensitivity.append({'anchor_delta_EV': ev, 'de00': fs.delta_e00(observed, tt),
                'baseline_de00': fs.delta_e00(fs.lab_from_codes(baseline['rgb']), bt),
                'model_de00': fs.delta_e00(observed, fs.lab_from_codes(engine.predict(frame['slot'], x*factor))),
                'target_shift_de00': fs.delta_e00(lab_target, tt),
                'model_prediction_shift_de00': fs.delta_e00(fs.lab_from_codes(pred),
                                               fs.lab_from_codes(engine.predict(frame['slot'], x*factor)))})
    frame.update({'input_x': x, 'baseline_input_x': bx, 'target_lab': lab_target, 'baseline_target_lab': base_target,
                  'target_definition': definition, 'model_rgb': pred, 'observed_lab': observed,
                  'de00': de, 'baseline_de00': base_de, 'model_de00': model_de,
                  'valid': valid, 'hue_deg': h, 'scene_lab_unscaled': scene_lab,
                  'input_lightness_Lstar': input04_lab[:, 0],
                  'gr_anchor_sensitivity': sensitivity,
                  'error_map_coordinates': 'hue from own DNG D65 XYZ; lightness from its DNG-driven matched 04 response; not Nominal04',
                  'model': engine.description()})
    return frame


def summarize_slot(frames):
    valid = np.concatenate([np.asarray(f['valid']) for f in frames])
    de = np.concatenate([f['de00'] for f in frames])
    base = np.concatenate([f['baseline_de00'] for f in frames])
    model = np.concatenate([f['model_de00'] for f in frames])
    hues = np.concatenate([f['hue_deg'] for f in frames])
    lightness = np.concatenate([f['input_lightness_Lstar'] for f in frames])
    patches = [(f, i, q) for f in frames for i, q in enumerate(f['patches'])]
    chromatic = valid & ~np.array([q['gray'] for _, _, q in patches])
    worst = []
    for k in np.flatnonzero(valid)[np.argsort(de[valid])[::-1][:8]]:
        f, i, q = patches[k]
        name = q['name'] if f['chart'] == 'physical' else plain_colour(f['scene_lab_unscaled'][i])
        worst.append({'frame': f['id'], 'patch': q['label'], 'colour': name, 'de00': float(de[k])})
    result = {'frames': [f['id'] for f in frames], 'measured_vs_target': stats(de[valid]),
            'all_patches_including_flagged': stats(de), 'model_vs_measured': stats(model[valid]),
            'similarity': similarity(de[valid], base[valid]), 'excluded_patches': int((~valid).sum()),
            'per_hue': [{'hue_start_deg': i*15, **stats(de[chromatic & (hues >= i*15) & (hues < (i+1)*15)]),
                         'model_vs_measured': stats(model[chromatic & (hues >= i*15) & (hues < (i+1)*15)])}
                        for i in range(24)], 'worst_colours': worst,
            'per_lightness': [{'Lstar_start': l, 'measured_vs_target': stats(de[valid & (lightness >= l) & (lightness < l+10)]),
                              'model_vs_measured': stats(model[valid & (lightness >= l) & (lightness < l+10)])}
                             for l in range(0, 100, 10)],
            'model_error_by_hue_lightness': [
                {'hue_start_deg': i*15, 'Lstar_start': l,
                 **stats(model[chromatic & (hues >= i*15) & (hues < (i+1)*15) & (lightness >= l) & (lightness < l+10)])}
                for l in range(0, 100, 10) for i in range(24)],
            'target_kinds': sorted({f['target_definition']['kind'] for f in frames})}
    if frames[0]['slot'] in ('01', '02'):
        rows = []
        for j, ev in enumerate((-.3, 0., .3)):
            def gather(key):
                return np.concatenate([f['gr_anchor_sensitivity'][j][key] for f in frames])[valid]
            dd, bb = gather('de00'), gather('baseline_de00')
            rows.append({'anchor_delta_EV': ev, 'measured_vs_target': stats(dd),
                         'model_vs_measured': stats(gather('model_de00')), 'similarity': similarity(dd, bb),
                         'target_shift_vs_current': stats(gather('target_shift_de00')),
                         'model_prediction_shift_vs_current': stats(gather('model_prediction_shift_de00'))})
        result['gr_anchor_sensitivity'] = {'default_delta_EV': 0., 'best_anchor_selected': False,
            'definition': 'multiply own DNG linear input by 2**EV before target and model rendering; measured JPEG fixed',
            'is_confidence_interval': False, 'rows': rows}
    return result


def write_hue_map(path, slots, model_error=False):
    """An exportable numeric hue heatmap; absent bins remain blank."""
    from xml.sax.saxutils import escape
    width, height = 1230, 70+70*len(slots)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<text x="10" y="22" font-family="sans-serif" font-size="14">'
             + ('Camera versus deployed-table model' if model_error else 'Camera versus target')
             + '; median ΔE00 by DNG scene hue; grey patches excluded</text>']
    for j in range(24):
        parts.append(f'<text x="{78+j*47}" y="48" font-family="sans-serif" font-size="11">{j*15}°</text>')
    for i, (slot, summary) in enumerate(slots.items()):
        y = 58+70*i
        parts.append(f'<text x="10" y="{y+26}" font-family="sans-serif" font-size="14">{escape(slot)}</text>')
        for j, q in enumerate(summary['per_hue']):
            if model_error:
                q = q['model_vs_measured']
            value = q['median']
            if value is None:
                fill, label = '#eeeeee', '—'
            else:
                t = min(value/8, 1.)
                fill = f'rgb({int(70+170*t)},{int(190-130*t)},80)'
                label = f'{value:.2f}'
            x = 72+j*47
            parts += [f'<rect x="{x}" y="{y}" width="45" height="43" fill="{fill}"/>',
                      f'<text x="{x+3}" y="{y+18}" font-family="sans-serif" font-size="11">{label}</text>',
                      f'<text x="{x+3}" y="{y+35}" font-family="sans-serif" font-size="9">n={q["n"]}</text>']
    parts.append('</svg>')
    output_path(path).write_text('\n'.join(parts)+'\n')


def write_model_hue_lightness_map(path, summary):
    width, height = 1230, 480
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<text x="10" y="22" font-family="sans-serif" font-size="14">Camera versus deployed-table model: median ΔE00; DNG hue / matched 04 lightness; blank means no valid sample</text>']
    for j in range(24):
        parts.append(f'<text x="{78+j*47}" y="48" font-family="sans-serif" font-size="11">{j*15}°</text>')
    for i, q in enumerate(summary['model_error_by_hue_lightness']):
        col, row = i % 24, i // 24
        x, y = 72+col*47, 58+row*40
        if col == 0:
            parts.append(f'<text x="3" y="{y+22}" font-family="sans-serif" font-size="11">L {q["Lstar_start"]}–{q["Lstar_start"]+10}</text>')
        value = q['median']
        if value is None:
            fill, label = '#eee', ''
        else:
            t = min(value/8, 1.)
            fill = f'rgb({int(70+170*t)},{int(190-130*t)},80)'; label = f'{value:.2f}'
        parts += [f'<rect x="{x}" y="{y}" width="45" height="38" fill="{fill}"/>',
                  f'<text x="{x+3}" y="{y+16}" font-family="sans-serif" font-size="11">{label}</text>',
                  f'<text x="{x+3}" y="{y+31}" font-family="sans-serif" font-size="9">n={q["n"]}</text>']
    parts.append('</svg>')
    output_path(path).write_text('\n'.join(parts)+'\n')


def run(manifest_path, output, overrides=None, diagnostic=False):
    mount_guard()
    output = output_path(output)
    p = Provenance()
    manifest = read(p.add(manifest_path))
    specs = validate_manifest(manifest)
    diagnostic = diagnostic or manifest.get('diagnostic_only', False)
    frames, seed_by_set = [], {}
    # Extract controls first so the blurred-frame locator can use an observed 04 homography.
    for spec in sorted(specs, key=lambda f: f['slot'] != '04'):
        f = extract(spec, p, seed_by_set.get(spec['set']))
        if spec['chart'] == 'hue-ring' and spec['slot'] == '04':
            seed_by_set[spec['set']] = f['geometry']['H']
        frames.append(f)
        print(f'已提取 {f["id"]}，{len(f["patches"])} 块。', flush=True)
    index = {f['id']: f for f in frames}
    checks = {s: metadata_checks([f for f in frames if f['set'] == s]) for s in sorted({f['set'] for f in frames})}
    engines, targets = {}, {}
    for f in frames:
        path = input_path(f.get('table', manifest.get('table', str(DEFAULT_TABLE))))
        if manifest.get('table_sha256') and not f.get('table'):
            require(sha(path) == manifest['table_sha256'], 'DAT SHA-256 与拍摄清单不符')
        key = str(path), f['meta']['iso']
        if key not in engines:
            engines[key] = Engine(path, f['meta']['iso'], p)
            targets[key] = Targets(engines[key], p, overrides)
        engine = engines[key]
        score_record(engine, targets[key], f, index[f['baseline']])
        f['measurement_valid'] = checks[f['set']]['pass'] and engine.calibrated_iso and not diagnostic
        f['target_measurement_valid'] = checks[f['set']]['pass'] and not diagnostic
        f['eligible_for_refit'] = f['measurement_valid'] and f['meta']['iso'] == 200
        f['iso_status'] = 'ISO 800 未标定' if f['meta']['iso'] == 800 else (
            '已标定' if engine.calibrated_iso else '未标定')
    grouped = {slot: summarize_slot([f for f in frames if f['slot'] == slot])
               for slot in sorted({f['slot'] for f in frames})}
    result = {'schema': 'closedloop-measurement/1', 'diagnostic_only': diagnostic,
              'evidence_kind': manifest.get('evidence_kind', 'camera'),
              'eligible_for_refit': all(f['eligible_for_refit'] for f in frames),
              'eligible_refit_sets': sorted(s for s in checks if all(
                  f['eligible_for_refit'] for f in frames if f['set'] == s)),
              'original_camera_95_percent_proven': False,
              'metadata_checks': checks, 'slots': grouped, 'frames': frames,
              'model_validation_scope': 'synthetic DNG/JPEG only; no camera evidence'
                   if manifest.get('evidence_kind') == 'synthetic' else
                   'historical diagnostic versus selected DAT; not deployed-table camera acceptance'
                   if diagnostic else 'measured camera response versus manifest DAT prediction',
              'note': 'similarity 是相对 04 的误差改善率，不是原机相似度百分比。04 模型检查受 04 反算条件限制。',
              'provenance': p.finish()}
    result['sets'] = {s: {slot: summarize_slot([f for f in frames if f['set'] == s and f['slot'] == slot])
                         for slot in sorted({f['slot'] for f in frames if f['set'] == s})}
                      for s in sorted(checks)}
    dump(output, result)
    write_hue_map(output.with_name(output.stem+'_hue_map.svg'), grouped)
    write_hue_map(output.with_name(output.stem+'_model_hue_map.svg'), grouped, model_error=True)
    for slot, summary_slot in grouped.items():
        write_model_hue_lightness_map(output.with_name(output.stem+f'_slot{slot}_model_hue_lightness.svg'), summary_slot)
    request_pairs = {(f['id'], f['slot']) for f in frames}
    request_pairs |= {(f['baseline'], f['slot']) for f in frames}
    requests = {'schema': 'closedloop-target-requests/1', 'frames': [
        {'id': fid, 'slot': slot, 'key': fid+':'+slot, 'dng_sha256': index[fid]['hashes']['DNG'],
         'labels': [q['label'] for q in index[fid]['patches']], 'chart': index[fid]['chart'],
         'raw_wb': index[fid]['raw_wb'], 'input_x': index[fid]['input_x'], 'xyz_camera': index[fid]['xyz_camera'],
         'required_anchor_EV': [-.3, 0., .3] if slot in ('01', '02') else [0.],
         'baseline_id': index[fid]['baseline']} for fid, slot in sorted(request_pairs)]}
    dump(output.with_name(output.stem + '_target_requests.json'), requests)
    summary = output.with_suffix('.md')
    lines = ['测量结果', '', '状态：' + ('可供回拟审核。' if result['eligible_for_refit'] else '仅诊断，不能用于接受候选。'),
             '', result['note'], '', '| 槽位 | 有效色块 | 相机到目标 ΔE00 中位 / p90 / 最大 | 小于 1 / 2 / 3 | 相机到模型 ΔE00 中位 / p90 / 最大 | 相对改善率 |',
             '|---|---:|---|---|---|---:|']
    for slot, s in grouped.items():
        a = s['measured_vs_target']; sim = s['similarity']['value']
        vals = ' / '.join(f'{a[k]:.3f}' if a[k] is not None else '无' for k in ('median', 'p90', 'max'))
        md = s['model_vs_measured']
        model_vals = ' / '.join(f'{md[k]:.3f}' if md[k] is not None else '无' for k in ('median', 'p90', 'max'))
        shares = ' / '.join(f'{100*a[f"share_under_{k}"]:.1f}%' if a[f'share_under_{k}'] is not None else '无' for k in (1, 2, 3))
        lines.append(f'| {slot} | {a["n"]} | {vals} | {shares} | {model_vals} | '
                     + (f'{100*sim:.1f}%' if sim is not None else '不定义') + ' |')
    if any(slot in grouped for slot in ('01', '02')):
        lines += ['', 'GR 锚点敏感度。默认始终为 0 EV，没有选择误差最小的锚点；这些不是置信区间。', '',
                  '| 槽位 | 锚点变化 EV | 相机到目标中位 / p90 | 相机到模型中位 | 相对改善率 |',
                  '|---|---:|---|---:|---:|']
        for slot in ('01', '02'):
            if slot not in grouped:
                continue
            for r in grouped[slot]['gr_anchor_sensitivity']['rows']:
                de, md = r['measured_vs_target'], r['model_vs_measured']
                sim = r['similarity']['value']
                if de['median'] is not None:
                    lines.append(f'| {slot} | {r["anchor_delta_EV"]:+.1f} | {de["median"]:.3f} / {de["p90"]:.3f} | '
                                 f'{md["median"]:.3f} | '+(f'{100*sim:.1f}%' if sim is not None else '不定义')+' |')
    lines += ['', '误差图', '', f'- [目标误差按色相]({output.stem}_hue_map.svg)。',
              f'- [模型误差按色相]({output.stem}_model_hue_map.svg)。']
    lines += [f'- [槽位 {slot} 的模型误差按色相和明度]({output.stem}_slot{slot}_model_hue_lightness.svg)。' for slot in grouped]
    lines += ['', '最大误差的颜色', '']
    for slot, s in grouped.items():
        worst = '、'.join(f'{q["colour"]} {q["de00"]:.2f}' for q in s['worst_colours'][:3])
        lines.append(f'- {slot}：{worst if worst else "无有效色块"}。')
    lines += ['', '拍摄条件检查', ''] + [e for c in checks.values() for e in c['errors']+c['warnings']]
    lines += [w for f in frames for w in f['geometry'].get('orientation_checks', {}).get('warnings', [])]
    summary.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'output': str(output), 'eligible_for_refit': result['eligible_for_refit'],
                      'frames': len(frames), 'slots': list(grouped)}, ensure_ascii=False))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest', help='closedloop-frames/1 JSON')
    ap.add_argument('--out', default=str(LOCAL / 'measurement.json'))
    ap.add_argument('--targets', help='closedloop-targets/1 JSON，供 GR round5 等生成器回填')
    ap.add_argument('--diagnostic', action='store_true', help='保留无效拍摄诊断，禁止用于回拟接受')
    a = ap.parse_args()
    result = run(a.manifest, a.out, a.targets, a.diagnostic)
    return 0 if result['eligible_for_refit'] else 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print(f'测量失败：{exc}', file=sys.stderr)
        sys.exit(1)
