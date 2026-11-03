"""Nested group CV: smoothness is selected using training patches only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import LOCAL, guard, read, dump
from prepare import modules, rgb_to_ycc, ycc_to_rgb, SLOTS
from simulate import fit, predict, omitted, lut_predict, target_rgb, stats, error_stats, lut_array
import numpy as np


def inner_score(model, x, yg, target, groups, training, fs):
    yy=np.empty((int(training.sum()),12))
    positions=np.flatnonzero(training)
    pred=np.full_like(yg,np.nan)
    for g in np.unique(groups[training]):
        jj=np.flatnonzero((groups==g)&training)
        pred[jj]=yg[jj]-np.linalg.solve(model['q'][np.ix_(jj,jj)],model['a'][jj])
    return [float(np.median(fs.delta_e00(fs.lab_from_codes(np.clip(
                ycc_to_rgb(pred[training,j*3:j*3+3]),0,255)),target[training,j])))
            for j in range(4)]


def main():
    guard()
    cm,_,_=modules();fs=cm.helper('fs')
    ds=read('research/body_lut/local/dataset.json');rr=ds['rows'];nn=len(rr)
    x=np.asarray([r['ycc'] for r in rr]);groups=np.array([r['group'] for r in rr])
    target=np.array([[r['targets'][s] for s in SLOTS] for r in rr])
    yg=rgb_to_ycc(np.clip(target_rgb(fs,target),0,255)).reshape(nn,12)
    rgb=np.asarray([r['rgb'] for r in rr]);lab=fs.lab_from_codes(rgb)
    base=np.stack([fs.delta_e00(lab,target[:,j]) for j in range(4)],axis=1)
    isp=np.array([[r['isp_rgb'][s] for s in SLOTS] for r in rr])
    ispde=np.stack([fs.delta_e00(fs.lab_from_codes(isp[:,j]),target[:,j]) for j in range(4)],axis=1)
    old=read('research/body_lut/local/results.json')
    candidates={(w,r):fit(x,yg,w,r) for w in (24.,48.,96.) for r in (.01,.1,1.)}
    # Verify deletion algebra against a genuinely refitted model on the complement.
    ii=np.flatnonzero(groups==groups[0]);keep=np.setdiff1d(np.arange(nn),ii)
    one=candidates[(24.,.01)]
    direct=fit(x[keep],yg[keep],24.,.01)
    algebra_error=float(np.max(np.abs(predict(omitted(one,ii),x[ii])-predict(direct,x[ii]))))
    assert algebra_error<1e-8
    report={'method':'outer group holdout; choose width/ridge by inner grouped-LOO median DE00 on training rows',
        'deletion_matches_refit_max_code_error':algebra_error,'candidates':[list(k) for k in candidates],
        'scores':{},'folds':{},'deployment_parameters':{}}
    for mode in ('patch_loo','hue_30deg','screen_to_physical'):
        held=np.zeros(nn,bool)
        outputs={k:np.full((nn,12),np.nan) for k in ['smooth']+
            [f'n{n}_{v}' for n in (9,17,33) for v in ('float','fixed16','fixed8')]}
        notes=[]
        for oldfold in old['folds'][mode]:
            ii=np.array(oldfold['test'],int);training=np.ones(nn,bool);training[ii]=False
            adjusted=[];scores=[]
            for key,full in candidates.items():
                left=omitted(full,ii)
                # Schur complement gives the exact inverse kernel matrix on the training subset.
                q=full['q'];left['q']=q-q[:,ii]@np.linalg.solve(q[np.ix_(ii,ii)],q[ii])
                scores.append(inner_score(left,x,yg,target,groups,training,fs))
                adjusted.append(left)
            choices=np.argmin(scores,axis=0)
            for j,choice in enumerate(choices):
                left=adjusted[choice]
                outputs['smooth'][ii,j*3:j*3+3]=predict(left,x[ii])[:,j*3:j*3+3]
                for n in (9,17,33):
                    outputs[f'n{n}_float'][ii,j*3:j*3+3]=lut_predict(left,x[ii],n)[:,j*3:j*3+3]
                    for bits in (8,16):
                        outputs[f'n{n}_fixed{bits}'][ii,j*3:j*3+3]=lut_predict(left,x[ii],n,True,bits)[:,j*3:j*3+3]
            held[ii]=True
            notes.append({'test':ii.tolist(),'parameters':{s:list(candidates)[choices[j]] for j,s in enumerate(SLOTS)},
                'inner_training_median_de00':{s:float(scores[choices[j]][j]) for j,s in enumerate(SLOTS)}})
        report['folds'][mode]=notes
        report['scores'][mode]={name:{s:stats(fs,yy[held,j*3:j*3+3],target[held,j],base[held,j])
            for j,s in enumerate(SLOTS)} for name,yy in outputs.items()}
        report['scores'][mode]['frozen_isp_model']={s:error_stats(ispde[held,j],base[held,j]) for j,s in enumerate(SLOTS)}
        # Domain-specific views expose duplicate/domain weighting, without changing fitting.
        report['scores'][mode]['n17_fixed16_by_domain']={domain:{s:stats(fs,
            outputs['n17_fixed16'][sel,j*3:j*3+3],target[sel,j],base[sel,j]) for j,s in enumerate(SLOTS)}
            for domain in ('screen','physical') if np.any(sel:=held & np.array([r['domain']==domain for r in rr]))}
        np.savez(LOCAL/f'nested_predictions_{mode}.npz',mask=held,target=target,baseline=base,isp_de=ispde,**outputs)
        print('nested',mode,{s:round(report['scores'][mode]['n17_fixed16'][s]['similarity']*100,2) for s in SLOTS},flush=True)
    fullscores=[inner_score(m,x,yg,target,groups,np.ones(nn,bool),fs) for m in candidates.values()]
    chosen=np.argmin(fullscores,axis=0)
    # A single deployed LUT per slot, trained on all rows, after training-only parameter selection.
    tables={n:[] for n in (9,17,33)}
    for j,s in enumerate(SLOTS):
        key=list(candidates)[chosen[j]]
        report['deployment_parameters'][s]=list(key)
        model=candidates[key]
        np.savez(LOCAL/f'deploy_model_{s}.npz',x=x,a=model['a'],width=key[0],ridge=key[1])
        for n in (9,17,33):
            tables[n].append(lut_array(model,n)[:,:,:,j])
    for n,tt in tables.items():
        table=np.stack(tt,axis=3)
        np.save(LOCAL/f'deploy_lut{n}_float.npy',table)
        np.save(LOCAL/f'deploy_lut{n}_q8_8.npy',np.floor(table*256+.5).astype('>u2'))
    dump('nested_results.json',report)


if __name__=='__main__':
    main()
