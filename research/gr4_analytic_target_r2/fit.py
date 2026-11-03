"""Same hw_refit_r1 equations and folds, new diagnostic targets, no outer tuning."""
from pathlib import Path
import argparse
import json
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np

FOLDS = [f'page{i}' for i in range(1, 7)] + [f'hue{i}' for i in range(3)]
ROUTES = {
    'frozen_current': ((), False),
    'current_refit': ((), True),
    'candidate_Y': (('gain_Y', 'gain_nodes'), True),
    'candidate_C': (('gain_C',), True),
    'candidate_all': (('gain_Y', 'gain_nodes', 'offsets', 'six', 'tint_add', 'nodes', 'four'), True),
    'candidate_all_C': (('gain_C', 'offsets', 'six', 'tint_add', 'nodes', 'four'), True),
    'candidate_RLUT': (('gain_Y', 'offsets', 'six', 'tint_add', 'nodes', 'four', 'rlut'), True),
}


def data(m, slot, fold, target=None):
    d = rt.old.prepare_data(m, slot, fold)
    a = rt.arrays(rt.LOCAL / 'data' / (slot + '.npz'))
    d['old_target'], d['old_baseline'] = d['target'].copy(), d['baseline'].copy()
    d['target'] = a['target'].copy() if target is None else target.copy()
    d['base_rgb'] = a['base_rgb']
    d['scene'] = a['scene']
    d['baseline'] = m.fs.delta_e00(m.fs.lab_from_codes(a['base_rgb']), d['target'])
    assert np.array_equal(d['score_mask'], a['supported'])
    assert np.all(~(d['train'] & d['held']))
    return d


def packed_check(P, p):
    s = P.state(p, True)
    codes = P.stock_codes + s['node_delta']
    return dict(matrix=bool(abs(s['C']).max() <= 2047 and abs(s['C'][1:]).max() <= 1279),
        sectors=bool(abs(s['A']).max() <= 127 and abs(s['B']).max() <= 127),
        monotone_curve=bool(np.diff(s['q'], axis=1).min() >= 0),
        node_order=bool(codes[0] >= 0 and codes[-1] <= 255 and np.diff(np.r_[codes, codes[0] + 256]).min() >= 2),
        gain_nodes=bool(np.diff(s['gain_nodes']).min() > 0),
        gain_range=bool(s['gains'].min() >= .5 and s['gains'].max() <= 1.5),
        rlut=bool(np.diff(s['rlut'], axis=1).min() >= 0 and s['rlut'].min() >= 0 and s['rlut'].max() <= 255))


def fit_one(m, slot, fold, route, d, tag='main', nfev=65, cls=None):
    path = rt.LOCAL / 'fits' / tag / slot / route / (fold + '.json')
    if path.exists():
        return rt.read(path)
    features, daily = ROUTES[route]
    P = (cls or rt.old.Problem)(m, slot, d, features, daily)
    if P.np:
        p, status = P.fit(nfev)
        attempts = [status]
        if not status['success']:
            p, status = P.fit(nfev * 2, p)
            attempts.append(status)
    else:
        p, status, attempts = np.zeros(0), dict(success=True, nfev=0, seconds=0), []
    pred = P.predict(p, True)
    continuous = P.predict(p, False)
    error = m.fs.delta_e00(m.fs.lab_from_codes(pred), d['target'])
    err_float = m.fs.delta_e00(m.fs.lab_from_codes(continuous), d['target'])
    old_error = m.fs.delta_e00(m.fs.lab_from_codes(pred), d['old_target'])
    held = d['score_mask'] if fold == 'full' else d['held']
    current = rt.old.Problem(m, slot, d).predict(np.zeros(0))
    current_e = m.fs.delta_e00(m.fs.lab_from_codes(current), d['target'])
    result = dict(slot=slot, fold=fold, tag=tag, route=route, evidence='电脑预测',
        target_label='未验证的模拟目标，仅作诊断', camera_verified=False, deployment_allowed=False,
        solver=status, attempts=attempts, integer_checks=packed_check(P, p),
        score=rt.old.score(error[held], d['baseline'][held]),
        continuous_score=rt.old.score(err_float[held], d['baseline'][held]),
        old_target_score=rt.old.score(old_error[held], d['old_baseline'][held]),
        frozen_current=rt.old.score(current_e[held], d['baseline'][held]),
        train_keys=d['train_keys'], held_keys=d['held_keys'], theta=p,
        parameters=rt.old.packed_parameters(P, p), training_only=True,
        total_seconds=sum(a['seconds'] for a in attempts))
    rt.dump(path, result)
    np.savez_compressed(path.with_suffix('.npz'), prediction=pred, prediction_continuous=continuous,
        error=error, error_continuous=err_float, old_error=old_error,
        target=d['target'], old_target=d['old_target'], baseline=d['baseline'], old_baseline=d['old_baseline'],
        held=held, train=d['train'], theta=p, current=current, current_error=current_e)
    print(json.dumps(dict(tag=tag, slot=slot, fold=fold, route=route,
        percent=round(result['score']['similarity'] * 100, 3), median=result['score']['median'],
        ok=status['success'], packed=all(result['integer_checks'].values()),
        seconds=round(result['total_seconds'], 2))), flush=True)
    return result


def aggregate(tag='main'):
    rows = []
    for slot in ('01', '02'):
        for route in ROUTES:
            for scheme, folds in [('page', FOLDS[:6]), ('hue', FOLDS[6:])]:
                paths = [rt.LOCAL / 'fits' / tag / slot / route / (f + '.npz') for f in folds]
                if not all(p.exists() for p in paths): continue
                aa = [rt.arrays(p) for p in paths]
                docs = [rt.read(p.with_suffix('.json')) for p in paths]
                cat = lambda k: np.concatenate([a[k][a['held']] for a in aa])
                e, b = cat('error'), cat('baseline')
                rows.append(dict(slot=slot, route=route, scheme=scheme, tag=tag, evidence='电脑预测',
                    **rt.old.score(e, b), continuous=rt.old.score(cat('error_continuous'), b),
                    old_target=rt.old.score(cat('old_error'), cat('old_baseline')),
                    similarity_old_denominator=float(1 - np.median(e) / np.median(cat('old_baseline'))),
                    converged=sum(d['solver']['success'] for d in docs), total_folds=len(folds),
                    packed_valid=all(all(d['integer_checks'].values()) for d in docs),
                    seconds=sum(d['total_seconds'] for d in docs)))
    rt.dump('aggregates/' + tag + '.json', rows)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slots', default='01,02')
    ap.add_argument('--folds', default=','.join(FOLDS))
    ap.add_argument('--routes', default=','.join(ROUTES))
    ap.add_argument('--nfev', type=int, default=65)
    args = ap.parse_args()
    m = rt.model()
    for slot in args.slots.split(','):
        for fold in args.folds.split(','):
            d = data(m, slot, fold)
            for route in args.routes.split(','):
                fit_one(m, slot, fold, route, d, nfev=args.nfev)
    print(json.dumps(aggregate(), ensure_ascii=False), flush=True)
    rt.finish('fit')


if __name__ == '__main__': main()
