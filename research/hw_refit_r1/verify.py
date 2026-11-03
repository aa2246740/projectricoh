"""Recompute saved predictions from integer fields and recheck frozen inputs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import *
from run import SLOTS, FOLDS, routes
import argparse
import json


def packed_predict(m, slot, d, doc):
    """Independent of optimizer theta, state(), and forward()."""
    c = doc['packed']
    x, features = d['x'], doc['features']
    pre = np.column_stack([np.interp(np.clip(x[:, i], 0, 4095), c['curve_x'], c['curve_y'][i]) for i in range(3)])
    if 'rlut' in features:
        table = np.array(c['rlut_outputs_u12']) * 255 / 4095
        grid = np.array(c['rlut_inputs_u12']) * 255 / 4095 if 'rlut_inputs_u12' in c else np.linspace(0, 255, 33)
        pre = np.column_stack([np.interp(pre[:, i], grid, table[i]) for i in range(3)])
    offsets = np.array(c['output_input_offset_delta']) * doc.get('c100_delta_unit',1.)
    pre = pre + INPUT_INV @ offsets[3:]
    ycc = pre @ (np.array(c['matrix']) / 1024).T + np.array(d['current']['tail'])[:3] + offsets[:3]
    ci = ycc[:, 1] - 128 + 1j * (ycc[:, 2] - 128)
    old = m.table.nodes.copy()
    blob = rt.inp(rt.s.FW / 'jlaunch3').read_bytes()
    native = np.frombuffer(blob[0xE12F4:0xE12F4 + 48], np.uint8)[::2].astype(int)
    nodes = old + (np.array(c['c040_codes']) - native) * 360 / 256
    m.table.nodes = nodes
    try:
        z = m.effective(np.array(c['A']), np.array(c['B'])) / m.stock_effective
        co = m.table.forward(ci, z)[0]
    finally:
        m.table.nodes = old
    if 'four' in features:
        W = f.weights_cyclic(m.mm.hue_deg(ci), nodes)[:, [0, 11, 17, 23]]
        v = np.array(c['c080_extra_cd'])
        co += 1j / 32 * ((W @ v[:4]) * ci.real + (W @ v[4:]) * ci.imag)
    for key in ('gain_Y', 'gain_C', 'gain_C2'):
        if key not in features:
            continue
        axis = ycc[:, 0] / 255 if key == 'gain_Y' else abs(ci) / doc.get('c120_radius_max', 128 * np.sqrt(2))
        if key == 'gain_C2':
            axis **= 2
        co *= np.interp(axis, np.r_[0, c['c120_nodes_u14'], 16383] / 16383,
                        np.array(c['c120_gain_u8']) / 64)
    tint = np.array(c['c004_signed_magnitude_delta']) * doc.get('c004_delta_unit',1.)
    if 'tint_add' in features:
        co += tint[0] + 1j * tint[1]
    if 'tint_Y' in features:
        co += (tint[0] + 1j * tint[1]) * np.clip(ycc[:, 0] / 255, 0, 1)
    return np.clip(m.mm.rgb_from_ycc(ycc[:, 0], co) + d['bias'], 0, 255)


def core_checks():
    m = rt.model()
    records = []
    for slot in SLOTS:
        d = prepare_data(m, slot, 'page1')
        families = [ ('gain_Y', 'offsets', 'six', 'tint_Y', 'nodes', 'four', 'rlut'),
                     ('gain_C', 'offsets', 'six', 'tint_add', 'nodes', 'four'),
                     ('gain_C2', 'gain_nodes') ]
        for n, features in enumerate(families):
            P = Problem(m, slot, d, features, True)
            rng = np.random.default_rng(8 + n)
            p = rng.normal(size=P.np) * .05
            residual, J = P.evaluate(p)
            for key, sl in P.blocks.items():
                direction = np.zeros(P.np)
                direction[sl] = rng.normal(size=sl.stop - sl.start)
                direction /= np.linalg.norm(direction)
                eps = 1e-6
                numerical = (P.evaluate(p + eps * direction)[0] - P.evaluate(p - eps * direction)[0]) / (2 * eps)
                relative = float(np.linalg.norm(numerical - J @ direction) / max(np.linalg.norm(numerical), 1e-10))
                records.append(dict(slot=slot, feature_set=n, block=key, relative_error=relative))
    rt.dump('verification/jacobians.json', records)
    assert max(r['relative_error'] for r in records) < 3e-4, sorted(records, key=lambda r: r['relative_error'])[-5:]
    # Five affine fields have at most three independent pixel effects at a fixed C.
    P = Problem(m, '05', prepare_data(m, '05', 'page1'), ('offsets',))
    M = P.C / 1024
    affine = np.column_stack([np.eye(3), M @ INPUT_INV])
    rank = int(np.linalg.matrix_rank(affine))
    assert rank == 3
    rt.dump('verification/affine_rank.json', dict(matrix=affine, rank=rank, fields=5,
            consequence='input offsets are absorbed into output offsets for a fixed linear matrix; bounds and regularization can still differ'))
    code_gaps = np.diff(np.r_[P.stock_codes, P.stock_codes[0] + 256])
    model_gaps = np.diff(np.r_[P.orig_nodes, P.orig_nodes[0] + 360])
    lower_model_gap = float(np.min(model_gaps - (code_gaps - 2) * 360 / 256))
    assert lower_model_gap > 0
    rt.dump('verification/c040_geometry.json', dict(stock_codes=P.stock_codes,
            minimum_model_gap_given_integer_gap2_deg=lower_model_gap,
            order_of_measured_response_nodes_preserved=True))
    rt.finish('core_checks')
    print(json.dumps(dict(jacobian_checks=len(records), max_relative_error=max(r['relative_error'] for r in records), affine_rank=rank)), flush=True)


def all_checks():
    m = rt.model()
    errors, baseline_errors, checks, n = [], [], [], 0
    refined_count, missing_refined, objective_errors = 0, [], []
    cache = {}
    for path in sorted((rt.LOCAL / 'fits').rglob('*.json')):
        doc = rt.read(path)
        assert doc['model_sha256'] == rt.sha(rt.HERE / 'model.py'), 'saved solver used a different model source'
        key = doc['slot'], doc['fold']
        if key not in cache:
            cache[key] = prepare_data(m, *key)
        d = cache[key]
        a = rt.arrays(path.with_suffix('.npz'))
        assert set(map(tuple, doc['train_keys'])).isdisjoint(set(map(tuple, doc['holdout_keys'])))
        independent = packed_predict(m, key[0], d, doc)
        errors.append(float(np.max(abs(independent - a['prediction_integer']))))
        e = m.fs.delta_e00(m.fs.lab_from_codes(independent), d['target'])
        errors.append(float(np.max(abs(e - a['error_integer']))))
        q = score(e[a['held']], a['baseline'][a['held']])
        errors.append(abs(q['similarity'] - doc['scores']['integer']['similarity']))
        features, daily = routes()[doc['route'].split('_reg')[0]]
        reg_scale = float(doc['route'].split('_reg')[1]) if '_reg' in doc['route'] else 1.
        P = Problem(m, key[0], d, features, daily, reg_scale)
        continuous = P.predict(np.array(doc['theta']))
        errors.append(float(np.max(abs(continuous - a['prediction_continuous']))))
        current = f.predict(m, key[0], d['current'], d['x'], unclipped=True)
        baseline_errors.append(float(np.max(abs(np.clip(current + d['bias'], 0, 255) - a['current_prediction']))))
        stored_points = d['current_doc'].get('points', [])
        if key[1] != 'full' and stored_points:
            by_key = {(r['frame'], r['patch_id']): r for r in stored_points}
            reference = []
            for i in np.flatnonzero(a['held']):
                rec = d['records'][i]
                r = by_key[rec['frame'], rec['patch_id']]
                reference.append(r['pure_after_de00'] if key[0] in ('05', '06') else r['new']['candidate'])
            baseline_errors.append(float(np.max(abs(np.array(reference) - a['current_error'][a['held']]))))
        # The response keeps the integer fields exactly; no rounding of final pixels is claimed.
        assert np.allclose(a['target'], d['target']) and np.allclose(a['bias'], d['bias'])
        assert np.array_equal(a['train'], d['train'])
        gray_reference = np.array([r['key'].startswith('GRAY_') or r['key'] in ('ANCHOR_white', 'ANCHOR_black', 'ANCHOR_midgray', 'ANCHOR_darkgray', 'ANCHOR_lightgray') for r in d['records']]) & a['held']
        assert np.array_equal(a['gray'], gray_reference), 'gray-axis population includes a colour anchor'
        for quant in ('continuous', 'integer'):
            expected_gray = score(a['error_' + quant][gray_reference], a['baseline'][gray_reference])
            assert expected_gray['n'] == doc['gray'][quant]['n']
            if expected_gray['n']:
                assert abs(expected_gray['median'] - doc['gray'][quant]['median']) < 1e-10
        eligible_refine = any(k in doc['features'] for k in ('offsets', 'tint_add', 'tint_Y', 'gain_Y', 'gain_C', 'gain_C2', 'rlut'))
        refined_path = rt.LOCAL / 'integer_refined' / path.relative_to(rt.LOCAL / 'fits')
        if eligible_refine and not refined_path.exists():
            missing_refined.append(str(refined_path.relative_to(rt.HERE)))
        if refined_path.exists():
            rd = rt.read(refined_path)
            ra = rt.arrays(refined_path.with_suffix('.npz'))
            rp = packed_predict(m, key[0], d, rd)
            errors.append(float(np.max(abs(rp - ra['prediction_integer']))))
            re = m.fs.delta_e00(m.fs.lab_from_codes(rp), d['target'])
            errors.append(float(np.max(abs(re - ra['error_integer']))))
            assert not rd['heldout_used_for_selection']
            assert rd['final_training_objective'] <= rd['start_training_objective'] + 1e-8
            assert rd['model_sha256'] == doc['model_sha256']
            for field in ('matrix', 'A', 'B', 'curve_x', 'curve_y', 'c040_codes', 'c120_nodes_u14', 'c080_extra_cd'):
                assert np.array_equal(rd['packed'][field], doc['packed'][field])
            if 'rlut' in doc['features']:
                assert np.array_equal(rd['packed']['rlut_inputs_u12'], np.r_[0, np.arange(1, 32) * 128, 4095])
                output = np.array(rd['packed']['rlut_outputs_u12'])
                assert output.min() >= 0 and output.max() <= 4095 and np.diff(output, axis=1).min() >= 0
            else:
                assert np.array_equal(rd['packed']['rlut_outputs_u12'], doc['packed']['rlut_outputs_u12'])
            assert np.max(abs(np.array(rd['packed']['c004_signed_magnitude_delta']))) <= 8
            assert np.all(abs(np.array(rd['packed']['output_input_offset_delta'])) <= np.array([4, 8, 8, 8, 8]))
            assert np.min(rd['packed']['c120_gain_u8']) >= 32 and np.max(rd['packed']['c120_gain_u8']) <= 96
            effective = np.array(doc['theta'])
            for name, field in [('offsets', 'output_input_offset_delta'), ('tint_add', 'c004_signed_magnitude_delta'), ('tint_Y', 'c004_signed_magnitude_delta')]:
                if name in P.blocks:
                    effective[P.blocks[name]] = rd['packed'][field]
            for name in ('gain_Y', 'gain_C', 'gain_C2'):
                if name in P.blocks:
                    effective[P.blocks[name]] = np.array(rd['packed']['c120_gain_u8']) - 64
            component = m.fs.de00_components(m.fs.lab_from_codes(rp), d['target'])
            cost = float(np.sum(component[d['train']] ** 2) + np.sum((P.R @ effective) ** 2))
            objective_errors.append(abs(cost - rd['final_training_objective']))
            refined_count += 1
        checks.append(dict(path=str(path.relative_to(rt.HERE)), solver=doc['solver']['success'],
                           integer_fields=all(doc['integer_checks'].values())))
        n += 1
    assert errors and max(errors) < 1e-8, max(errors)
    assert max(baseline_errors) < 1e-8
    assert not objective_errors or max(objective_errors) < 1e-6
    expected = len(routes()) * len(SLOTS) * len(FOLDS)
    missing = [f'{slot}/{name}/{fold}' for slot in SLOTS for name in routes() for fold in FOLDS
               if not (rt.LOCAL / f'fits/{slot}/{name}/{fold}.json').exists()]
    alt_path = rt.HERE / 'unfrozen06_summary.json'
    alt_result = None
    if alt_path.exists():
        from unfrozen06 import UnfrozenProblem
        alt_docs = sorted((rt.LOCAL / 'unfrozen06/fits/06').rglob('*.json'))
        alt_errors, alt_failed, alt_invalid = [], [], []
        for path in alt_docs:
            doc = rt.read(path)
            assert doc['scope_model_sha256'] == rt.sha(rt.HERE / 'unfrozen06.py')
            d = cache['06', doc['fold']]
            a = rt.arrays(path.with_suffix('.npz'))
            P = UnfrozenProblem(m, '06', d, doc['features'], doc['daily'])
            alt_errors.append(float(np.max(abs(P.predict(np.array(doc['theta'])) - a['prediction_continuous']))))
            rd_path = rt.LOCAL / 'unfrozen06/integer_refined' / path.relative_to(rt.LOCAL / 'unfrozen06/fits')
            rd = rt.read(rd_path) if rd_path.exists() else doc
            ra = rt.arrays(rd_path.with_suffix('.npz')) if rd_path.exists() else a
            pred = packed_predict(m, '06', d, rd)
            alt_errors.append(float(np.max(abs(pred - ra['prediction_integer']))))
            e = m.fs.delta_e00(m.fs.lab_from_codes(pred), d['target'])
            alt_errors.append(float(np.max(abs(e - ra['error_integer']))))
            if not doc['solver']['success']:
                alt_failed.append(str(path.relative_to(rt.HERE)))
            if not all(doc['integer_checks'].values()):
                alt_invalid.append(str(path.relative_to(rt.HERE)))
        assert len(alt_docs) == 230 and max(alt_errors) < 1e-8
        alt_result = dict(fits=len(alt_docs), max_error=max(alt_errors), unsuccessful=alt_failed, integer_invalid=alt_invalid)
    radius_result = None
    radius_path = rt.HERE / 'c120_radius_sensitivity.json'
    if radius_path.exists():
        radius_docs=sorted((rt.LOCAL/'c120_radius').rglob('fits/*/*/*.json'))
        radius_errors=[]
        for path in radius_docs:
            doc=rt.read(path); d=cache[doc['slot'],doc['fold']]
            root=path.parents[3]
            refined=root/'integer_refined'/path.relative_to(root/'fits')
            rd=rt.read(refined); a=rt.arrays(refined.with_suffix('.npz'))
            pred=packed_predict(m,doc['slot'],d,rd)
            radius_errors.append(float(np.max(abs(pred-a['prediction_integer']))))
            e=m.fs.delta_e00(m.fs.lab_from_codes(pred),d['target'])
            radius_errors.append(float(np.max(abs(e-a['error_integer']))))
            assert not rd['heldout_used_for_selection']
            assert rd['final_training_objective']<=rd['start_training_objective']+1e-8
        assert len(radius_docs)==320 and max(radius_errors)<1e-8
        radius_result=dict(fits=len(radius_docs),max_error=max(radius_errors))
    result = dict(saved_runs=n, expected_primary_runs=expected, missing=missing,
                  independent_packed_max_error=max(errors), baseline_max_rgb_error=max(baseline_errors),
                  unsuccessful=[c['path'] for c in checks if not c['solver']],
                  integer_invalid=[c['path'] for c in checks if not c['integer_fields']],
                  integer_refined_runs=refined_count, missing_integer_refinement=missing_refined,
                  independent_training_objective_max_error=max(objective_errors) if objective_errors else None,
                  unfrozen06=alt_result,
                  c120_radius_sensitivity=radius_result,
                  no_camera_acceptance=True, quantization_scope='parameters only; assumed new-field units; no cycle-accurate ISP arithmetic')
    rt.dump('verification/replay.json', result)
    rt.finish('replay')
    print(json.dumps(result, ensure_ascii=False), flush=True)
    assert not missing and not missing_refined, 'Incomplete primary fits or integer refinement'
    assert n == expected + 320, 'Missing supplementary regularization fits'
    assert alt_result and alt_result['fits'] == 230, '06 all-current-control sensitivity incomplete'
    assert radius_result and radius_result['fits']==320, 'C120 normalization sensitivity incomplete'


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['core', 'all'])
    args = ap.parse_args()
    core_checks() if args.command == 'core' else all_checks()
