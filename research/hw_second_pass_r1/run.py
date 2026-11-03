"""Foreground, finite fitting batches. Writes only this task directory."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import *
import argparse
import datetime
import json
import platform
import traceback


def tag(mode, order, tier):
    return f'{mode}_{order}_{tier}'


def preflight():
    expected = {
      'research/refit_50mm_r7/local/v6/candidate_v6.DEEPTBL':'21159c8143a87680b624adfae6b34e8ab4b4d730a8720907cf2e448dd43b1592',
      'research/gr4_nega_returns_r1/local/candidate/DEEPTBL_50mm_gr4_posi_nega_r1.DAT':'10d3d182bfdd92c80e3c936b93d063764c100b02713aa610c47df74ecb32d670',
      'artifacts/firmware/gxr-1.51/ilaunch3':'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
      'artifacts/firmware/gxr-1.51/jlaunch3':'951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673'}
    for path, digest in expected.items():
        assert rt.sha(rt.inp(path)) == digest, path
    for path in ('research/hw_mining_r1/validation/VALIDATION.md','research/hw_mining_r1/gpt/REPORT.md',
                 'research/hw_refit_r1/REPORT.md','research/hw_refit_r1/summary.json',
                 'research/body_lut/REPORT.md','research/gr4_lut_ceiling/REPORT.md',
                 'research/body_lut/local/nested422_results.json',
                 'research/gr4_lut_ceiling/local/lut/body_summary.json',
                 'research/gr4_lut_ceiling/local/lut/native_physical_summary.json'):
        rt.inp(path)
    m = rt.model()
    checks, jacobians = [], []
    for slot in SLOTS:
        for fold in FOLDS:
            d = old.prepare_data(m, slot, fold)
            P = Pair(m, slot, d, 'mcm', 'a', 'fixed')
            cached = rt.arrays(f'research/hw_refit_r1/local/fits/{slot}/baseline/{fold}.npz')
            diff = float(np.max(abs(P.fixed_rgb-cached['current_prediction'])))
            assert diff < 1e-8
            assert np.array_equal(d['held'], cached['held']) if fold != 'full' else True
            assert np.max(abs(d['target']-cached['target'])) < 1e-8
            assert np.max(abs(d['baseline']-cached['baseline'])) < 1e-8
            path = rt.LOCAL/f'data/{slot}/{fold}.npz'
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(path, x=d['x'], target=d['target'], bias=d['bias'], baseline=d['baseline'],
                                train=d['train'], held=d['held'], score_mask=d['score_mask'],
                                first_published=P.fixed_rgb, pages=d['pages'], hue_group=d['hue_group'])
            rt.dump(path.with_suffix('.json'), dict(slot=slot,fold=fold,records=d['records'],
                    current=d['current'], train_keys=d['train_keys'], held_keys=d['held_keys']))
            checks.append(dict(slot=slot, fold=fold, baseline_max_rgb=diff, n=len(d['x']),
                               train=int(d['train'].sum()), held=int((d['held'] if fold!='full' else d['score_mask']).sum())))
        for order in ('a', 'b'):
            for tier in ('c120Y', 'c120C'):
                P = Pair(m, slot, old.prepare_data(m,slot,'page1'),tier,order,'joint')
                rng = np.random.default_rng(9241)
                p = rng.normal(0,.08,P.np)
                _, J = P.evaluate(p)
                for source, base, label in ((P.first,0,'first'), (P.body,P.nfirst,'body')):
                    for key, sl in source.blocks.items():
                        direction = np.zeros(P.np)
                        direction[base+sl.start:base+sl.stop] = rng.normal(size=sl.stop-sl.start)
                        direction /= np.linalg.norm(direction)
                        eps=1e-6
                        fd=(P.evaluate(p+eps*direction)[0]-P.evaluate(p-eps*direction)[0])/(2*eps)
                        rel=float(np.linalg.norm(fd-J@direction)/max(np.linalg.norm(fd),1e-10))
                        jacobians.append(dict(slot=slot,order=order,tier=tier,source=label,block=key,relative_error=rel))
    assert max(r['relative_error'] for r in jacobians) < 5e-4, sorted(jacobians,key=lambda x:x['relative_error'])[-5:]
    rt.dump('verification/preflight.json', dict(frozen_hashes=expected,checks=checks,jacobians=jacobians,
              prediction_label='电脑预测',camera=False,firmware_build=False))
    import scipy
    rt.dump('environment.json',dict(python=sys.version,executable=sys.executable,numpy=np.__version__,
        scipy=scipy.__version__,platform=platform.platform(),isolated=sys.flags.isolated,dont_write_bytecode=sys.dont_write_bytecode))
    rt.finish('preflight')
    print(json.dumps(dict(baselines=len(checks),jacobians=len(jacobians),max_jacobian_error=max(r['relative_error'] for r in jacobians))),flush=True)


def seeds(P, slot, fold):
    options=[np.zeros(P.np)]
    if P.nfirst:
        path=rt.ROOT/f'research/hw_refit_r1/local/fits/{slot}/all_Ymove_add/{fold}.json'
        doc=rt.read(path)
        seed=np.zeros(P.np)
        for key, pair in doc['blocks'].items():
            if key in P.first.blocks:
                seed[P.first.blocks[key]]=np.array(doc['theta'])[slice(*pair)]
        options.append(seed)
    for kind in ((P.mode,'curves'),(P.mode,'mcm'),('fixed',P.tier)):
        mode,tier=kind
        path=rt.LOCAL/f'fits/{slot}/{tag(mode,P.order,tier)}/{fold}.json'
        if not path.exists():
            continue
        doc=rt.read(path)
        for original in options[:2]:
            seed=original.copy()
            if P.nfirst and mode=='joint':
                for key,pair in doc['first_blocks'].items():
                    seed[P.first.blocks[key]]=np.array(doc['theta'])[slice(*pair)]
            for key,pair in doc['body_blocks'].items():
                if key in P.body.blocks:
                    sl=P.body.blocks[key]
                    seed[P.nfirst+sl.start:P.nfirst+sl.stop]=np.array(doc['theta'])[slice(*pair)]
            options.append(seed)
    values=[float(np.sum(P.evaluate(seed)[0]**2)) for seed in options]
    k=int(np.argmin(values))
    return options[k],dict(candidate_objectives=values,chosen=k,heldout_used=False)


def one(m,slot,fold,d,mode,order,tier,nfev=40,overwrite=False):
    name=tag(mode,order,tier)
    path=rt.LOCAL/f'fits/{slot}/{name}/{fold}.json'
    if path.exists() and not overwrite:
        return rt.read(path)
    P=Pair(m,slot,d,tier,order,mode)
    seed,seed_info=seeds(P,slot,fold)
    p,status=P.fit(nfev,seed)
    attempts=[status]
    if not status['success']:
        p,status=P.fit(nfev,p)
        attempts.append(status)
    continuous=P.predict(p)
    rounded=P.predict(p,True)
    final,refinement=P.refine_integer(p)
    integer=P.predict(final,True)
    e={key:m.fs.delta_e00(m.fs.lab_from_codes(value),d['target']) for key,value in [('continuous',continuous),('rounded',rounded),('integer',integer)]}
    held=d['held'] if fold!='full' else d['score_mask']
    current_e=m.fs.delta_e00(m.fs.lab_from_codes(P.fixed_rgb),d['target'])
    gray=np.array([r['key'].startswith('GRAY_') or r['key'] in ('ANCHOR_white','ANCHOR_black','ANCHOR_midgray','ANCHOR_darkgray','ANCHOR_lightgray') for r in d['records']])&held
    body_blocks={key:[P.nfirst+sl.start,P.nfirst+sl.stop] for key,sl in P.body.blocks.items()}
    checks=integer_checks(P,final)
    result=dict(slot=slot,fold=fold,route=name,mode=mode,order=order,tier=tier,
      prediction_label='电脑预测',camera_verified=False,hardware_semantics_verified=False,
      train_n=int(d['train'].sum()),held_n=int(held.sum()),solver=status,attempts=attempts,seeds=seed_info,
      scores={key:old.score(value[held],d['baseline'][held]) for key,value in e.items()},
      gray={key:old.score(value[gray],d['baseline'][gray]) for key,value in e.items()},
      current=old.score(current_e[held],d['baseline'][held]),integer_checks=checks,integer_refinement=refinement,
      theta_continuous=p,theta=final,first_blocks={key:[sl.start,sl.stop] for key,sl in P.first.blocks.items()},
      body_blocks=body_blocks,packed=P.pack(final),model_sha256=rt.sha(rt.HERE/'pipeline.py'))
    rt.dump(path,result)
    np.savez_compressed(path.with_suffix('.npz'),prediction_integer=integer,prediction_rounded=rounded,
       prediction_continuous=continuous,error_integer=e['integer'],error_rounded=e['rounded'],error_continuous=e['continuous'],
       baseline=d['baseline'],held=held,gray=gray,train=d['train'],target=d['target'],current_error=current_e,
       first_output=P.first.predict(final[:P.nfirst],True) if P.nfirst else P.fixed_rgb)
    print(json.dumps(dict(slot=slot,fold=fold,route=name,ok=status['success'],checks=all(checks.values()),
       seconds=round(sum(a['seconds'] for a in attempts),3),nfev=sum(a['nfev'] for a in attempts),
       similarity=round(100*result['scores']['integer']['similarity'],3))),flush=True)
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('command',choices=['preflight','fit'])
    ap.add_argument('--slots',default=','.join(SLOTS))
    ap.add_argument('--folds',default=','.join(FOLDS))
    ap.add_argument('--modes',default='fixed,joint')
    ap.add_argument('--orders',default='a,b')
    ap.add_argument('--tiers',default=','.join(TIERS))
    ap.add_argument('--nfev',type=int,default=40)
    ap.add_argument('--overwrite',action='store_true')
    ap.add_argument('--deadline-utc',help='Optional ISO-8601 stop time; no expired session deadline on future reproductions')
    args=ap.parse_args()
    deadline=datetime.datetime.fromisoformat(args.deadline_utc).astimezone(datetime.timezone.utc) if args.deadline_utc else None
    log=(rt.LOCAL/f'foreground_{rt.os.getpid()}.log').open('a')
    class Tee:
        def __init__(self,original):self.original=original
        def write(self,s):self.original.write(s);log.write(s);return len(s)
        def flush(self):self.original.flush();log.flush()
    sys.stdout=Tee(sys.stdout);sys.stderr=Tee(sys.stderr)
    if args.command=='preflight':
        preflight();return
    m=rt.model();completed=0;errors=[]
    for slot in args.slots.split(','):
        for fold in args.folds.split(','):
            d=old.prepare_data(m,slot,fold)
            for mode in args.modes.split(','):
                for order in args.orders.split(','):
                    for tier in args.tiers.split(','):
                        now=datetime.datetime.now(datetime.timezone.utc)
                        if deadline is not None and now>=deadline:
                            rt.finish('timebox_stop');print('TIMEBOX_STOP; retain completed fits',flush=True);return
                        try:
                            one(m,slot,fold,d,mode,order,tier,args.nfev,args.overwrite);completed+=1
                        except Exception as exc:
                            error=dict(slot=slot,fold=fold,route=tag(mode,order,tier),error=repr(exc),traceback=traceback.format_exc())
                            errors.append(error);rt.dump(f'errors/{slot}_{fold}_{tag(mode,order,tier)}.json',error)
                            print(json.dumps(error),flush=True)
    rt.finish('fit_'+str(rt.os.getpid()))
    print(json.dumps(dict(completed=completed,errors=len(errors))),flush=True)
    assert not errors


if __name__=='__main__':main()
