#!/usr/bin/env python3
"""Fit every look at both concentrations and bases; keep hardware entries private."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--look', help='Optional original .cube stem; otherwise all seven')
    ap.add_argument('--max-nfev', type=int, default=120)
    args = ap.parse_args()
    preflight(); install_fence()
    import csv
    import struct
    import zlib
    import numpy as np
    Camera, Problem, score, stats, Cube, _, sector_rows, _ = converter()
    c = Camera()
    with np.load(LOCAL/'prepared/dataset.npz', allow_pickle=False) as z:
        data = {k: z[k].copy() for k in z.files}
    dataset_sha256 = sha(LOCAL/'prepared/dataset.npz')
    prepared_sha256 = hashlib.sha256(''.join(sha(p) for p in sorted((LOCAL/'prepared').glob('*.npz'))).encode()).hexdigest()
    models = {}
    for path in sorted((LOCAL/'prepared').glob('*.npz')):
        if path.stem == 'dataset':
            continue
        with np.load(path, allow_pickle=False) as z:
            models[path.stem] = {k: z[k].copy() for k in z.files}
    scenes = json.loads((LOCAL/'prepared/scenes.json').read_text())
    def target(cube, base, alpha):
        return np.clip((1-alpha)*base + alpha*cube.apply(base/255)*255, 0, 255)
    paths = sorted(ORIGINAL.glob('*.cube'))
    if args.look:
        paths = [p for p in paths if p.stem == args.look]
        if not paths:
            raise ValueError('Unknown look')
    for path in paths:
        cube = Cube.read(path)
        slug = path.stem.lower().replace(' ', '_')
        for basis in ('gxr04', 'panasonic_s1rii'):
            bd = {k: data[k+'_stock'] for k in ('train','test','ramp')} if basis == 'gxr04' else models['S1RII']
            for concentration in (100, 70):
                alpha = concentration/100
                desired = target(cube, bd['train'], alpha)
                testtarget = target(cube, bd['test'], alpha)
                ramp = target(cube, bd['ramp'], alpha)
                solutions = {}
                for variant in ('safe', 't1'):
                    dest = LOCAL/'fits'/slug/basis/f'p{concentration}'/variant
                    metrics_path = dest/'metrics.json'
                    P = Problem(c, data['train_x'], desired, variant=variant,
                                sample_weights=data['train_weights'])
                    if (metrics_path.exists() and (dest/'candidate.json').exists() and
                            json.loads(metrics_path.read_text()).get('prepared_sha256') == prepared_sha256 and
                            json.loads(metrics_path.read_text()).get('fit_code_sha256') == sha(HERE/'fit_luts.py') and
                            json.loads(metrics_path.read_text())['solver'].get('max_nfev_budget') == args.max_nfev):
                        old = json.loads((dest/'candidate.json').read_text())
                        solutions[variant] = (P, np.array(old['theta']))
                        print(slug, basis, concentration, variant, 'reuse', flush=True)
                        continue
                    initial = P.theta0.copy()
                    ramp_y = np.maximum.accumulate(ramp@np.array([.299,.587,.114]))
                    initial[P.qstart:P.t2start] = np.tile(ramp_y-c.curve.ys, 3 if P.t1 else 1)
                    if variant == 't1':
                        previous, q0 = solutions['safe']
                        initial = P.promote(q0, previous)
                    fit, solver = P.solve(initial, args.max_nfev)
                    solver['max_nfev_budget'] = args.max_nfev
                    q = P.quantize(fit.x)
                    theta = q['theta']
                    solutions[variant] = (P, theta)
                    export = P.export(q, dest)
                    _, surface = c.src.surface_bank()
                    identity = c.src.recipe_struct(surface, 5)
                    assert len(identity) == 49
                    entry = (dest/'candidate.entry').read_bytes()
                    crc = zlib.crc32(identity)
                    assert struct.unpack_from('>I', entry, 4)[0] == crc
                    (dest/'recipe.identity49.bin').write_bytes(identity)
                    candidate = json.loads((dest/'candidate.json').read_text())
                    candidate.update(identity49_hex=identity.hex(), identity49_crc32=f'{crc:08x}',
                        identity49_sha256=sha(dest/'recipe.identity49.bin'), identity_is_template_placeholder=True,
                        look=path.stem, basis=basis, concentration_percent=concentration,
                        source_lut_sha256=sha(path), personal_use_only=True, firmware_ready=False,
                        deployable=False, accepted=False)
                    dump(dest/'candidate.json', candidate)
                    train, _ = score(c, data['train_stock'], P.predict(theta, data['train_x']), desired)
                    testpred = P.predict(theta, data['test_x'])
                    synthetic, err = score(c, data['test_stock'], testpred, testtarget)
                    synthetic['share_de00_lt_2'] = float(np.mean(err < 2))
                    rows = sector_rows(c, data['test_x'], data['test_stock'], testpred, testtarget)
                    with (dest/'sector_residuals.csv').open('w', newline='') as f:
                        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
                    per_scene, hbase, hpred, htarget = [], [], [], []
                    calibrated = []
                    for i, smeta in enumerate(scenes):
                        take = data[f'scene{i}_take']
                        stock = data[f'scene{i}_stock'][take]
                        base = stock if basis == 'gxr04' else models['S1RII'][f'scene{i}'][take]
                        tar = target(cube, base, alpha)
                        pred = P.predict(theta, data[f'scene{i}_x'][take])
                        sc, se = score(c, stock, pred, tar)
                        sc['share_de00_lt_2'] = float(np.mean(se < 2))
                        per_scene.append({'path': smeta['path'], 'iso': smeta['iso'],
                             'model_calibrated_for_scene_iso': smeta['model_calibrated_for_scene_iso'], **sc})
                        hbase.append(stock); hpred.append(pred); htarget.append(tar)
                        if smeta['model_calibrated_for_scene_iso']:
                            calibrated.append(i)
                    hbase, hpred, htarget = map(np.concatenate, (hbase,hpred,htarget))
                    real, _ = score(c, hbase, hpred, htarget)
                    keep = np.concatenate([np.arange(len(data[f'scene{i}_take']))+sum(len(data[f'scene{j}_take']) for j in range(i))
                                           for i in calibrated])
                    real_calibrated, _ = score(c, hbase[keep], hpred[keep], htarget[keep])
                    uncertainty = []
                    if basis == 'panasonic_s1rii':
                        for model_name, md in models.items():
                            mt = target(cube, md['test'], alpha)
                            ms, _ = score(c, data['test_stock'], testpred, mt)
                            mh = []
                            for i in range(len(scenes)):
                                take = data[f'scene{i}_take']
                                mb = md[f'scene{i}'][take] if model_name == 'S1RII' else md[f'scene{i}']
                                mh.append(target(cube, mb, alpha))
                            msc, _ = score(c, hbase, hpred, np.concatenate(mh))
                            uncertainty.append({'model': model_name, 'synthetic': ms, 'all_scenes': msc})
                    # Repeat quantization at scoring time, including saturation and integer fields.
                    doc = {'look': path.stem, 'source_lut_sha256': sha(path), 'basis': basis,
                           'dataset_sha256': dataset_sha256,
                           'prepared_sha256': prepared_sha256, 'fit_code_sha256': sha(HERE/'fit_luts.py'),
                           'concentration_percent': concentration, 'variant': variant,
                           'train': train, 'synthetic_holdout': synthetic,
                           'all_scene_holdout': real, 'iso200_scene_holdout': real_calibrated,
                           'per_scene': per_scene, 'model_uncertainty': uncertainty,
                           'model_uncertainty_definition': 'same S1RII recipe evaluated against ten model targets; not ten refits',
                           'solver': solver, 'sector_safety': q['safety'], 'export': export,
                           'all_inputs_readonly': True, 'quantized_before_scoring': True,
                           'evidence_kind': '50mm forward-model simulation, never new camera acceptance',
                           'camera_acceptance': False, 'daily_eligible': False}
                    if basis == 'panasonic_s1rii':
                        valid = models['S1RII']['test_inverse_residual'] <= 1e-3
                        doc['inverse_supported_synthetic'], _ = score(c, data['test_stock'][valid], testpred[valid], testtarget[valid])
                        doc['inverse_supported_test_share'] = float(valid.mean())
                    dump(metrics_path, doc)
                    notes = [
                        '这是 50mm ISO 200 前向模型预测，不是新实拍；safe 仅表示不用 T 控制。',
                        '固定 24 扇区和曲线只能近似三维 LUT；同一色相随亮度、饱和度变化的细节仍会偏。',
                        '机型、胡子所用白平衡和标准风格设置未知；sRGB/Rec.709 的具体传递函数也未声明。',
                        '不能复制颗粒、锐化、光晕、局部对比和已裁掉的高光。',
                        'safe 使用共同曲线，无法分别给灰色暗部和亮部染色。' if variant == 'safe' else
                        'T1 使用 R=C、G=B5、B=D 三通道曲线，需要 T 控制，只能作为受限研究候选。',
                    ]
                    if basis == 'panasonic_s1rii':
                        notes.append('松下基底来自非单射 S2V 表的数值反演，多解及无近似原像区域都保留在误差中。')
                    if not solver['success']:
                        notes.append('优化器达到预算上限或未收敛；报告保留原始状态。')
                    (dest/'LIMITATIONS.txt').write_text('\n'.join(notes)+'\n')
                    print(slug, basis, concentration, variant, 'DE00',
                          round(synthetic['de00']['median'], 3), round(synthetic['de00']['p90'], 3),
                          'similarity', None if synthetic['similarity'] is None else round(synthetic['similarity']*100, 1),
                          'status', solver['status'], flush=True)


if __name__ == '__main__':
    main()
