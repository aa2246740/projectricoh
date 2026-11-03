"""Run finite foreground batches; resumable outputs stay inside hw_refit_r1."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import *
import argparse
import json
import traceback

FOLDS = [f'page{i}' for i in range(1, 7)] + [f'hue{i}' for i in range(3)] + ['full']
SLOTS = ['05', '06', '01', '02']


def routes():
    out = {'baseline': ((), False), 'current_refit': ((), True)}
    for name, family in FAMILIES.items():
        out['solo_' + name] = (family, False)
        out['joint_' + name] = (family, True)
    for axis in ('Y', 'C', 'C2'):
        for tint in ('add', 'Y'):
            out[f'all_{axis}_{tint}'] = ((f'gain_{axis}', 'offsets', 'six', f'tint_{tint}', 'nodes', 'four'), True)
    out['all_Ymove_add'] = (('gain_Y', 'gain_nodes', 'offsets', 'six', 'tint_add', 'nodes', 'four'), True)
    for axis in ('Y', 'C'):
        out[f'upper_RLUT_{axis}'] = ((f'gain_{axis}', 'offsets', 'six', 'tint_add', 'nodes', 'four', 'rlut'), True)
    return out


def integer_checks(P, p):
    s = P.state(p, True)
    codes = P.stock_codes + s['node_delta']
    return dict(matrix_sign_magnitude=bool(np.max(abs(s['C'])) <= 2047 and np.max(abs(s['C'][1:])) <= 1279),
                sector_sign_magnitude=bool(np.max(abs(s['A'])) <= 127 and np.max(abs(s['B'])) <= 127),
                curves_monotone=bool(np.min(np.diff(s['q'], axis=1)) >= 0),
                c040_order=bool(codes[0] >= 0 and codes[-1] <= 255 and np.min(np.diff(np.r_[codes, codes[0] + 256])) >= 2),
                c120_order=bool(np.min(np.diff(s['gain_nodes'])) > 0),
                c120_gain_range=bool(np.min(s['gains']) >= .5 and np.max(s['gains']) <= 1.5),
                rlut_monotone_u12=bool(np.min(np.diff(s['rlut'], axis=1)) >= 0 and np.min(s['rlut']) >= 0 and np.max(s['rlut']) <= 255))


def run_one(m, slot, fold, name, d, max_nfev=65, overwrite=False, reg_scale=1.):
    tag = name if reg_scale == 1 else f'{name}_reg{reg_scale:g}'
    path = rt.LOCAL / f'fits/{slot}/{tag}/{fold}.json'
    if path.exists() and not overwrite:
        return rt.read(path)
    features, daily = routes()[name]
    P = Problem(m, slot, d, features, daily, reg_scale)
    if P.np:
        p, status = P.fit(max_nfev)
        attempts = [status]
        if not status['success']:
            p, status = P.fit(max_nfev * 2, p)
            attempts.append(status)
    else:
        p, status, attempts = np.zeros(0), {'success': True, 'nfev': 0, 'cost': None, 'seconds': 0, 'parameters': 0}, []
    predicted, errors = {}, {}
    for label, quant in [('continuous', False), ('integer', True)]:
        predicted[label] = P.predict(p, quant)
        errors[label] = m.fs.delta_e00(m.fs.lab_from_codes(predicted[label]), d['target'])
    base_P = Problem(m, slot, d)
    baseline_pred = base_P.predict(np.zeros(0))
    current_e = m.fs.delta_e00(m.fs.lab_from_codes(baseline_pred), d['target'])
    held = d['held'] if fold != 'full' else d['score_mask']
    gray = np.array([r['key'].startswith('GRAY_') or r['key'] in ('ANCHOR_white', 'ANCHOR_black', 'ANCHOR_midgray', 'ANCHOR_darkgray', 'ANCHOR_lightgray') for r in d['records']])
    gray &= held
    checks = integer_checks(P, p)
    result = dict(slot=slot, fold=fold, route=tag, features=features, daily=daily,
                  model_sha256=rt.sha(rt.HERE / 'model.py'),
                  prediction_label='电脑预测', camera_verified=False, deployment_allowed=False,
                  baseline_kind='fold-specific v6/r1 analogue; heldout excluded from calibration, prior and recipe fit',
                  train_n=int(d['train'].sum()), held_n=int(held.sum()),
                  train_keys=d['train_keys'], holdout_keys=d['held_keys'],
                  solver=status, attempts=attempts, integer_checks=checks,
                  current=score(current_e[held], d['baseline'][held]),
                  scores={k: score(e[held], d['baseline'][held]) for k, e in errors.items()},
                  gray_current=score(current_e[gray], d['baseline'][gray]),
                  gray={k: score(e[gray], d['baseline'][gray]) for k, e in errors.items()},
                  theta=p, blocks={k: [v.start, v.stop] for k, v in P.blocks.items()},
                  packed=packed_parameters(P, p))
    rt.dump(path, result)
    np.savez_compressed(path.with_suffix('.npz'), theta=p,
                        prediction_continuous=predicted['continuous'], prediction_integer=predicted['integer'],
                        error_continuous=errors['continuous'], error_integer=errors['integer'],
                        current_error=current_e, current_prediction=baseline_pred, baseline=d['baseline'],
                        held=held, gray=gray, train=d['train'], target=d['target'],
                        input_x=d['x'], bias=d['bias'])
    print(json.dumps(dict(slot=slot, fold=fold, route=tag, ok=status['success'],
                          checks=all(checks.values()), nfev=sum(a['nfev'] for a in attempts),
                          seconds=round(sum(a['seconds'] for a in attempts), 3),
                          similarity=round(100 * result['scores']['integer']['similarity'], 3)), ensure_ascii=False), flush=True)
    return result


def prepare():
    expected = {
        'research/refit_50mm_r7/local/v6/candidate_v6.DEEPTBL': '21159c8143a87680b624adfae6b34e8ab4b4d730a8720907cf2e448dd43b1592',
        'research/gr4_nega_returns_r1/local/candidate/DEEPTBL_50mm_gr4_posi_nega_r1.DAT': '10d3d182bfdd92c80e3c936b93d063764c100b02713aa610c47df74ecb32d670'}
    for k, h in expected.items():
        assert rt.sha(rt.inp(k)) == h
    for path in ['research/hw_mining_r1/validation/VALIDATION.md', 'research/fidelity_ceiling/fuji/REALISTIC.md',
                 'research/fidelity_ceiling/fuji/scripts/realistic.py', 'research/gr4_lut_ceiling/isp.py',
                 'research/lut_convert/fit.py', 'research/color_fit_v2/fuji_round5/core.py']:
        rt.inp(path)
    m = rt.model()
    rows, good, arrays = f.data(m)
    rt.dump('source_data.json', {k: dict(measured=v['measured'], known04=[[q['page'], q['patch_id']] for q in v['rows']],
                                       usable=[[q['frame'], q['patch_id']] for q in rows[k] if q['usable']])
                                 for k, v in arrays.items() if k in ('05', '06')})
    parser = rt.module('hw_stage2l_parser', 'firmware/stage2l_switch/tools/deep_sources.py')
    _, bank = parser.surface_bank()
    parsed = {key: parser.parse(rt.inp(key).read_bytes(), bank) for key in expected}
    checks = []
    for slot in SLOTS:
        d = prepare_data(m, slot, 'full')
        P = Problem(m, slot, d)
        reference = f.predict(m, slot, d['current'], d['x'], unclipped=True)
        diff = float(np.max(abs(P.predict(np.zeros(0)) - np.clip(reference + d['bias'], 0, 255))))
        assert diff < 1e-8
        path = next(k for k in expected if ('refit_50mm' in k) == (slot in ('05', '06')))
        entry = next(e for e in parsed[path] if e['slot'] == int(slot))
        row = m.mm.MatrixRow.from_bytes(entry['written'][3][:28])
        ab = np.array([m.fs.decode_word(entry['written'][2][i * 4:i * 4 + 4]) for i in range(24)])
        assert np.array_equal(row.coef, P.C)
        assert np.array_equal(row.tail, P.tail)
        assert np.array_equal(ab[:, 0], P.A) and np.array_equal(ab[:, 1], P.B)
        inputs, outputs = parser.unpack_tone(*entry['written'][:2])
        assert np.array_equal(np.r_[0, inputs, 4095], P.xnodes) if len(inputs) == 31 else np.array_equal(inputs, P.xnodes)
        assert np.array_equal(outputs, P.q0[1])
        if slot == '06':
            assert np.array_equal(list(entry['written'][6][:33]), P.q0[0])
            assert np.array_equal(list(entry['written'][6][33:]), P.q0[2])
        checks.append(dict(slot=slot, published_bytes_match_full_fit=True, zero_prediction_max_rgb=diff,
                           full_n=int(d['score_mask'].sum())))
    rt.dump('verification/preflight.json', dict(frozen_hashes=expected, published_checks=checks,
                                               parser_all_entries=True, camera_access=False, firmware_build=False))
    rt.finish('preflight')
    print(json.dumps(checks), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['prepare', 'fit'])
    ap.add_argument('--slots', default=','.join(SLOTS))
    ap.add_argument('--folds', default=','.join(FOLDS))
    ap.add_argument('--routes', default='all')
    ap.add_argument('--nfev', type=int, default=65)
    ap.add_argument('--overwrite', action='store_true')
    ap.add_argument('--reg-scale', type=float, default=1.)
    a = ap.parse_args()
    log = (rt.LOCAL / ('foreground_' + str(rt.os.getpid()) + '.log')).open('a')
    class Tee:
        def __init__(self, original):
            self.original = original
        def write(self, text):
            self.original.write(text)
            log.write(text)
            return len(text)
        def flush(self):
            self.original.flush()
            log.flush()
    sys.stdout = Tee(sys.stdout)
    sys.stderr = Tee(sys.stderr)
    if a.command == 'prepare':
        prepare()
        return
    m = rt.model()
    wanted = list(routes()) if a.routes == 'all' else a.routes.split(',')
    start = time.monotonic()
    completed, errors = 0, []
    for slot in a.slots.split(','):
        for fold in a.folds.split(','):
            d = prepare_data(m, slot, fold)
            for name in wanted:
                try:
                    run_one(m, slot, fold, name, d, a.nfev, a.overwrite, a.reg_scale)
                    completed += 1
                except Exception as exc:
                    error = dict(slot=slot, fold=fold, route=name, error=repr(exc), traceback=traceback.format_exc())
                    errors.append(error)
                    rt.dump(f'errors/{slot}_{fold}_{name}.json', error)
                    print(json.dumps(error), flush=True)
    rt.finish('batch_' + str(rt.os.getpid()))
    print(json.dumps(dict(completed=completed, errors=len(errors), seconds=time.monotonic() - start)), flush=True)
    assert not errors, 'See retained errors; unsuccessful tasks must not be counted as completed'


if __name__ == '__main__':
    main()
