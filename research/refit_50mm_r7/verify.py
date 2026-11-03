"""Verify the saved table, OOF predictions and consumed source files."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import direct_fit as d
import metrics
from refit import rt,np,s,calibrate
import json
import subprocess


def main():
    import build_v6
    src=build_v6.parser();_,bank=src.surface_bank()
    path=rt.LOCAL/'v6/candidate_v6.DEEPTBL'
    blob=path.read_bytes();parsed=src.parse(blob,bank)
    manifest=rt.load('v6/manifest.json')
    assert s.digest(path)==manifest['candidate_sha256']
    assert manifest['source_sha256']==s.digest(s.DAILY)
    old=src.parse(s.DAILY.read_bytes(),bank)
    unchanged=[]
    for a,b in zip(old,parsed):
        slot=f'{a["slot"]:02d}'
        if slot in ('03','04','07','08'):
            index=src.TABLE_SLOTS.index(a['slot']);start=16+448*index
            assert blob[start:start+448]==s.DAILY.read_bytes()[start:start+448]
            unchanged.append(slot)
    assert unchanged==['04','03','07','08']
    m=rt.model();packed=rt.model()
    packed.base.entries={f'{e["slot"]:02d}':e for e in parsed}
    rng=np.random.default_rng(20261024)
    test_x=np.vstack([rng.uniform(0,4095,(512,3)),np.repeat(np.geomspace(8,3500,129)[:,None],3,axis=1)])
    roundtrip={};neutral={}
    for slot,variant in build_v6.SELECTED.items():
        if variant=='retained':
            expected=m.predict(slot,test_x)
        else:
            c=rt.load(f'direct/{variant}/full/{slot}.json')['candidate']
            expected=d.predict(m,slot,c,test_x)
        actual=packed.predict(slot,test_x)
        error=float(np.max(abs(expected-actual)))
        assert error<1e-8,(slot,error)
        roundtrip[slot]={'points':len(test_x),'max_rgb_code_error':error}
        gray=test_x[-129:]
        lab=packed.fs.lab_from_codes(packed.predict(slot,gray))
        delta=packed.de(packed.predict(slot,gray),m.predict(slot,gray))
        neutral[slot]={'samples':129,'min_Lstar_step':float(np.diff(lab[:,0]).min()),
            'change_vs_daily_de00':d.f.stats(delta)}
        assert np.diff(lab[:,0]).min()>=-1e-8,(slot,'neutral luminance reversal')
    rows,good,arrays=d.f.data(m)
    replays=[];max_error=0.;max_metric=0.
    for slot,variant in build_v6.SELECTED.items():
        if variant=='retained':
            continue
        q=arrays[slot]['measured']
        raw=np.array([r['raw']for r in q]);obs=np.array([r['observed_rgb']for r in q])
        target=np.array([r['target']for r in q])
        lookup={(r['frame'],r['patch_id']):i for i,r in enumerate(q)}
        for fold in [f'page{i}'for i in range(1,7)]+[f'hue{i}'for i in range(3)]:
            path=metrics.path_for(variant,fold,slot)
            doc=json.loads(path.read_text());c=doc['candidate']
            assert c['solver_success'] and all(c['checks'].values())
            train=set(map(tuple,doc['train_keys']));held=set(map(tuple,doc['holdout_keys']))
            assert train.isdisjoint(held)
            cal=rt.load(f'folds/{fold}/calibration.json')
            x=calibrate.apply_calibration(raw,cal)
            prior=rt.load(f'folds/{fold}/{slot}_prior.json')
            if fold.startswith('page'):
                assert all(page!=int(fold[4:])for page,pid in prior['training_keys'])
            else:
                group={(r['page'],r['patch_id']):r['hue_group']for r in rows[slot]if r['usable']}
                assert all(group[page,pid]!=int(fold[3:])for page,pid in prior['training_keys'])
            bias,_=calibrate.prior_bias(prior,x,slot)
            candidate=d.predict(m,slot,c,x,unclipped=True)
            pure=np.clip(candidate+bias,0,255)
            projection=np.clip(obs+candidate-m.predict(slot,x,unclipped=True),0,255)
            pure_error=m.fs.delta_e00(m.fs.lab_from_codes(pure),target)
            projection_error=m.fs.delta_e00(m.fs.lab_from_codes(projection),target)
            errors=[]
            for p in doc['points']:
                i=lookup[p['frame'],p['patch_id']]
                er=max(float(np.max(abs(pure[i]-p['pure_predicted_rgb']))),
                       float(np.max(abs(projection[i]-p['projected_rgb']))))
                metric_error=max(abs(pure_error[i]-p['pure_after_de00']),abs(projection_error[i]-p['after_de00']))
                max_error=max(max_error,er);max_metric=max(max_metric,float(metric_error));errors.append(er)
            assert max(errors,default=0)<1e-8
            replays.append({'slot':slot,'fold':fold,'n':len(doc['points']),
                'train_holdout_disjoint':True,'prior_holdout_excluded':True,'max_rgb_error':max(errors,default=0)})
    assert max_metric<1e-8
    inputs=rt.load('verification/inputs_unchanged.json')
    for name,digest in inputs['sha256'].items():
        assert s.digest(rt.ROOT/name)==digest,name
    cp=subprocess.run([str(rt.LOCAL/'host/table-validator'),str(rt.LOCAL/'v6/candidate_v6.DEEPTBL'),'accept'],
        capture_output=True,text=True,timeout=3)
    assert cp.returncode==0,cp.stderr
    ctests=rt.load('verification/original_c_and_parser.json')
    assert ctests['all_passed'] and len(ctests['cases'])==11
    # Numerical derivative checks include the neutral-axis fix and T2 Jacobian.
    jac=[]
    cal=rt.load('folds/full/calibration.json')
    for slot,variant in [('01','daily'),('02','daily'),('03','daily'),('05','guarded'),('06','tone'),('05','t2'),('05','d8')]:
        qq=arrays[slot]['measured'];x=calibrate.apply_calibration(np.array([r['raw']for r in qq]),cal)
        target0=np.array([r['target']for r in qq])
        P=d.Problem(m,slot,x,target0,np.zeros_like(x),np.ones(len(x),bool),variant=variant)
        p=P.initial.copy();res,J=P.data_parts(p)
        direction=rng.normal(size=P.np)
        step=1e-5
        fd=(P.data_parts(p+step*direction)[0]-P.data_parts(p-step*direction)[0])/(2*step)
        n=3*len(x);relative=float(np.linalg.norm(fd[:n]-J[:n]@direction)/max(np.linalg.norm(fd[:n]),1e-12))
        assert relative<.002,(slot,variant,relative)
        jac.append({'slot':slot,'variant':variant,'directional_data_J_relative_error':relative})
        m.table.nodes=P.original_nodes.copy()
    result={'all_passed':True,'candidate_sha256':manifest['candidate_sha256'],
        'unchanged_entries':unchanged,'packed_forward_roundtrip':roundtrip,'neutral_axis':neutral,
        'oof_replays':replays,'oof_max_rgb_error':max_error,'oof_max_de00_error':max_metric,
        'consumed_inputs_unchanged':inputs['count'],'original_C_output':cp.stdout,
        'original_C_and_parser_cases':len(ctests['cases']),'jacobian':jac,
        'camera_acceptance':False,'firmware_ready':False}
    rt.dump('verification/final.json',result)
    print(json.dumps({'passed':True,'packed_points_per_recipe':len(test_x),'OOF_folds_replayed':len(replays),
        'max_rgb_error':max_error,'max_de00_error':max_metric,'inputs_unchanged':inputs['count']},ensure_ascii=False))


if __name__=='__main__':
    main()
