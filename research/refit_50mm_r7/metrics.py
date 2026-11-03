"""Compute all published scores from heldout rows, never training summaries."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import refit as f
from refit import rt,np,s
import json
import csv

SELECTED={'01':'guarded','02':'guarded','03':'retained','05':'guarded','06':'tone'}


def path_for(variant,fold,slot):
    recovered=rt.LOCAL/f'direct/{variant}_n240/{fold}/{slot}.json'
    return recovered if recovered.exists() else rt.LOCAL/f'direct/{variant}/{fold}/{slot}.json'


def collect(slot,variant,scheme):
    folds=[f'page{i}'for i in range(1,7)] if scheme=='page' else [f'hue{i}'for i in range(3)]
    out=[];summaries=[]
    for fold in folds:
        p=path_for('daily' if variant=='retained' else variant,fold,slot)
        d=json.loads(p.read_text())
        assert d['candidate']['solver_success'],str(p)
        rows=d['points']
        if variant=='retained':
            rows=[{**r,'after_de00':r['before_de00'],'pure_after_de00':r['before_de00'],
                'pure_before_de00':r['before_de00']}for r in rows]
        rows=[{**r,'fold':fold}for r in rows]
        assert set(map(tuple,d['train_keys'])).isdisjoint(set(map(tuple,d['holdout_keys'])))
        b=np.array([r['baseline_de00']for r in rows])
        summary={'fold':fold,'n':len(rows),'n_train':d['n_train'],
            'measured_before':f.score([r['before_de00']for r in rows],b),
            'pure_model':f.score([r['pure_after_de00']for r in rows],b),
            'delta_projection':f.score([r['after_de00']for r in rows],b),
            'solver_nfev':d['candidate']['solver_nfev'],
            'sector_guard_alpha':d['candidate'].get('sector_guard',{}).get('alpha')}
        summaries.append(summary);out+=rows
    keys=[(r['frame'],r['patch_id'])for r in out]
    assert len(keys)==len(set(keys))
    return out,summaries


def summarize(points):
    baseline=[r['baseline_de00']for r in points]
    return {'measured_before':f.score([r['before_de00']for r in points],baseline),
        'pure_model_before':f.score([r['pure_before_de00']for r in points],baseline),
        'pure_model_after':f.score([r['pure_after_de00']for r in points],baseline),
        'delta_projection_after':f.score([r['after_de00']for r in points],baseline)}


def main():
    result={'metric':'1 - median(heldout DeltaE00) / median(matched 04 DeltaE00)',
        'mean_metric':'1 - mean(heldout DeltaE00) / mean(matched 04 DeltaE00)',
        'estimator':'untrimmed native CFA and JPEG means, jpeg6 policy',
        'primary':'pure model on heldout RAW + training-only interpolated residual prior',
        'secondary':'old heldout measured JPEG + new-minus-old model response delta',
        'camera_acceptance':False,'selected':SELECTED,'recipes':{},'research':{}}
    sector_rows=[]
    for slot,variant in SELECTED.items():
        d={}
        for scheme in ('page','hue'):
            points,folds=collect(slot,variant,scheme)
            summary=summarize(points)
            rt.dump(f'oof/{slot}_{scheme}.json',points)
            d[scheme]={'scores':summary,'folds':folds,
                'worst_points':sorted(points,key=lambda r:r['pure_after_de00'],reverse=True)[:8]}
            if slot in ('05','06'):
                d[scheme]['sectors']=[]
                for sector in range(24):
                    pp=[r for r in points if r['sector']==sector]
                    q={'slot':slot,'scheme':scheme,'sector':sector,'hue_low':15*sector,'n':len(pp),
                        **summarize(pp)}
                    d[scheme]['sectors'].append(q)
                    sector_rows.append({'slot':slot,'scheme':scheme,'sector':sector,'hue_low':15*sector,
                        'n':len(pp),'old_similarity':q['measured_before']['similarity_median'],
                        'model_similarity':q['pure_model_after']['similarity_median'],
                        'model_median':q['pure_model_after']['de00']['median'],
                        'model_p90':q['pure_model_after']['de00']['p90'],
                        'projection_similarity':q['delta_projection_after']['similarity_median']})
                strata=[]
                for l0,l1 in ((0,35),(35,70),(70,101)):
                    for c0,c1 in ((0,12),(12,35),(35,200)):
                        pp=[r for r in points if l0<=r['Lstar']<l1 and c0<=r['Cstar']<c1]
                        strata.append({'Lstar':[l0,l1],'Cstar':[c0,c1],'n':len(pp),**summarize(pp)})
                d[scheme]['lightness_chroma']=strata
            # This is an arithmetic target, not an attainable noise floor.
            q=summary['pure_model_after']
            if slot in ('05','06'):
                target=.05*q['baseline_de00']['median']
                d[scheme]['to_95']={'required_median_de00':target,
                    'current_median_de00':q['de00']['median'],
                    'needed_further_residual_reduction':1-target/q['de00']['median']}
        a=d['page']['scores']['measured_before']['similarity_median']
        b=d['hue']['scores']['measured_before']['similarity_median']
        assert abs(a-b)<1e-12
        result['recipes'][slot]=d
    for slot in ('05','06'):
        result['research'][slot]={}
        for variant in ('d8','four','t2'):
            result['research'][slot][variant]={}
            for scheme in ('page','hue'):
                points,folds=collect(slot,variant,scheme)
                summary=summarize(points)
                base=result['recipes'][slot][scheme]['scores']
                result['research'][slot][variant][scheme]={'scores':summary,'folds':folds,
                    'extra_similarity_pp_model':100*(summary['pure_model_after']['similarity_median']-
                        base['pure_model_after']['similarity_median']),
                    'extra_similarity_pp_projection':100*(summary['delta_projection_after']['similarity_median']-
                        base['delta_projection_after']['similarity_median'])}
    out=rt.LOCAL/'metrics';out.mkdir(exist_ok=True)
    with (out/'sectors.csv').open('w',newline='')as stream:
        w=csv.DictWriter(stream,fieldnames=list(sector_rows[0]));w.writeheader();w.writerows(sector_rows)
    rt.dump('metrics/summary.json',result)
    # Merge consumed-input manifests and verify actual current bytes.
    inputs={}
    for path in rt.LOCAL.rglob('*inputs.json'):
        doc=json.loads(path.read_text())
        for name,digest in doc.get('sha256',{}).items():
            assert name not in inputs or inputs[name]==digest,(name,'input versions conflict')
            inputs[name]=digest
    assert all(s.digest(rt.ROOT/p)==h for p,h in inputs.items())
    rt.dump('verification/inputs_unchanged.json',{'all_inputs_unchanged':True,'count':len(inputs),'sha256':inputs})
    for slot,d in result['recipes'].items():
        print(slot,'actual',round(100*d['page']['scores']['measured_before']['similarity_median'],2),
            'model page/hue',[round(100*d[k]['scores']['pure_model_after']['similarity_median'],2)for k in ('page','hue')],
            'projection page/hue',[round(100*d[k]['scores']['delta_projection_after']['similarity_median'],2)for k in ('page','hue')])


if __name__=='__main__':
    main()
