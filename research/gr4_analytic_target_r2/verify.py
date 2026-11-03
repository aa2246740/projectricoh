"""Replay saved predictions, exclusion contracts, upstream LUT math, boundaries and hashes."""
from pathlib import Path
import argparse
import ast
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import fit as ff
import lut as ll
import pipeline as pp
import decompose as dd
import input_adapter as ia


def public_files():
    return sorted(p for p in rt.HERE.rglob('*') if p.is_file() and not p.is_relative_to(rt.LOCAL)
        and '__pycache__' not in p.parts and p.name != 'SHA256SUMS')


def checksums(seal=False):
    manifest = rt.HERE / 'SHA256SUMS'
    if seal:
        manifest.write_text(''.join(f'{rt.sha(p)}  {p.relative_to(rt.HERE)}\n' for p in public_files()))
    listed = []
    for line in manifest.read_text().splitlines():
        digest, name = line.split('  ', 1)
        p = (rt.HERE / name).resolve()
        assert p.is_relative_to(rt.HERE) and not p.is_relative_to(rt.LOCAL)
        assert rt.sha(p) == digest, name
        listed.append(name)
        print(name + ': OK')
    assert listed == [str(p.relative_to(rt.HERE)) for p in public_files()]
    rt.dump('verification/checksums.json', dict(count=len(listed), all_OK=True, files=listed))
    print(f'SHA256SUMS: {len(listed)} files, all OK')


def upstream_lut():
    path = rt.inp('research/hw_second_pass_r1/lut_control.py')
    tree = ast.parse(path.read_text())
    names = {'kernel', 'fit', 'predict', 'grid', 'apply'}
    pure = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
    from scipy.linalg import cho_factor, cho_solve
    from scipy.spatial.distance import cdist
    namespace = dict(np=np, cho_factor=cho_factor, cho_solve=cho_solve, cdist=cdist)
    # Trusted existing project code only; the downloaded repository is never imported or executed.
    exec(compile(pure, str(path), 'exec'), namespace)
    return namespace


