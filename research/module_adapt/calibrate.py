"""Patch interchange, 04 input-residual calibration and analysis-only recipe fitting."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
import support as s
from unit_model import UnitModel


def features(raw_wb, degree=1):
    r, g, b = np.asarray(raw_wb, float).T
    cols = [np.ones(len(r)), r, g, b]
    if degree == 2:
        cols += [r*r, g*g, b*b, r*g, r*b, g*b]
    return np.column_stack(cols)


def apply_calibration(raw_wb, calibration):
    raw_wb = np.asarray(raw_wb, float)
    return 4095*(raw_wb+features(raw_wb, calibration['degree'])@np.asarray(calibration['residual_coefficients']))


def load_exchange(patches, frames, unit, slot='04'):
    meta = s.read(frames)
    assert meta['schema'] == 'ricoh-module-frames/1'
    rows = []
    seen = set()
    for line_no, line in enumerate(s.source(patches).read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        required = {'frame', 'page', 'patch_id', 'class', 'raw_rgb', 'jpeg_rgb', 'valid', 'spatial_sd'}
        assert required <= set(row), f'第 {line_no} 行缺少字段'
        assert type(row['valid']) is bool
        key = (row['frame'], str(row['page']), str(row['patch_id']))
        assert key not in seen, f'重复色块 {key}'
        seen.add(key)
        f = meta['frames'][row['frame']]
        assert {'module', 'iso', 'shutter_s', 'aperture_f', 'white_balance', 'selector_bytes'} <= set(f)
        assert f['module'] in ('50mm', '28mm', 'mount')
        assert f.get('color_space', 'sRGB') == 'sRGB', '必须先转换并记录非 sRGB JPEG'
        if not row['valid']:
            if f['module'] == unit and f['selector_bytes']['recipe_slot'] == slot:
                row.update(meta=f, usable=False)
                rows.append(row)
            continue
        wb = np.asarray(f['white_balance']['gains'], float)
        assert wb.shape == (3,) and np.all(np.isfinite(wb)) and np.all(wb > 0)
        assert int(f['iso']) > 0 and float(f['shutter_s']) > 0 and float(f['aperture_f']) > 0
        for field in ('raw_rgb', 'jpeg_rgb'):
            v = np.asarray(row[field], float)
            assert v.shape == (3,) and np.isfinite(v).all()
        raw, jpeg = np.asarray(row['raw_rgb']), np.asarray(row['jpeg_rgb'])
        assert np.all((raw >= 0) & (raw <= 1)) and np.all((jpeg >= 0) & (jpeg <= 255))
        sd = row['spatial_sd']
        if isinstance(sd, dict):
            assert 'raw_rgb' in sd and 'jpeg_rgb' in sd
            raw_sd = np.asarray(sd['raw_rgb'], float)
            jpeg_sd = np.asarray(sd['jpeg_rgb'], float)
            assert raw_sd.shape == jpeg_sd.shape == (3,)
        else:
            jpeg_sd = np.broadcast_to(np.asarray(sd, float), (3,))
            raw_sd = np.zeros(3)
        assert np.isfinite(raw_sd).all() and np.isfinite(jpeg_sd).all()
        assert np.all(raw_sd >= 0) and np.all(jpeg_sd >= 0)
        if f['module'] != unit or f['selector_bytes']['recipe_slot'] != slot:
            continue
        row.update(meta=f, raw_wb=raw*wb, raw_sd=raw_sd, jpeg_sd=jpeg_sd)
        row['usable'] = row['valid'] and bool(np.all(raw < .98) and np.all((jpeg > 1) & (jpeg < 254)))
        row['usable'] &= bool(np.max(raw_sd) <= .025 and np.max(jpeg_sd) <= 10)
        rows.append(row)
    assert rows, '没有对应单元和配方的色块'
    return rows, meta


def fit04(model, rows, degree=1, holdout_page=None):
    all_good = [r for r in rows if r['usable']]
    parameter_names = ('contrast', 'sharpness', 'vividness', 'orange_saturation', 'green_saturation',
                       'blue_saturation', 'red_saturation', 'magenta_saturation',
                       'orange_hue', 'green_hue', 'blue_hue', 'red_hue', 'magenta_hue')
    display_to_raw = (7, 6, 1, 2, 3, 4, 5, 8, 9)
    expected_raw = [display_to_raw[model.display[k]-1] for k in parameter_names]
    for r in all_good:
        selectors = r['meta']['selector_bytes']
        assert selectors.get('image_setting') == 1 and selectors.get('type26_control') == 2, '04 必须为 Standard，control=2'
        assert selectors.get('raw13') == expected_raw, '选择器字节与模型滑块状态不符，需要针对性建模'
    assert len({r['meta']['iso'] for r in all_good}) == 1, '每个 ISO 单独标定'
    assert all(r['meta']['iso'] == model.base.iso for r in all_good)
    assert all(r['meta']['white_balance']['mode'].lower() in ('manual', 'ct', 'custom') for r in all_good), '必须固定手动 WB'
    if model.unit == 'mount':
        lens_keys = {(r['meta'].get('lens_id'), r['meta']['aperture_f'],
                      json.dumps(r['meta'].get('corrections', {}), sort_keys=True)) for r in all_good}
        assert len(lens_keys) == 1 and next(iter(lens_keys))[0], 'Mount 必须指定同一镜头、光圈和校正状态'
    pages = sorted({str(r['page']) for r in all_good})
    holdout_page = str(holdout_page) if holdout_page is not None else pages[-1] if len(pages) > 1 else None
    held = np.array([str(r['page']) == holdout_page if holdout_page is not None else
                     int(hashlib.sha256(str(r['patch_id']).encode()).hexdigest()[:8], 16) % 5 == 0 for r in all_good])
    assert np.any(held) and (~held).sum() >= (30 if degree == 1 else 60), '训练或留出色块不足'
    raw = np.array([r['raw_wb'] for r in all_good])
    jpeg = np.array([r['jpeg_rgb'] for r in all_good])
    latent, bad = model.inverse04(jpeg, raw)
    train = ~held & ~bad
    valid = held & ~bad
    assert train.sum() >= (30 if degree == 1 else 60) and valid.sum() >= 8
    H = features(raw, degree)
    assert np.linalg.matrix_rank(H[train]) == H.shape[1], '色块没有覆盖可辨识的颜色范围'
    # Spatial SD is a weight, not a claim about standard error or independent pixels.
    w = 1/np.sqrt(1+np.array([np.mean(r['jpeg_sd']**2) for r in all_good]))
    target = latent/4095-raw
    ridge = 1e-9
    C = np.linalg.lstsq(np.vstack([H[train]*w[train, None], np.eye(H.shape[1])*ridge]),
                        np.vstack([target[train]*w[train, None], np.zeros((H.shape[1], 3))]), rcond=None)[0]
    # Some stock hue maps have multiple valid inverse roots. Resolve the shared
    # input mapping by replaying actual 04 outputs, not by treating one root as truth.
    def forward_residual(flat):
        candidate = 4095*(raw[train]+H[train]@flat.reshape(C.shape))
        pred = model.predict('04', candidate)
        return ((pred-jpeg[train])*w[train, None]).ravel()
    opt = least_squares(forward_residual, C.ravel(), max_nfev=50,
                        ftol=1e-11, xtol=1e-11, gtol=1e-11)
    C = opt.x.reshape(C.shape)
    calibration = {'schema': 'ricoh-unit-calibration/1', 'module': model.unit, 'iso': model.base.iso,
                   'degree': degree, 'residual_coefficients': C.tolist(),
                   'residual_location': 'native RAW after black/white normalization and metadata WB, before type-26',
                   'response_kernel_source': 'borrowed 50mm; not identifiable from 04 alone',
                   'source_kind': sorted({r['meta'].get('source_kind', 'camera') for r in all_good}),
                   'holdout_page': holdout_page, 'n_train': int(train.sum()), 'n_holdout': int(valid.sum()),
                   'solver_success': bool(opt.success), 'solver_nfev': opt.nfev,
                   'n_rejected_initial': len(rows)-len(all_good), 'n_rejected_inverse': int(bad.sum()),
                   'table_sha256': s.digest(s.DAILY), 'lens_id': all_good[0]['meta'].get('lens_id'),
                   'selector_bytes_04': all_good[0]['meta']['selector_bytes'],
                   'aperture_f': all_good[0]['meta']['aperture_f'],
                   'corrections': all_good[0]['meta'].get('corrections', {}),
                   'camera_acceptance': False, 'firmware_ready': False}
    corrected = apply_calibration(raw, calibration)
    for label, selected in (('train', train), ('holdout', valid)):
        calibration[label] = {'uncorrected_de00': s.stats(model.de(model.predict('04', raw[selected]*4095), jpeg[selected])),
                              'corrected_de00': s.stats(model.de(model.predict('04', corrected[selected]), jpeg[selected])),
                              'inverse_root_conditioned_rmse_12bit': float(np.sqrt(np.mean((corrected[selected]-latent[selected])**2)))}
    calibration['input_condition_number'] = float(np.linalg.cond(H[train]))
    calibration['raw_wb_min'] = raw[train].min(axis=0).tolist()
    calibration['raw_wb_max'] = raw[train].max(axis=0).tolist()
    return calibration


def recipe_fit(model, slot, x, target_lab, train=None, max_nfev=45, bias_rgb=None):
    """Fit Y plus symmetric sectors; retain this recipe's curve and T1 channels."""
    x, target_lab = np.asarray(x, float), np.asarray(target_lab, float)
    train = np.ones(len(x), bool) if train is None else np.asarray(train, bool)
    row, A, B = model.parameters(slot)
    pre = model.pre(slot, x)
    y, ci = row.apply(pre)
    nvar = 2 if slot == '03' else 50
    J = np.zeros((len(x), 3, nvar))
    J[:, :, 0] = ((pre[:, 0]-pre[:, 1])/1024)[:, None]
    J[:, :, 1] = ((pre[:, 2]-pre[:, 1])/1024)[:, None]
    if slot != '03':
        W = model.table.kernel_weights(model.mm.hue_deg(ci), abs(ci))*model.table.gain
        dc = ci[:, None]*W/32
        for start, response in ((2, dc), (26, 1j*dc)):
            J[:, 0, start:start+24] = 1.402*response.imag
            J[:, 1, start:start+24] = -.344136*response.real-.714136*response.imag
            J[:, 2, start:start+24] = 1.772*response.real
    bias_rgb = np.zeros((len(x), 3)) if bias_rgb is None else np.asarray(bias_rgb, float)
    assert bias_rgb.shape == (len(x), 3) and np.isfinite(bias_rgb).all()
    initial_rgb = model.predict(slot, x, unclipped=True)+bias_rgb

    def rgb(p):
        return np.clip(initial_rgb+np.einsum('ncv,v->nc', J, p), 0, 255)

    def residual(p):
        r = model.fs.de00_components(model.fs.lab_from_codes(rgb(p)[train]), target_lab[train]).ravel()
        regularizers = [.004*p[:2]]
        if slot != '03':
            colors = p[2:].reshape(2, 24)
            regularizers += [.025*p[2:], .05*(colors-np.roll(colors, 1, axis=1)).ravel()]
        return np.r_[r, *regularizers]

    bounds = np.r_[np.full(2, 192.), np.full(nvar-2, 96.)]
    opt = least_squares(residual, np.zeros(nvar), bounds=(-bounds, bounds), max_nfev=max_nfev,
                        ftol=1e-7, xtol=1e-7, gtol=1e-7)
    coef = row.coef.copy()
    dy = np.rint(opt.x[:2]).astype(int)
    coef[0] += [dy[0], -dy.sum(), dy[1]]
    candidate_row = row.copy(coef=coef)
    if slot != '03':
        current_effective = model.effective(A, B)
        z = current_effective/model.stock_effective
        T = model.stock_effective*(abs(z)*np.exp(1j*model.table.k*np.angle(z)))
        T += (opt.x[2:26]+1j*opt.x[26:50])/32
        eff_z = T/model.stock_effective
        new_z = abs(eff_z)*np.exp(1j*np.angle(eff_z)/model.table.k)
        physical = new_z*model.stock_effective*32
        newA = np.rint((physical.real-model.d0)*100/model.sat).astype(int)
        newB = np.rint(-physical.imag*100/model.sat-model.d1).astype(int)
        bounded = bool(np.all(abs(newA) <= 127) and np.all(abs(newB) <= 127))
        newA, newB = np.clip(newA, -127, 127), np.clip(newB, -127, 127)
    else:
        newA, newB, bounded = A, B, True
    candidate = np.clip(model.predict(slot, x, candidate_row, newA, newB, unclipped=True)+bias_rgb, 0, 255)
    actual_error = model.fs.delta_e00(model.fs.lab_from_codes(candidate), target_lab)
    before_error = model.fs.delta_e00(model.fs.lab_from_codes(np.clip(initial_rgb, 0, 255)), target_lab)
    gray = np.repeat(np.geomspace(8., 3500., 129)[:, None], 3, axis=1)
    neutral = model.fs.lab_from_codes(model.predict(slot, gray, candidate_row, newA, newB))
    artifact = {'schema': 'ricoh-module-recipe-analysis/1', 'module': model.unit, 'slot': slot,
                'matrix_row1_q10': coef.tolist(), 'matrix_tail': list(row.tail),
                'colour_A': newA.tolist(), 'colour_B': newB.tolist(),
                'curves_and_T1_retained_from_daily_sha256': s.digest(s.DAILY),
                'solver_success': bool(opt.success), 'solver_message': opt.message, 'nfev': opt.nfev,
                'checks': {'coefficients_bounded_before_clipping': bounded,
                           'matrix_valid': not candidate_row.violations(row),
                           'Y_row_sum_preserved': bool(coef[0].sum() == row.coef[0].sum()),
                           'neutral_L_nondecreasing': bool(np.all(np.diff(neutral[:, 0]) >= -1e-8))},
                'n_train': int(train.sum()), 'n_holdout': int((~train).sum()),
                'train_before': s.stats(before_error[train]), 'train_after': s.stats(actual_error[train]),
                'holdout_before': s.stats(before_error[~train]), 'holdout_after': s.stats(actual_error[~train]),
                'deployment_allowed': False, 'firmware_ready': False, 'camera_acceptance': False,
                'limitation': '04-only calibration does not identify recipe response; T1 nodes and row20 are fixed; dense safety and actual recipe capture remain required'}
    return artifact, candidate, actual_error


