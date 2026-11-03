"""Finite foreground model runs, held-out aggregation, and numerical checks."""
from pathlib import Path
import argparse
import csv
import json
import platform
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
vm = rt.module('value_model', rt.HERE / 'model.py')


def check_inputs():
    checked = []
    for directory in ('hw_refit_r1', 'gr4_analytic_target_r1', 'gr4_analytic_target_r2'):
        folder = rt.ROOT / 'research' / directory
        for line in rt.inp(folder / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split(maxsplit=1)
            path = folder / name.lstrip('*')
            rt.inp(path, digest)
            checked.append(str(path.relative_to(rt.ROOT)))
    rt.dump('verification/upstream.json', dict(files=len(checked), all_ok=True, paths=checked))
    rt.dump('environment.json', dict(python=sys.version, executable=sys.executable,
        platform=platform.platform(), numpy=np.__version__, prediction='电脑预测',
        settings=dict(radius=vm.LIMIT, mix_scale=vm.SCALE, mix_ridge=vm.RIDGE,
            folds=vm.FOLDS, integer='Q10', no_network=True, no_device_access=True)))
    print(json.dumps(dict(upstream_files=len(checked), all_ok=True)), flush=True)


def numerical_checks():
    m = rt.model()
    rows = []
    for slot in ('01', '02', '05', '06'):
        d = vm.data(m, slot, 'page1')
        current = rt.old.Problem(m, slot, d, (), True)
        for hypothesis in ('current', 'H1', 'H2', 'H3'):
            P = vm.Problem(m, slot, d, hypothesis)
            zero = np.zeros(P.np)
            assert np.max(abs(P.predict(zero) - current.predict(np.zeros(current.np)))) < 1e-9
            rng = np.random.default_rng(2701)
            p = rng.normal(size=P.np) * .07
            r, J = P.evaluate(p)
            for key, sl in P.blocks.items():
                direction = np.zeros(P.np)
                direction[sl] = rng.normal(size=sl.stop-sl.start)
                direction /= np.linalg.norm(direction)
                eps = 1e-5
                numerical = (P.evaluate(p + eps*direction)[0] - P.evaluate(p - eps*direction)[0]) / (2*eps)
                relative = float(np.linalg.norm(numerical-J@direction) / max(np.linalg.norm(numerical), 1e-10))
                rows.append(dict(slot=slot, hypothesis=hypothesis, block=key, relative_error=relative))
            assert set(map(tuple, d['train_keys'])).isdisjoint(map(tuple, d['held_keys']))
    rt.dump('verification/jacobians.json', rows)
    maximum = max(r['relative_error'] for r in rows)
    print(json.dumps(dict(jacobian_checks=len(rows), maximum_relative_error=maximum)), flush=True)
    assert maximum < 5e-4


def checks(P, p):
    s, q = P.state(p, True), P.packed(p)['mix_q10']
    offdiag = np.array([q[i,j] for i,j in vm.PAIRS])
    return dict(existing_matrix=bool(abs(s['C']).max() <= 2047 and abs(s['C'][1:]).max() <= 1279),
        existing_sectors=bool(abs(s['A']).max() <= 127 and abs(s['B']).max() <= 127),
        monotone_curves=bool(np.diff(s['q'], axis=1).min() >= 0 and s['q'].min() >= 0 and s['q'].max() <= 255),
        mix_range=bool(abs(offdiag).max() <= P.radius*1024 + 1e-9),
        mix_structure=bool(np.all(q.sum(axis=1) == 1024) if P.hypothesis == 'H2' else np.all(q.diagonal() == 1024)))


def path_for(kind, slot, hypothesis, fold, tag='main'):
    return rt.LOCAL / 'fits' / tag / kind / slot / hypothesis / (fold + '.json')


def fit_one(m, d, slot, fold, kind, hypothesis, tag='main', nfev=65,
            placement='before_calibration', radius=vm.LIMIT, ridge=vm.RIDGE, base=None):
    path = path_for(kind, slot, hypothesis, fold, tag)
    if path.exists(): return rt.read(path)
    P = vm.Problem(m, slot, d, hypothesis, placement, radius, ridge)
    attempts, vectors = [], []
    starts = [np.zeros(P.np)]
    if hypothesis != 'current' and base is not None:
        initial = np.zeros(P.np)
        initial[:P.base_np] = base['theta']
        starts.append(initial)
    for initial in starts:
        p, status = P.fit(nfev, initial)
        attempts.append(status)
        if not status['success']:
            p, status = P.fit(2*nfev, p)
            attempts.append(status)
        vectors.append((float(P.evaluate(p)[0] @ P.evaluate(p)[0]), p.copy(), status))
    _, p, status = min(vectors, key=lambda item: item[0])
    pq, refinement = vm.integer_refine(P, p)
    predictions = dict(continuous=P.predict(p), direct=P.predict(p, True), integer=P.predict(pq, True))
    errors = {k: m.fs.delta_e00(m.fs.lab_from_codes(v), d['target']) for k,v in predictions.items()}
    held = d['score_mask'] if fold == 'full' else d['held']
    frozen = rt.old.Problem(m, slot, d).predict(np.zeros(0))
    frozen_error = m.fs.delta_e00(m.fs.lab_from_codes(frozen), d['target'])
    packed = P.packed(pq)
    valid = checks(P, pq)
    result = dict(slot=slot, fold=fold, target_kind=kind, hypothesis=hypothesis, tag=tag,
        evidence='电脑预测', target_label='未验证目标，仅诊断' if kind=='diagnostic' else '现有冻结桥接或富士 LUT 目标',
        placement=placement, radius=radius, ridge=ridge, training_only_selection=True,
        solver=status, attempts=attempts, theta=p, theta_integer=pq, refinement=refinement,
        integer_checks=valid, packed=packed, train_keys=d['train_keys'], held_keys=d['held_keys'],
        train_n=int(d['train'].sum()), held_n=int(held.sum()),
        scores={k: rt.old.score(v[held], d['baseline'][held]) for k,v in errors.items()},
        frozen=rt.old.score(frozen_error[held], d['baseline'][held]),
        seconds=sum(s['seconds'] for s in attempts), camera_verified=False,
        sources=dict(model=rt.sha(rt.HERE/'model.py'), frozen_model=rt.sha(rt.ROOT/'research/hw_refit_r1/model.py')))
    rt.dump(path, result)
    np.savez_compressed(path.with_suffix('.npz'), **{'prediction_'+k:v for k,v in predictions.items()},
        **{'error_'+k:v for k,v in errors.items()}, frozen_error=frozen_error,
        frozen_prediction=frozen, held=held, train=d['train'], baseline=d['baseline'],
        target=d['target'], pages=d['pages'], hue_group=d['hue_group'])
    print(json.dumps(dict(kind=kind, slot=slot, fold=fold, hypothesis=hypothesis, tag=tag,
        similarity=round(100*result['scores']['integer']['similarity'],3),
        ok=status['success'], integer_ok=all(valid.values()), seconds=round(result['seconds'],3))), flush=True)
    return result


def fit_batch(args):
    m = rt.model()
    for kind in args.kinds.split(','):
        for slot in args.slots.split(','):
            if kind == 'diagnostic' and slot not in ('01','02'): continue
            for fold in args.folds.split(','):
                d = vm.data(m, slot, fold, kind)
                base = None
                if args.tag == 'main':
                    base = fit_one(m,d,slot,fold,kind,'current',nfev=args.nfev)
                else:
                    base = rt.read(path_for(kind, slot, 'current', fold))
                for hypothesis in args.hypotheses.split(','):
                    if hypothesis == 'current': continue
                    fit_one(m,d,slot,fold,kind,hypothesis,args.tag,args.nfev,
                        args.placement,args.radius,args.ridge,base)
    rt.finish('fit_' + args.tag)


def aggregate(tag='main'):
    rows = []
    hypotheses = ('current','H1','H2','H3') if tag=='main' else ('H1','H2','H3')
    for kind in ('bridge','diagnostic'):
        for slot in ('01','02','05','06'):
            if kind == 'diagnostic' and slot not in ('01','02'): continue
            for hypothesis in hypotheses:
                for scheme, folds in [('page',vm.FOLDS[:6]),('hue',vm.FOLDS[6:])]:
                    paths = [path_for(kind,slot,hypothesis,f,tag) for f in folds]
                    if not all(p.exists() for p in paths): continue
                    docs = [rt.read(p) for p in paths]
                    aa = [rt.arrays(p.with_suffix('.npz')) for p in paths]
                    cat = lambda k: np.concatenate([a[k][a['held']] for a in aa])
                    b = cat('baseline')
                    assert len(b) == {'01':245,'02':270,'05':301,'06':313}[slot]
                    row = dict(target_kind=kind,slot=slot,hypothesis=hypothesis,scheme=scheme,tag=tag,
                        evidence='电脑预测', **rt.old.score(cat('error_integer'),b),
                        continuous=rt.old.score(cat('error_continuous'),b),
                        direct=rt.old.score(cat('error_direct'),b), frozen=rt.old.score(cat('frozen_error'),b),
                        all_converged=all(d['solver']['success'] for d in docs),
                        integer_valid=all(all(d['integer_checks'].values()) for d in docs),
                        seconds=sum(d['seconds'] for d in docs), folds=len(folds))
                    base_paths = [path_for(kind,slot,'current',f) for f in folds]
                    bb = [rt.arrays(p.with_suffix('.npz')) for p in base_paths]
                    ebase = np.concatenate([a['error_integer'][a['held']] for a in bb])
                    current = rt.old.score(ebase,b)
                    row['current_refit'] = current
                    row['gain_frozen_pp'] = 100*(row['similarity']-row['frozen']['similarity'])
                    row['gain_current_refit_pp'] = 100*(row['similarity']-current['similarity'])
                    row['reduction_frozen_de00'] = row['frozen']['median']-row['median']
                    row['reduction_current_refit_de00'] = current['median']-row['median']
                    rows.append(row)
    rt.dump('aggregate_' + tag + '.json',rows)
    return rows


def write_csv(rows):
    out = rt.HERE / 'scores.csv'
    columns = ['evidence','target_kind','slot','hypothesis','scheme','n','similarity','gain_frozen_pp',
        'gain_current_refit_pp','median','p90','baseline_median','reduction_frozen_de00',
        'reduction_current_refit_de00','all_converged','integer_valid']
    with out.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns)
        writer.writeheader()
        writer.writerows({k:r[k] for k in columns} for r in rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command',choices=['check','fit','aggregate'])
    ap.add_argument('--kinds',default='bridge,diagnostic')
    ap.add_argument('--slots',default='01,02,05,06')
    ap.add_argument('--folds',default=','.join(vm.FOLDS))
    ap.add_argument('--hypotheses',default='H1,H2,H3')
    ap.add_argument('--tag',default='main')
    ap.add_argument('--placement',default='before_calibration',choices=['before_calibration','at_curve'])
    ap.add_argument('--radius',type=float,default=vm.LIMIT)
    ap.add_argument('--ridge',type=float,default=vm.RIDGE)
    ap.add_argument('--nfev',type=int,default=65)
    args=ap.parse_args()
    if args.command == 'check':
        check_inputs()
        numerical_checks()
    elif args.command == 'fit': fit_batch(args)
    else:
        rows=aggregate(args.tag)
        if args.tag=='main': write_csv(rows)
        print(json.dumps(dict(rows=len(rows), all_converged=all(r['all_converged'] for r in rows)),ensure_ascii=False))
    rt.finish(args.command)


if __name__ == '__main__': main()
