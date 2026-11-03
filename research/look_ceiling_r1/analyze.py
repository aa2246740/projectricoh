"""Public aggregate metrics and private perceptual error decompositions."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import csv
import collections
import runtime as rt
from runtime import np,ROOT,HERE,LOCAL
from quality import fixtures,diagnostics
from ceiling_model import Problem
from run import training_objective

def arrays(path):
    with np.load(path,allow_pickle=False) as z:return dict(z)

def components(prediction,target):
    values=rt.de00_components(rt.lab_from_codes(prediction),rt.lab_from_codes(target))
    energy=np.mean(values*values,axis=0)
    total=float(energy.sum())
    return dict(mean_squared_de00=total,energy_L=float(energy[0]),energy_C_rotation=float(energy[1]),
        energy_H_orthogonal=float(energy[2]),share_percent=(energy/total*100).tolist() if total>1e-20 else [0.,0.,0.],
        definition='Orthogonal DE00 residual squared means. Rotation is folded into the last two components. Medians are not additive.')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args()
    public=[];csv_rows=[];ranges=[];phocus=[];current_quality=[];quality_rows=[]
    train=arrays(LOCAL/'samples_train.npz')['x'];syn=arrays(LOCAL/'samples_synthetic.npz')['x']
    train_keys=set(map(tuple,train));strict=np.array([tuple(row) not in train_keys for row in syn])
    rt.dump('split_audit.json',dict(label='电脑预测',train_n=len(train),synthetic_n=len(syn),
        duplicate_train_synthetic=int((~strict).sum()),strict_synthetic_n=int(strict.sum()),
        training_and_photo_paths_disjoint=True,main_scores_keep_published_split=True))
    model,_,_=rt.upstream.camera_model()
    metas=sorted(LOCAL.glob('target_[0-9][0-9].json'))
    for path in metas:
        meta=rt.read(path);index=meta['index'];data=arrays(path.with_suffix('.npz'))
        c=rt.camera_for_unit(meta.get('camera_ui',0));gradients,ring=fixtures(c)
        entry=bytes.fromhex(meta['entry_hex'])
        cq=diagnostics(c,lambda x,rounded:model.predict(entry,x,quantize=rounded,bw_chroma='zero'),gradients,ring)
        current_quality.append(dict(index=index,name=meta['name'],quality=cq))
        groups={key:arrays(LOCAL/meta.get('group_files',{}).get(key,'samples_'+key+'.npz'))
                for key in ('train','synthetic','a12-50','a12-28','mount-a12')}
        train_set=set(map(tuple,groups['train']['x']))
        current_objective=training_objective(data['train_base'],data['train_published'],data['train_target'],groups['train']['sw'])
        synkeep=np.array([tuple(row) not in train_set for row in groups['synthetic']['x']])
        for fitpath in sorted((LOCAL/'fits'/f'{index:02d}').glob('L*.json')):
            doc=rt.read(fitpath);pred=arrays(fitpath.with_suffix('.npz'))
            if 'hue_defined_intervals' not in doc['quality'] and (doc['config']['level']<=1 or doc['config'].get('full_fields')):
                P=Problem(c,groups['train']['x'],data['train_target'],groups['train']['sw'],doc['config'])
                state=P.unpack(doc['parameters'])
                doc['quality']=diagnostics(c,lambda xx,r:P.predict_state(state,xx,r),gradients,ring)
            scores=doc['scores'].copy()
            scores['synthetic_strict']=rt.score(data['synthetic_base'][synkeep],pred['synthetic'][synkeep],data['synthetic_target'][synkeep])
            overfit={};train_improved=False
            if doc.get('parent'):
                parent=rt.read(fitpath.parent/(doc['parent']+'.json'))
                train_improved=doc['train_objective']<parent['train_objective']-1e-10
                overfit={g:bool(train_improved and scores[g]['de00']['median']>=parent['scores'][g]['de00']['median']-1e-10)
                    for g in ('synthetic','a12-50','mount-a12') if scores[g] is not None}
            row=dict(label='电脑预测',index=index,name=meta['name'],family=meta['family'],
                builtin_slot=meta.get('builtin_slot'),unit=meta.get('unit','shared-50mm-fit'),
                primary=bool(doc['config']['level']<=1 or doc['config'].get('full_fields')),
                config=doc['config'],scores=scores,quality=doc['quality'],
                parameter_quantization_de00=doc['parameter_quantization_de00'],
                parent=doc['parent'],gain_over_parent_pp=doc['gain_over_parent_pp'],
                overfit_flags=overfit,photo_synthetic_gap_pp=doc['photo_synthetic_gap_pp'],
                overfit_definition='Training weighted integer DE00 squared improved, held-out median DE00 did not. Diagnostic flag, not proof of cause.',
                training_objective_improved_over_parent=train_improved,
                overfit_vs_current_flags={g:bool(doc['train_objective']<current_objective-1e-10 and
                    scores[g]['de00']['median']>=meta['scores'][g]['de00']['median']-1e-10)
                    for g in ('synthetic','a12-50','mount-a12') if scores[g] is not None},
                solver_converged=all(a['success'] for a in doc['solver_attempts']),
                solver_nfev=sum(a['nfev'] for a in doc['solver_attempts']),selection=doc['selection'],
                added_reverse_hue_intervals=doc['quality']['reverse_hue_intervals']-cq['reverse_hue_intervals'],
                current_published_scores=meta['scores'],current_quality=cq,
                parameters_file=str(fitpath.relative_to(HERE)),hardware_acceptance=False)
            public.append(row)
            for gradient,v in row['quality']['gradients'].items():
                quality_rows.append(dict(label='电脑预测',index=index,name=meta['name'],unit=row['unit'],
                    variant=doc['config']['key'],primary=row['primary'],gradient=gradient,
                    continuous_step_max_de00=v['continuous_step_de00']['max'],integer_step_max_de00=v['integer_step_de00']['max'],
                    integer_step_p95_de00=v['integer_step_de00']['p95'],channel_jump_max=v['adjacent_integer_code_jump_max'],
                    longest_identical_output_run=v['longest_identical_output_run'],negative_lightness_steps=v['negative_lightness_steps'],
                    hue_step_max_deg=v['hue_step_max_deg'],reverse_hue_intervals=row['quality']['reverse_hue_intervals'],
                    hue_monotone=row['quality'].get('hue_monotone'),hue_defined_intervals=row['quality'].get('hue_defined_intervals'),
                    quantization_median_de00=v['quantization_de00']['median']))
            for group,s in scores.items():
                if s is None:continue
                csv_rows.append(dict(label='电脑预测',index=index,name=meta['name'],unit=meta.get('unit','shared'),
                    variant=doc['config']['key'],layer=doc['config']['level'],group=group,
                    primary=row['primary'],
                    n=s['de00']['n'],similarity_percent=s['similarity_percent'],median_de00=s['de00']['median'],
                    p95_de00=s['de00']['p95'],max_de00=s['de00']['max'],baseline_median_de00=s['baseline_de00']['median'],
                    train_similarity_percent=scores['train']['similarity_percent'],
                    reverse_hue_intervals=doc['quality']['reverse_hue_intervals'],
                    max_gradient_integer_step_de00=doc['quality']['max_integer_gradient_step_de00'],
                    output_clipped_share=float(np.any(((pred['synthetic'][synkeep] if group=='synthetic_strict' else pred[group])<=0)|
                        ((pred['synthetic'][synkeep] if group=='synthetic_strict' else pred[group])>=255),axis=1).mean()),
                    overfit=overfit.get(group),overfit_vs_current=row['overfit_vs_current_flags'].get(group),solver_converged=row['solver_converged']))
            if index in (4,5):
                for group in ('train','synthetic','a12-50','mount-a12'):
                    if group not in pred:continue
                    target=data[group+'_target'];base=data[group+'_base'];prediction=pred[group]
                    labs=rt.lab_from_codes(base);chroma=np.linalg.norm(labs[:,1:],axis=1)
                    hue=np.degrees(np.arctan2(labs[:,2],labs[:,1]))%360
                    masks=dict(all=np.ones(len(base),bool),near_neutral=chroma<5,shadow=labs[:,0]<25,
                        highlight=labs[:,0]>75,saturated=chroma>40,
                        skin_region=(hue>=20)&(hue<=70)&(chroma>=5)&(chroma<=45)&(labs[:,0]>=20)&(labs[:,0]<=85))
                    for name,mask in masks.items():
                        if not mask.any():continue
                        phocus.append(dict(index=index,name=meta['name'],variant=doc['config']['key'],group=group,
                            subset=name,overlapping_subsets=True,baseline=components(base[mask],target[mask]),
                            residual=components(prediction[mask],target[mask]),
                            score=rt.score(base[mask],prediction[mask],target[mask])))
    for index in sorted(set(r['index'] for r in public)):
        for layer in range(5):
            rr=[r for r in public if r['index']==index and r['config']['level']==layer and r['primary']]
            if not rr:continue
            for group in ('synthetic','synthetic_strict','a12-50','mount-a12'):
                ss=[(r,r['scores'][group]) for r in rr if r['scores'][group] is not None and r['scores'][group]['similarity_percent'] is not None]
                if not ss:continue
                lo=min(ss,key=lambda a:a[1]['similarity_percent']);hi=max(ss,key=lambda a:a[1]['similarity_percent'])
                ranges.append(dict(index=index,name=rr[0]['name'],layer=layer,group=group,
                    minimum_percent=lo[1]['similarity_percent'],maximum_percent=hi[1]['similarity_percent'],
                    minimum_variant=lo[0]['config']['key'],maximum_variant=hi[0]['config']['key'],
                    variants=len(ss),interpretation='Observed hypotheses, not confidence interval or exhaustive physical bound'))
    rt.dump('results.json',dict(label='电脑预测',fits=public,fit_count=len(public),
        primary_fit_count=sum(r['primary'] for r in public),target_profiles=len(metas),
        complete_expected_primary_fit_count=51*30,partial=args.partial,hypothesis_ranges=ranges))
    rt.dump('current_quality.json',current_quality)
    rt.dump('primary_quality.json',{f'{r["index"]:02d}/{r["config"]["key"]}':r['quality'] for r in public if r['primary']})
    rt.dump('phocus_components.json',phocus)
    with (HERE/'scores.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(csv_rows[0]));writer.writeheader();writer.writerows(csv_rows)
    with (HERE/'hypothesis_ranges.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(ranges[0]));writer.writeheader();writer.writerows(ranges)
    with (HERE/'quality.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(quality_rows[0]));writer.writeheader();writer.writerows(quality_rows)
    print('Aggregated',len(public),'fits',len(csv_rows),'score rows',flush=True)
    rt.finish('analysis')

if __name__=='__main__':main()
