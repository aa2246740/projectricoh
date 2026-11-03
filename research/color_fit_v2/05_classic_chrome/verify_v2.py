#!/usr/bin/env python3
"""Read back slot 05 candidates through the unchanged v2 chain and table gates."""
import sys
sys.dont_write_bytecode = True
import importlib.util
import json
from pathlib import Path
import signal
import zipfile

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('chrome_fit_verify', HERE / 'fit_v2.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def main():
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('120 second verification bound')))
    signal.alarm(120)
    data = json.loads((m.LOCAL / 'evaluation.json').read_text())
    fit = json.loads((m.LOCAL / 'fit.json').read_text())
    assert fit['stage'] == 'v2-candidate' and fit['firmware_ready'] is False
    assert fit['recommended_variant'] == data['decision']['selected'] == 'sector'
    assert fit['accepted'] is True
    assert all(m.sha(p) == h for p, h in data['inputs_sha256_before'].items())
    assert data['inputs_sha256_before'] == data['inputs_sha256_after']
    src = m.load_module('chrome_verify_rules', m.ROOT / 'firmware/stage2j/tools/deep_sources.py')
    out = {'stage': 'v2-candidate', 'firmware_ready': False, 'models': {}, 'protected_inputs_unchanged': True,
           'protected_input_count': len(data['inputs_sha256_before']), 'table_files_built': False}
    max_cached_error, max_metric_error, max_cold_start_drift = 0., 0., 0.
    for tag in ('iso200', 'iso1600'):
        S, target, samples, e, ei = m.setup(tag)
        assert m.baseline_check(S) == data['baseline']
        xyz = m.fs.chart_xyz_d65(S.ctx.fuji)
        cached_target = np.array([target.chart_target(l) for l in S.labels])
        current_target = np.array([target.scene_target(xyz[l]) for l in S.labels])
        target_error = float(m.fs.delta_e00(cached_target, current_target).max())
        assert target_error < 1e-9
        with zipfile.ZipFile(S.args.fuji_zip) as z:
            leaf = 'gfx-eterna-55-3d-lut-v110/65Grid/F-Log2/FLog2_to_CLASSIC-CHROME_65grid_V.1.00.cube'
            cube_sha = m.hashlib.sha256(z.read(leaf)).hexdigest()
        assert cube_sha == '43f7fc5f262eaa2525c0de805ad7fa50f5b77d85873840ae48ab2a07a6b36ff9'
        out['models'][tag] = {'chart_cache_vs_live_lut_max_de00': target_error,
                              'cube_sha256': cube_sha, 'variants': {}}
        for mode in ('sector', 'yonly'):
            P = m.problem(S, samples, e, mode)
            q = data['variants'][mode]['full']
            payload = fit['alternatives'][mode]
            assert not src.matrix_problems(src.json_matrix(payload, mode))
            blob = src.json_colour(payload, mode)
            decoded = np.array([m.fs.decode_word(blob[4*s:4*s+4]) for s in range(24)])
            assert np.array_equal(decoded, np.column_stack((q['A'], q['B'])))
            assert all(P.sector_ok(int(a), int(b), s) for s, (a, b) in enumerate(decoded))
            row1 = m.mm.MatrixRow.from_words(payload['matrix_row1']['words_u16'])
            row2 = m.mm.MatrixRow.from_words(payload['matrix_row2']['words_u16'])
            assert row1.row_sums()[0] == S.rows['row1'].row_sums()[0]
            assert np.array_equal(row1.coef[1:], S.rows['row1'].coef[1:])
            if mode == 'sector':
                assert row1.to_bytes() == S.rows['row1'].to_bytes()
                assert row2.to_bytes() == S.rows['row2'].to_bytes()
            else:
                assert row2.to_bytes() == m.mm.row2_from_row1(row1, S.rows)[0].to_bytes()
            theta = np.array(q['theta'])
            cached = P.predict(theta)
            original = m.f.JointProblemV2.predict(P, theta)
            Z = m.fs.Z_of_words(np.array(q['A']), np.array(q['B']), S.ctx)
            chain = m.fs.lab_from_codes(S.chain.forward(P.x, S.curves['chrome'], e, row=row1, Zrow=Z)['rgb'])
            max_cached_error = max(max_cached_error, float(np.max(abs(cached-original))),
                                   float(np.max(abs(cached-chain))))
            errors = []
            rec = data['variants'][mode]
            for i in P.chrom_idx:
                label = P.labels[i]
                fold = rec['folds'][label]
                assert label not in fold['training_labels'] and len(fold['training_labels']) == 23
                assert set(fold['training_labels']) == set(P.labels) - {label}
                assert all(P.sector_ok(int(a), int(b), s) for s, (a, b) in enumerate(zip(fold['A'], fold['B'])))
                qrow1 = S.rows['row1'].copy(coef=np.array(fold['Cq']))
                qrow2 = S.rows['row2'] if mode == 'sector' else m.mm.row2_from_row1(qrow1, S.rows)[0]
                assert not src.matrix_problems(qrow1.to_bytes() + qrow2.to_bytes())
                raw = m.f.JointProblemV2.predict(P, np.array(fold['theta']), np.array([i]))[0]
                cached_fold = P.predict(np.array(fold['theta']), np.array([i]))[0]
                max_cached_error = max(max_cached_error, float(np.max(abs(raw-cached_fold))))
                err = float(m.fs.delta_e00(P.lt[i], raw))
                errors.append(err)
                expected = data['evaluation'][tag]['variants'][mode]['loo_per_patch'][label]['de00']
                max_metric_error = max(max_metric_error, abs(err-expected))
                if tag == 'iso200':
                    # Check that the full-fit warm start did not determine a different held-out answer.
                    idx = np.array([j for j in P.fit_idx if j != i])
                    cold, _ = P.solve(idx=idx, max_nfev=350, tol=1e-8)
                    a = P.predict(cold, np.array([i]))[0]
                    b = P.predict(np.array(fold['continuous_theta']), np.array([i]))[0]
                    max_cold_start_drift = max(max_cold_start_drift, float(m.fs.delta_e00(a, b)))
            observed = m.stat(errors)
            expected = data['evaluation'][tag]['variants'][mode]['loo']
            assert max(abs(observed[k]-expected[k]) for k in ('median','p90','max')) < 1e-9
            _, rho, phi = P.split(np.array(rec['continuous_theta']))
            Zq = m.fs.Z_of_words(np.array(q['A']), np.array(q['B']), S.ctx)
            bindings = {'continuous_scale_min': np.where(np.exp(rho) < .5501)[0].tolist(),
                        'continuous_scale_max': np.where(np.exp(rho) > 1.5999)[0].tolist(),
                        'continuous_rotation_limit': np.where(abs(np.degrees(phi)) > 24.999)[0].tolist(),
                        'quantized_scale_range': [float(abs(Zq).min()), float(abs(Zq).max())],
                        'quantized_rotation_range_deg': [float(np.angle(Zq,deg=True).min()), float(np.angle(Zq,deg=True).max())],
                        'signed_word_limit_count': int((abs(decoded)==127).sum())}
            out['models'][tag]['variants'][mode] = {'loo': observed, 'constraints_pass': True, 'bindings': bindings}
    assert max_cached_error < 1e-10
    assert max_metric_error < 1e-9
    assert max_cold_start_drift < .01
    out.update({'cached_vs_unchanged_v2_max_lab_abs': max_cached_error,
                'recomputed_loo_max_de00_difference': max_metric_error,
                'warm_vs_cold_start_heldout_max_de00': max_cold_start_drift,
                'fit_json_sha256': m.sha(m.LOCAL/'fit.json')})
    assert not list(HERE.rglob('*.DAT'))
    m.dump(m.LOCAL/'verification.json', out)
    print('PASS', 'constraints, live LUT, both ISO, 36 integer folds, unchanged v2 chain, input hashes')
    print('max_Lab_difference', max_cached_error, 'cold_start_max_de00', max_cold_start_drift)


if __name__ == '__main__':
    main()