def main():
    m = rt.model()
    data = {(slot, fold): ff.data(m, slot, fold) for slot in ('01', '02') for fold in ff.FOLDS}
    checked, worst = 0, 0.
    tags = ['main', 'wide_radius'] + ['sensitivity_' + n for n in pp.VARIANTS]
    tags += [dd.FIT_TAG + n for n in dd.VARIANTS]
    tags += ['wide_sensitivity_' + n for n in ('exposure_minus_quarter', 'exposure_plus_quarter', 'relative_control', 'fuji_metering')]
    for tag in tags:
        for path in sorted((rt.LOCAL / 'fits' / tag).rglob('*.json')):
            doc = rt.read(path)
            a = rt.arrays(path.with_suffix('.npz'))
            d = {**data[(doc['slot'], doc['fold'])], 'target': a['target'], 'baseline': a['baseline']}
            assert set(map(tuple, doc['train_keys'])).isdisjoint(map(tuple, doc['held_keys']))
            assert np.array_equal(d['train'], a['train']) and np.array_equal(d['held'], a['held'])
            features, daily = ff.ROUTES[doc['route']]
            P = rt.old.Problem(m, doc['slot'], d, features, daily)
            theta = np.asarray(doc['theta'])
            pred = P.predict(theta, True)
            diff = float(abs(pred - a['prediction']).max())
            worst = max(worst, diff)
            assert diff < 1e-10, (path, diff)
            independent_error = rt.cm.delta_e00(rt.lab(pred / 255), a['target'])
            assert np.max(abs(independent_error - a['error'])) < 2e-10, path
            held = a['held']
            med = float(np.median(independent_error[held]))
            assert abs(med - doc['score']['median']) < 2e-10, path
            assert abs((1 - med / np.median(a['baseline'][held])) - doc['score']['similarity']) < 2e-10
            assert ff.packed_check(P, theta) == doc['integer_checks'] and all(doc['integer_checks'].values())
            checked += 1
    assert checked == 630, checked
    print(f'ISP saved-prediction and metric replay: {checked} folds, maximum RGB difference {worst:g}', flush=True)

    upstream = upstream_lut()
    lut_n = 0
    for path in sorted((rt.LOCAL / 'lut').rglob('*.json')):
        doc = rt.read(path)
        a = rt.arrays(path.with_suffix('.npz'))
        d = data[doc['slot'], doc['fold']]
        assert np.array_equal(a['train'], d['train']) and np.array_equal(a['held'], d['held'])
        assert doc['heldout_used_for_choice'] is False
        best = min(doc['inner'], key=lambda row: row['inner_median'])
        assert best == doc['choice']
        x = rt.old.Problem(m, doc['slot'], d).predict(np.zeros(0)) if doc['source'] == 'current' else m.predict('04', d['x'])
        assert np.array_equal(x, a['input'])
        model = upstream['fit'](x[d['train']], ll.target_rgb(d['target'][d['train']]), best['width'], best['ridge'])
        table = upstream['grid'](model, 17)
        assert np.array_equal(table, a['nodes_q8_8']), path
        pred = upstream['apply'](table, x)
        assert np.array_equal(pred, a['prediction'])
        assert np.array_equal(ll.apply(table, x), pred)
        error = rt.cm.delta_e00(rt.lab(pred / 255), d['target'])
        assert abs(np.median(error[d['held']]) - doc['score']['median']) < 2e-10
        lut_n += 1
    assert lut_n == 36
    print('LUT17: all 36 tables and predictions match the frozen upstream equations', flush=True)

    leakage = []
    for slot in ('01', '02'):
        for fold in ('page1', 'hue0'):
            d = data[slot, fold]
            doc = rt.read(rt.LOCAL / f'fits/main/{slot}/current_refit/{fold}.json')
            p = np.asarray(doc['theta'])
            P = rt.old.Problem(m, slot, d, (), True)
            r1, j1 = P.evaluate(p)
            poisoned = {**d, 'target': d['target'].copy(), 'x': d['x'].copy()}
            poisoned['target'][d['held']] = [70., 50., -40.]
            poisoned['x'][d['held']] = [123., 456., 789.]
            Q = rt.old.Problem(m, slot, poisoned, (), True)
            r2, j2 = Q.evaluate(p)
            assert np.array_equal(r1, r2) and np.array_equal(j1, j2)
            targets, parameters = dd.projections(m, slot, d)
            altered = {**d, 'scene': d['scene'].copy()}
            altered['scene'][d['held']] = [.11, .17, .23]
            _, other = dd.projections(m, slot, altered)
            for key in ('look_post_matrix_q10', 'curve_codes'):
                assert np.array_equal(parameters[key], other[key])
            for key in ('A', 'B'):
                if key in parameters['MA']: assert np.array_equal(parameters['MA'][key], other['MA'][key])
            for name, rgb in targets.items():
                saved = rt.arrays(rt.LOCAL / f'{dd.DETAIL}/{slot}/{fold}_{name}.npz')
                assert np.max(abs(rt.lab(rgb) - saved['simplified_target'])) < 2e-11
            leakage.append(dict(slot=slot, fold=fold, held_target_and_input_poisoned=True,
                training_residual_and_jacobian_bit_identical=True, component_projection_parameters_bit_identical=True))
    print('Four page/hue counterexamples: held pixels do not change training objectives or component parameters', flush=True)

    state = pp.common()
    chart = next(iter(ia.chart_sources()))
    assert np.all(ia.radial_factor(np.array([0., .5, 1.]), None, state) == 1)
    assert np.all(ia.radial_factor(np.array([0., .5, 1.]), '0' * 64, state) == 1)
    assert ia.radial_factor(1., chart, state) > 1
    assert not rt.read(rt.LOCAL / 'B/summary.json')['real_photo_accuracy_gate_passed']
    dense_saved = rt.arrays('research/gr4_analytic_target_r1/local/predictions_primary_pre_hard.npz')
    dense_new = rt.arrays(rt.LOCAL / 'B/dense_predictions.npz')
    assert all(np.array_equal(dense_saved[k], dense_new[k]) for k in rt.sim.MODES)
    b = rt.read(rt.LOCAL / 'B/summary.json')
    assert b['GXR_A_targets_unchanged'] and b['common_parameters_refitted'] is False

    de = rt.cm.delta_e00(np.array([[50., 2.6772, -79.7751], [50., 3.1571, -77.2803]]), np.array([[50., 0., -82.7485]] * 2))
    assert np.allclose(de, [2.0425, 2.8615], atol=5e-5, rtol=0)
    guards = {}
    outside = rt.ROOT / '.gr4-analytic-r2-denied-probe'
    assert not outside.exists()
    try: outside.write_text('must never be written')
    except PermissionError: guards['outside_write_denied'] = True
    assert not outside.exists()
    try: sys.audit('socket.connect', None, ('example.invalid', 443))
    except PermissionError: guards['network_denied'] = True
    synthetic = compile('pass', str(rt.ROOT / 'artifacts/downloads/synthetic_r2_boundary_probe.py'), 'exec')
    try: sys.audit('exec', synthetic)
    except PermissionError: guards['download_execution_denied'] = True
    assert len(guards) == 3
    assert all((rt.HERE / p).resolve().is_relative_to(rt.HERE) for p in rt.WRITES)
    rt.finish('verification')
    import scipy
    report = dict(status='PASS_RESEARCH_INTEGRITY_ONLY', evidence='电脑预测与既有真实照片离线重放',
        ISP_folds_replayed=checked, max_prediction_rgb_difference=worst, LUT17_tables_replayed=lut_n,
        upstream_LUT_parity=True, leakage_counterexamples=leakage, guards=guards,
        existing_inputs_unchanged=True, frozen_input_count=len(rt.INPUTS), local_ignored=True,
        real_photo_accuracy_gate_passed=False, adopted_GXR_target=False,
        camera_or_card_access=False, firmware_build=False, network_used=False,
        environment=dict(python=sys.version.split()[0], numpy=np.__version__, scipy=scipy.__version__))
    rt.dump('verification/integrity.json', report)
    (rt.HERE / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('Research integrity verified; real-photo accuracy gate remains failed', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--seal', action='store_true')
    ap.add_argument('--checksums', action='store_true')
    args = ap.parse_args()
    if args.seal or args.checksums: checksums(args.seal)
    else: main()
