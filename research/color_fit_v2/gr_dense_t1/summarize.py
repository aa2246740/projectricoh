"""Re-render held-out observations and publish aggregates only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as r
from fit import Fit, fit_path
import csv
import numpy as np


def errors(e, stock):
    out=r.stats(e)
    out['stock04']=r.stats(stock)
    out['similarity']=1-out['median']/out['stock04']['median'] if out['n'] else None
    out['fractions']={f'lt{k}':float((np.asarray(e)<k).mean()) if out['n'] else None for k in (1,2,3)}
    return out


def load(group,slot,level,kind='full',index=None):
    return r.read(fit_path(group,slot,level,kind,index))


def pooled_hue(group,slot,level,iso):
    ee,bb,ss=[],[],[]
    segments=[]
    for index in range(6):
        P=Fit(group,slot,level,'hue',index)
        doc=load(group,slot,level,'hue',index)
        D=r.data(slot,iso);d=P.d
        use=d['held']&d['eval_valid']
        x,target=d['x'][use],d['eval_target'][use]
        new=r.FS.lab_from_codes(P.predict(np.asarray(doc['theta']),x,D))
        old=r.P.prediction(D,D.current,x)
        stock=r.FS.lab_from_codes(d['rgb04'][use])
        e=r.FS.delta_e00(target,new)
        b=r.FS.delta_e00(target,old)
        s=r.FS.delta_e00(target,stock)
        ee.append(e);bb.append(b);ss.append(s)
        segments.append(dict(hue_start=index*60,new=errors(e,s),round5=errors(b,s),
            available=bool(len(e)),grey_gate=doc['checks'][str(iso)]['grey_gate'],
            safety_gate=doc['checks'][str(iso)]['safety']['passes'],
            solver_success=doc['solver']['success']))
    return dict(new=errors(np.concatenate(ee),np.concatenate(ss)),
                round5=errors(np.concatenate(bb),np.concatenate(ss)),segments=segments)


def folds(group,slot,level,iso):
    docs=[load(group,slot,level,'loo',i) for i in range(18)]
    new=[d['scores'][str(iso)]['bastibe_heldout']['new'] for d in docs]
    old=[d['scores'][str(iso)]['bastibe_heldout']['round5'] for d in docs]
    stock=[d['scores'][str(iso)]['bastibe_heldout']['stock04'] for d in docs]
    return dict(new=errors(new,stock),round5=errors(old,stock),
                improved_points=int((np.asarray(new)<old).sum()),
                grey_pass_count=sum(d['checks'][str(iso)]['grey_gate'] for d in docs),
                safety_pass_count=sum(d['checks'][str(iso)]['safety']['passes'] for d in docs),
                converged_count=sum(d['solver']['success'] for d in docs))


def improves(new,old):
    return new['n']>0 and new['median']<old['median'] and new['p90']<=old['p90']


def verified_fits():
    records={}
    for path in sorted((r.LOCAL/'verification').glob('fits_*.json')):
        for rec in r.read(path):
            assert rec['fit'] not in records, 'Overlapping verification batches'
            assert r.sha(r.LOCAL/'fits'/rec['fit'])==rec['sha256'], 'Stale verification'
            assert rec['integer_roundtrip'] and rec['tone_row_roundtrip'] and rec['scores_reproduced']
            records[rec['fit']]=rec
    assert len(records)==312, 'Verify every fit before publishing the summary'
    return records


def comparison_row(group,slot,level,iso,protocol,new,old):
    row=dict(group=group,slot=slot,level=level,iso=iso,protocol=protocol)
    for prefix,metric in [('new',new),('round5',old)]:
        row.update({f'{prefix}_{k}':metric[k] for k in ('n','median','p90','max','similarity')})
    row['similarity_change_pp']=100*(new['similarity']-old['similarity']) if new['n'] else None
    row['heldout_improves_median_and_p90']=improves(new,old) if protocol!='full_observed' else None
    return row


def main():
    groups={};rows=[];failures=[]
    verified=verified_fits()
    for group in ('gr3','gr4_hdf'):
        for slot in ('01','02'):
            key=group+'_'+slot
            item=dict(group=group,slot=slot,levels={})
            for level in ('a','b','c'):
                doc=load(group,slot,level)
                rec=dict(full=dict(scores=doc['scores'],checks=doc['checks'],solver=doc['solver']),
                         validation={},candidate_eligible=False,accepted=False,firmware_ready=False,deployable=False)
                curve=np.asarray(doc['channel_curves_RGB'])
                P=Fit(group,slot,level)
                rec['curve_constraints']=dict(nodes_per_channel=33,min_increment=float(np.diff(curve,axis=1).min()),
                    min_endpoint=float(curve[:,-1].min()),min_value=float(curve.min()),max_value=float(curve.max()),
                    changed_channel_nodes=int(np.count_nonzero(curve-P.q0)),
                    max_second_difference_change=float(abs(np.diff(curve-P.q0,n=2,axis=1)).max()))
                gate_reasons=[]
                if not doc['solver']['success']:gate_reasons.append('full_solver_budget_exhausted')
                for iso in (200,1600):
                    full=doc['checks'][str(iso)]
                    if not full['grey_gate']:gate_reasons.append(f'ISO{iso}_full_grey')
                    if not full['safety']['passes']:gate_reasons.append(f'ISO{iso}_full_safety')
                    if not full['full_chain']['passes_unclipped']:gate_reasons.append(f'ISO{iso}_full_chain')
                    loo=folds(group,slot,level,iso)
                    hue=pooled_hue(group,slot,level,iso)
                    validation=dict(loo=loo,hue=hue)
                    if not improves(loo['new'],loo['round5']):gate_reasons.append(f'ISO{iso}_LOO_not_better')
                    if not improves(hue['new'],hue['round5']):gate_reasons.append(f'ISO{iso}_hue_not_better')
                    if any(s['available'] and not improves(s['new'],s['round5']) for s in hue['segments']):
                        gate_reasons.append(f'ISO{iso}_some_observed_hue_segments_not_better')
                    if group=='gr4_hdf':
                        forward=load(group,slot,level,'image',0)
                        reverse=load(group,slot,level,'image',1)
                        forward_score=forward['scores'][str(iso)]
                        reverse_score=reverse['scores'][str(iso)]
                        validation['image_forward']=dict(new=forward_score['dense_heldout'],
                            round5=forward_score['round5_dense_heldout'],
                            checks=forward['checks'][str(iso)],solver=forward['solver'])
                        validation['image_reverse']=dict(new=reverse_score['bastibe_image_heldout'],
                            round5=reverse_score['round5_bastibe_image_heldout'],
                            checks=reverse['checks'][str(iso)],solver=reverse['solver'],
                            strict_independent_baseline_comparison=False)
                        for direction in ('image_forward','image_reverse'):
                            image=validation[direction]
                            if not improves(image['new'],image['round5']):gate_reasons.append(f'ISO{iso}_{direction}_not_better')
                    else:
                        validation['image_forward']=dict(available=False,
                            reason='The sole bastibe RAW supplies both dense observations and chart anchors')
                    rec['validation'][str(iso)]=validation
                    comparisons=[('full_observed',doc['scores'][str(iso)]['dense_all'],
                                  doc['scores'][str(iso)]['round5_dense_all']),
                                 ('LOO18',loo['new'],loo['round5']),('hue_heldout',hue['new'],hue['round5'])]
                    if group=='gr4_hdf':
                        comparisons.extend((direction,validation[direction]['new'],validation[direction]['round5'])
                                           for direction in ('image_forward','image_reverse'))
                    rows.extend(comparison_row(group,slot,level,iso,*values) for values in comparisons)
                related=[p for p in (r.LOCAL/'fits').glob(f'{group}_{slot}_{level}_*.json')]
                all_docs=[r.read(p) for p in related]
                all_verified=[verified[p.name] for p in related]
                rec['independent_safety_changed_decisions']=[]
                for path,f,vf in zip(related,all_docs,all_verified):
                    for iso,c in vf['checks'].items():
                        old=f['checks'][iso]['safety']
                        if old['passes']!=c['safety']['passes']:
                            rec['independent_safety_changed_decisions'].append(dict(
                                fit=path.name,iso=iso,recorded=old,independent=c['safety']))
                            if not c['safety']['passes']:
                                failures.append(dict(group=group,slot=slot,level=level,kind=f['kind'],
                                    index=f['index'],iso=iso,failed=['independent_0.1deg_safety']))
                for f in all_docs:
                    for iso,checks in f['checks'].items():
                        failed=[]
                        if not checks['grey_gate']:failed.append('grey')
                        if not checks['safety']['passes']:failed.append('safety')
                        if not f['solver']['success']:failed.append('solver')
                        if failed:failures.append(dict(group=group,slot=slot,level=level,kind=f['kind'],
                            index=f['index'],iso=iso,failed=failed))
                if not all(f['solver']['success'] for f in all_docs):gate_reasons.append('some_folds_solver_budget_exhausted')
                if not all(c['grey_gate'] and c['safety']['passes'] for f in all_docs for c in f['checks'].values()):
                    gate_reasons.append('some_folds_grey_or_safety_failed')
                if not all(c['safety']['passes'] for f in all_verified for c in f['checks'].values()):
                    gate_reasons.append('some_folds_independent_0.1deg_safety_failed')
                rec['all_fit_checks']=dict(fit_count=len(all_docs),
                    converged_count=sum(f['solver']['success'] for f in all_docs),
                    nfev_exhausted_count=sum(not f['solver']['success'] for f in all_docs),
                    independent_integer_tone_score_verified_count=len(all_verified),iso={})
                for iso in ('200','1600'):
                    rec['all_fit_checks']['iso'][iso]=dict(
                        grey_pass_count=sum(f['checks'][iso]['grey_gate'] for f in all_docs),
                        recorded_safety_pass_count=sum(f['checks'][iso]['safety']['passes'] for f in all_docs),
                        independent_0p1deg_safety_pass_count=sum(f['checks'][iso]['safety']['passes'] for f in all_verified),
                        max_real_grey_increase=max(f['checks'][iso]['real_grey_max_increase'] for f in all_docs),
                        max_neutral_ramp_change=max(f['checks'][iso]['neutral_ramp_change']['max'] for f in all_docs))
                rec['rejection_reasons']=list(dict.fromkeys(gate_reasons))
                rec['candidate_eligible']=not gate_reasons
                item['levels'][level]=rec
            groups[key]=item
    out=dict(schema='gr-dense-t1-summary/2',public_aggregate_only=True,
        accepted=False,firmware_ready=False,deployable=False,camera_acceptance=False,
        package_created=False,similarity_definition='1 - median(DE00(candidate,target)) / median(DE00(stock04,target))',
        fit_count=len(verified),independent_integer_tone_score_verified_count=len(verified),
        candidate_count=sum(x['candidate_eligible'] for g in groups.values() for x in g['levels'].values()),
        grey_limit=0.05,independent_safety_hue_step_degrees=0.1,
        acceptance_rule='Both ISO levels: strict median reduction and no p90 increase on every available held-out protocol; all grey, safety, integer and full-chain gates pass',
        score_evidence='Observed GR style targets with inferred GXR bridge; host models only',
        baseline=r.read(r.HERE/'baseline_metrics.json'),groups=groups,failed_checks=failures,
        projections={p.stem:r.read(p) for p in sorted(r.HERE.glob('projection_*.json'))})
    r.dump(r.HERE/'metrics.json',out)
    with (r.HERE/'comparison.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(f'summary complete; {out["candidate_count"]} eligible candidates; {len(rows)} paired comparisons; package not generated',flush=True)


if __name__=='__main__':main()
