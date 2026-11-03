#!/usr/bin/env python3
"""Analyze 04a,07,04b or 04a,07,04b,08,04c JPEG+DNG pairs, host only."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sp = importlib.util.spec_from_file_location('t3_model', Path(__file__).with_name('model_t3.py'))
m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
p = m.p
import numpy as np


def output_path(path=None):
    path = Path(path or p.LOCAL / 'analysis/latest').resolve()
    p.require(path.is_relative_to(p.LOCAL.resolve()), 'Analysis output must be below research/t3_probe/local/')
    p.ignored(path / 'verdict.json')
    return path


def equivalent_groups(predictions, mask):
    groups = []
    for key, value in predictions.items():
        for group in groups:
            if np.allclose(value[mask], predictions[group[0]][mask], atol=1e-9, rtol=0):
                group.append(key)
                break
        else:
            groups.append([key])
    return groups


def score_arrays(engine, a, probe, b, predictions, weights, checks=None, fraction=.5):
    a, probe, b = [np.asarray(x, float) for x in (a, probe, b)]
    p.require(a.shape == probe.shape == b.shape == (155, 3) and
              all(np.isfinite(v).all() for v in (a, probe, b)), 'Expected finite 155×3 RGB arrays')
    base = (1 - fraction) * a + fraction * b
    delta, repeat = probe - base, b - a
    affected = engine.ring & (weights[:, list(m.SECTORS)].sum(1) >= .1)
    controls = engine.ring & (weights[:, list(m.SECTORS)].sum(1) < 1e-6)
    grey_max = float(abs(repeat[engine.grey]).max())
    calibration_frames = m.calibration()
    cal_repeat = calibration_frames[1]['rgb'] - calibration_frames[0]['rgb']
    restore_rms, cal_rms = m.rms(repeat[engine.ring]), m.rms(cal_repeat[engine.ring])
    return_sectors = {}
    for sec in m.SECTORS:
        mask = engine.ring & (weights[:, sec] >= .1)
        measured = m.rms(repeat[mask])
        limit = max(2., 2 * m.rms(cal_repeat[mask]))
        return_sectors[str(sec)] = {'pass': measured <= limit, 'RMS_codes': measured, 'limit_codes': limit}
    restored = (grey_max <= max(2., 3 * float(abs(cal_repeat[engine.grey]).max())) and
                restore_rms <= max(2., 2.5 * cal_rms) and all(r['pass'] for r in return_sectors.values()))
    control_rms = m.rms(delta[controls])
    control_limit = max(2., 2 * m.rms(repeat[controls]), 2 * m.rms(cal_repeat[controls]))
    controls_ok = control_rms <= control_limit
    metadata_ok = checks is None or checks['pass']
    quality_ok = restored and controls_ok and metadata_ok
    sectors = {}
    for s in m.SECTORS:
        mask = engine.ring & (weights[:, s] >= .1)
        noise = max(m.rms(repeat[mask]), m.rms(cal_repeat[mask]), .4)
        groups = equivalent_groups(predictions, mask)
        scores = [{'hypotheses': group, 'residual_RMS_codes': m.rms((delta - predictions[group[0]])[mask])}
                  for group in groups]
        scores.sort(key=lambda x: x['residual_RMS_codes'])
        best = scores[0]
        second = scores[1]
        # A hue ray is one unit even when it occurs in both L* rings.
        rays = len({engine.layout['patches'][i]['hue_index'] for i in np.where(mask)[0]})
        fixed_gap = second['residual_RMS_codes'] - best['residual_RMS_codes']
        fixed_threshold = max(.3, noise / np.sqrt(max(rays, 1)))
        fits = []
        for key in ('H1', 'H2_transpose', 'H2_swap_axes', 'H2_swap_outputs', 'H2_diagonal_swap'):
            x, y = predictions[key][mask], delta[mask]
            denominator = float(np.sum(x * x))
            alpha = float(np.sum(x * y) / denominator) if denominator > 0 else 0.
            signal = m.rms(x)
            resolution = max(.05, noise / max(signal * np.sqrt(max(rays, 1)), .1))
            fits.append({'layout': key, 'scale': alpha, 'scale_resolution': resolution,
                         'residual_RMS_codes': m.rms(y - alpha * x)})
        candidate = fits[0]
        measured_de = engine.delta_e(np.clip(probe, 0, 255), np.clip(base, 0, 255))
        threshold = max(2., 2 * noise)
        selected = best['hypotheses'][:]
        status = 'compatible' if fixed_gap >= fixed_threshold else 'weak_separation'
        # A scale between the discrete half/one/double examples is also reportable.
        # This resolution is a heuristic from two 04 frames, not a confidence interval.
        if (candidate['residual_RMS_codes'] + fixed_threshold < best['residual_RMS_codes'] and
                abs(candidate['scale']) > 2 * candidate['scale_resolution'] and
                abs(candidate['scale'] - 1) > 2 * candidate['scale_resolution']):
            selected = ['H3_fitted_scale']
            status = 'compatible'
        if best['residual_RMS_codes'] > threshold and candidate['residual_RMS_codes'] > threshold:
            status = 'out_of_family'
        elif not quality_ok:
            status = 'abnormal'
        elif selected == ['H0']:
            status = 'no_effect'
        sectors[str(s)] = {'status': status, 'hypotheses': selected,
                           'best_fixed_hypotheses': best['hypotheses'],
                           'best_residual_RMS_codes': best['residual_RMS_codes'],
                           'next_residual_RMS_codes': second['residual_RMS_codes'],
                           'margin_codes': fixed_gap, 'required_margin_codes': fixed_threshold,
                           'measured_RMS_codes': m.rms(delta[mask]),
                           'measured_peak_de00': float(measured_de[mask].max()),
                           'measured_median_de00': float(np.median(measured_de[mask])),
                           'repeat_RMS_codes': m.rms(repeat[mask]), 'noise_floor_codes': noise,
                           'ring_patches': int(mask.sum()), 'distinct_hue_rays': rays,
                           'candidate_scale_fit': candidate, 'layout_scale_fits': fits, 'scores': scores}
    joint_scores = [{'hypothesis': key, 'residual_RMS_codes': m.rms((delta - value)[affected])}
                    for key, value in predictions.items()]
    joint_scores.sort(key=lambda x: x['residual_RMS_codes'])
    joint_best, joint_second = joint_scores[:2]
    joint_noise = max(m.rms(repeat[affected]), m.rms(cal_repeat[affected]), .4)
    joint_rays = len({engine.layout['patches'][i]['hue_index'] for i in np.where(affected)[0]})
    joint_gap = joint_second['residual_RMS_codes'] - joint_best['residual_RMS_codes']
    joint_separated = joint_gap >= max(.3, joint_noise / np.sqrt(joint_rays))
    if not quality_ok:
        result = 'abnormal'
    elif any(r['status'] == 'out_of_family' for r in sectors.values()):
        result = 'out_of_family'
    elif joint_best['hypothesis'] == 'H0' and all(r['status'] == 'no_effect' for r in sectors.values()):
        result = 'no_effect'
    elif joint_separated and all(r['status'] in ('compatible', 'weak_separation') for r in sectors.values()):
        result = 'compatible'
    else:
        result = 'not_identified'
    return {'schema': 'gxr-t3-verdict-1', 'result': result, 'sectors': sectors,
            'joint_best': joint_best, 'joint_second': joint_second, 'joint_margin_codes': joint_gap,
            'joint_separation_pass': joint_separated, 'joint_scores': joint_scores,
            '04_restore': {'pass': restored, 'grey_max_abs_codes': grey_max,
                           'ring_RMS_codes': restore_rms, 'calibration_ring_RMS_codes': cal_rms,
                           'sector_returns': return_sectors},
            'control_patches': {'pass': controls_ok, 'count': int(controls.sum()),
                                'RMS_codes': control_rms, 'limit_codes': control_limit},
            'metadata_checks': checks, 'baseline_fraction': fraction,
            'scope': 'Compatibility with a candidate host model; no physical byte semantics proven',
            'scale_resolution_note': 'Two-frame heuristic with hue-ray grouping, not a statistical confidence interval',
            'delta_07_minus_interpolated_04': delta}


def summary(verdict):
    names = {'compatible': '符合候选模型', 'no_effect': '未测到效果', 'not_identified': '未区分',
             'out_of_family': '超出候选模型', 'abnormal': '输入或恢复异常', 'weak_separation': '区分较弱'}
    if 'error' in verdict:
        return f"结果：异常。{verdict['error']}\n"
    lines = [f"T3 结果：{names[verdict['result']]}。"]
    for sector, r in verdict['sectors'].items():
        lines.append(f"扇区 {sector}：{names[r['status']]}，{' / '.join(r['hypotheses'])}；"
                     f"实测 RGB RMS {r['measured_RMS_codes']:.2f} 码，峰值 {r['measured_peak_de00']:.2f} ΔE00；"
                     f"按 H1 拟合尺度 {r['candidate_scale_fit']['scale']:.2f}。")
    lines.append(f"联合最佳 {verdict['joint_best']['hypothesis']}，残差 {verdict['joint_best']['residual_RMS_codes']:.2f} 码。")
    if 'H1' in verdict['sectors']['11']['best_fixed_hypotheses']:
        lines.append('扇区 11 的 d 在 H1 与转置布局下完全等价，需结合扇区 17 判读。')
    if not verdict['04_restore']['pass']:
        lines.append('04b 未回到允许的重复性范围，不能验收效果。')
    if not verdict['control_patches']['pass']:
        lines.append('未改扇区也发生过大变化，不能用本探针的局部模型解释。')
    for warning in verdict.get('warnings', []):
        lines.append('提示：' + warning)
    if 'probe2' in verdict:
        lines.append('08 已交给现有 probe2 分析器：' + verdict['probe2']['result_zh'] + '。')
    return '\n'.join(lines) + '\n'


def frame_checks(frames, old, engine):
    checks = old.metadata_checks(frames)
    raw = [np.array(f['cam_wb']) for f in frames]
    drifts = []
    for i in range(1, len(frames)):
        drift = np.median(np.log2(np.maximum(raw[i][engine.grey], 1e-8) /
                                  np.maximum(raw[0][engine.grey], 1e-8)), axis=0)
        drifts.append({'frame': i + 1, 'median_channel_EV': drift})
        if np.max(abs(drift)) > .03:
            checks['errors'].append(f'Frame {i+1}: grey RAW exposure/WB drift exceeds 0.03 EV')
    checks['raw_drifts'] = drifts
    checks['pass'] = not checks['errors']
    return checks


def analyze(paths, output=None, engine=None):
    p.require(len(paths) in (3, 5), 'Use 04a,07,04b or 04a,07,04b,08,04c')
    paths = [p.check_input(q) for q in paths]
    for path in paths:
        for suffix in ('.DNG', '.dng'):
            p.check_input(path.with_suffix(suffix))
    output = output_path(output)
    old = p.legacy_analyzer()
    ar = engine.ar if engine else p.load('t3_ring_extractor', p.ROOT / 'research/hue_ring/analyze_ring.py')
    layout = ar.load_layout()
    first = old.extract(paths[0], ar, layout)
    frames = [first] + [old.extract(q, ar, layout, np.array(first['H'])) for q in paths[1:]]
    engine = engine or m.Engine(frames[0]['meta']['display'])
    checks = frame_checks(frames, old, engine)
    rgb = [np.array(f['rgb']) for f in frames]
    raw = [np.array(f['cam_wb']) for f in frames]
    times = [ar.when_seconds(f['meta'], i) for i, f in enumerate(frames[:3])]
    fraction = (times[1] - times[0]) / (times[2] - times[0]) if times[2] > times[0] else .5
    if not 0 <= fraction <= 1:
        fraction = .5
        checks['warnings'].append('时间戳未夹在两张 04 之间，基线按两张 04 的均值计算')
    changes = p.load('t3_analyzer_parameters', p.HERE / 'build_validate.py').CHANGES
    dat = (p.PACKAGE/'DEEPTBL0.DAT').read_bytes()
    current = engine.src.parse(dat, (p.STAGE/'examples/DEEPISP0.DAT').read_bytes())
    stock, colour = engine.stock[2], current[6]['rows'][2]
    expected_offsets = {s*4 + (3 if s == 11 else 2) for s in m.SECTORS}
    p.require({i for i,(x,y) in enumerate(zip(stock,colour)) if x != y} == expected_offsets,
              'Actual 07 colour does not match the two-byte design')
    p.require(all(m.signmag(colour[s*4+(3 if s == 11 else 2)]) -
                  m.signmag(stock[s*4+(3 if s == 11 else 2)]) == changes[s] for s in m.SECTORS),
              'Actual 07 magnitude differs from analyzer parameters')
    p.require(current[6]['mask'] == 0 and current[6]['control'] == 2 and
              current[6]['rows'][:2] == engine.stock[:2] and current[6]['rows'][3:] == engine.stock[3:],
              'Actual 07 has changes outside the two colour bytes')
    pa, _, ca, qa = engine.predict(rgb[0], raw[0], changes)
    pb, _, cb, qb = engine.predict(rgb[2], raw[2], changes)
    predictions = {key: (1-fraction) * pa[key] + fraction * pb[key] for key in pa}
    weights = (1-fraction) * engine.weights(engine.mm.hue_deg(ca)) + fraction * engine.weights(engine.mm.hue_deg(cb))
    verdict = score_arrays(engine, rgb[0], rgb[1], rgb[2], predictions, weights, checks, fraction)
    warnings = list(checks['warnings'])
    bound = json.loads((p.HERE/'bounds_validation.json').read_text())
    if not bound['camera_handoff_ready']:
        warnings.append('当前包未通过联合布局与尺度门槛，只供主机诊断，不适合上机')
    for i, frame in enumerate(frames):
        clipping = frame['clipping_255']
        if clipping['warning']:
            warnings.append(f"第 {i+1} 帧彩块/灰块 {100*clipping['fraction']:.3f}% 像素至少一通道达到 255")
    verdict.update(code_sha256=p.source_manifest([p.HERE/name for name in
                   ('analyze_t3.py','model_t3.py','t3_core.py','build_validate.py')]), inputs=[{k: f[k] for k in ('JPEG', 'DNG', 'hashes')} for f in frames],
                   model_sha256=p.sha(p.MODEL), package_sha256=p.digest(dat),
                   camera_handoff_ready=bound['camera_handoff_ready'], inversion_quality=[qa, qb], warnings=warnings,
                   clipping=[f['clipping_255'] for f in frames], camera_acceptance='pending')
    if len(paths) == 5:
        t1_engine = old.m.Engine(frames[2]['meta']['display'])
        current = engine.src.parse((p.PACKAGE / 'DEEPTBL0.DAT').read_bytes(),
                                   (p.STAGE / 'examples/DEEPISP0.DAT').read_bytes())
        p.require(t1_engine.probe[7] == current[7], 'Existing probe2 analyzer uses different 08 bytes')
        probe2, _ = old.analyze([paths[2], paths[3], paths[4]], output / 'probe2', t1_engine)
        verdict['probe2'] = probe2
        verdict['probe2_delegation'] = 'existing analyze_probe2.py; input 04b,08,04c; all writes redirected to t3_probe/local'
        if not probe2['grey_return_within_2_codes'] or not probe2['metadata_checks']['pass']:
            verdict['result'] = 'abnormal'
    p.dump(output / 'verdict.json', verdict, private=True)
    p.dump(output / 'patches.json', frames, private=True)
    text = summary(verdict)
    p.save(output / 'SUMMARY.txt', text, private=True)
    return verdict, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frames', nargs='+', metavar='JPEG')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    p.preflight()
    output = output_path(args.out)
    try:
        verdict, text = analyze(args.frames, output)
    except (ValueError, KeyError, OSError, SystemExit) as error:
        verdict = {'schema': 'gxr-t3-verdict-1', 'result': 'abnormal', 'error': str(error)}
        p.dump(output / 'verdict.json', verdict, private=True)
        text = summary(verdict)
        p.save(output / 'SUMMARY.txt', text, private=True)
    print(text, end='')
    return 2 if verdict['result'] == 'abnormal' else 0


if __name__ == '__main__':
    sys.exit(main())