def prior_bias(prior, x, slot):
    assert prior['schema'] == 'ricoh-recipe-residual-prior/1' and prior['slot'] == slot
    assert prior['module'] == '50mm' and prior['source_kind'] == ['camera'], '只借用明确标记的 50mm 实拍先验'
    assert prior['table_sha256'] == s.digest(s.DAILY), '实拍残差与日用表不匹配'
    knots = np.asarray(prior['input_x'])
    values = np.asarray(prior['bias_rgb'])
    distance, index = cKDTree(np.log2(np.maximum(knots, 1))).query(np.log2(np.maximum(x, 1)), k=min(6, len(knots)))
    if distance.ndim == 1:
        distance, index = distance[:, None], index[:, None]
    weight = 1/np.maximum(distance, .025)**2
    bias = np.sum(values[index]*weight[:, :, None], axis=1)/weight.sum(axis=1)[:, None]
    unsupported = distance[:, 0] > .5
    bias[unsupported] = 0
    return bias, int(unsupported.sum())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--patches', type=Path, required=True)
    common.add_argument('--frames', type=Path, required=True)
    common.add_argument('--unit', choices=['50mm', '28mm', 'mount'], required=True)
    common.add_argument('--iso', type=int, choices=[200, 1600], default=200)
    common.add_argument('--output', type=Path, required=True)
    a = sub.add_parser('fit-04', parents=[common])
    a.add_argument('--degree', type=int, choices=[1, 2], default=1)
    a.add_argument('--holdout-page')
    b = sub.add_parser('fit-recipe', parents=[common])
    b.add_argument('--calibration', type=Path, required=True)
    b.add_argument('--targets', type=Path, required=True)
    b.add_argument('--slot', choices=['01', '02', '03', '05', '06'], required=True)
    b.add_argument('--residual-prior', type=Path)
    c = sub.add_parser('learn-50mm-residual', parents=[common])
    c.add_argument('--calibration', type=Path, required=True)
    c.add_argument('--slot', choices=['01', '02', '03', '05', '06'], required=True)
    args = ap.parse_args()
    s.guard()
    m = UnitModel(args.unit, iso=args.iso)
    rows, meta = load_exchange(args.patches, args.frames, args.unit,
                               args.slot if args.command == 'learn-50mm-residual' else '04')
    if args.command == 'fit-04':
        result = fit04(m, rows, args.degree, args.holdout_page)
    elif args.command == 'learn-50mm-residual':
        assert args.unit == '50mm'
        calibration = s.read(args.calibration)
        assert calibration['module'] == '50mm' and calibration['iso'] == args.iso
        assert calibration['table_sha256'] == s.digest(s.DAILY)
        valid = [r for r in rows if r['usable']]
        assert len(valid) >= 30 and all(r['meta']['iso'] == args.iso for r in valid)
        x = apply_calibration(np.array([r['raw_wb'] for r in valid]), calibration)
        bias = np.array([r['jpeg_rgb'] for r in valid])-m.predict(args.slot, x, unclipped=True)
        result = {'schema': 'ricoh-recipe-residual-prior/1', 'module': '50mm', 'slot': args.slot,
                  'iso': args.iso, 'input_x': x.tolist(), 'bias_rgb': bias.tolist(),
                  'table_sha256': s.digest(s.DAILY),
                  'source_kind': sorted({r['meta'].get('source_kind', 'camera') for r in valid}),
                  'transfer_to_other_modules_is_an_assumption': True, 'camera_acceptance': False,
                  'note': '拟合用同一配方帧自己的 RAW；借到别单元只是先验，不能替代别单元配方实拍'}
    else:
        calibration = s.read(args.calibration)
        assert calibration['module'] == args.unit and calibration['iso'] == args.iso
        assert calibration['table_sha256'] == s.digest(s.DAILY), '日用表已变化，先更新标定'
        targets = s.read(args.targets)
        assert targets['schema'] == 'ricoh-module-targets/1' and targets['whitepoint'] == 'D65' and targets['source']
        index = {(str(q['page']), str(q['patch_id'])): q for q in targets['samples'] if q['slot'] == args.slot}
        valid = [r for r in rows if r['usable'] and (str(r['page']), str(r['patch_id'])) in index]
        assert len(valid) >= 80, '配方拟合至少需要 80 个有效目标点'
        assert all(r['meta']['iso'] == args.iso for r in valid)
        if args.unit == 'mount':
            assert all(r['meta'].get('lens_id') == calibration['lens_id'] and
                       r['meta']['aperture_f'] == calibration['aperture_f'] and
                       r['meta'].get('corrections', {}) == calibration['corrections'] for r in valid), 'Mount 镜头、光圈或校正状态与标定不符'
        raw = np.array([r['raw_wb'] for r in valid])
        x = apply_calibration(raw, calibration)
        target = np.array([index[str(r['page']), str(r['patch_id'])]['target_lab'] for r in valid])
        # Hold out complete 15-degree hue bands, never isolated repeated patches.
        _, ci = m.stock_matrix.apply(m.curve04(x))
        h = np.floor(m.mm.hue_deg(ci)/15).astype(int) % 3
        bias = None
        if args.residual_prior:
            prior = s.read(args.residual_prior)
            assert prior['iso'] == args.iso
            bias, unsupported = prior_bias(prior, x, args.slot)
        result, candidate, err = recipe_fit(m, args.slot, x, target, train=h != 0, bias_rgb=bias)
        if args.residual_prior:
            result['borrowed_50mm_prior_sha256'] = s.digest(args.residual_prior)
            result['prior_unsupported_points'] = unsupported
            result['prior_transfer_is_an_assumption'] = True
        baseline_target = np.array([index[str(r['page']), str(r['patch_id'])].get('baseline_target_lab', target[i]) for i, r in enumerate(valid)])
        base = m.fs.delta_e00(m.fs.lab_from_codes(m.predict('04', x)), baseline_target)
        result['holdout_similarity'] = s.similarity(err[h == 0], base[h == 0])
        result['target_source'] = targets['source']
        result['calibration_sha256'] = s.digest(args.calibration)
        lo, hi = np.array(calibration['raw_wb_min']), np.array(calibration['raw_wb_max'])
        result['input_extrapolated_points'] = int(np.any((raw < lo) | (raw > hi), axis=1).sum())
    s.dump(args.output, result)
    s.finish(str(args.output)+'.inputs.json')
    print('已写入分析 JSON；未生成 DAT、卡文件或机身代码。')


if __name__ == '__main__':
    main()
