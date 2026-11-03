"""Held-out actual horizontal pairs, using the nested-CV parameters already selected."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import LOCAL,guard,read,dump
from prepare import modules,rgb_to_ycc,ycc_to_rgb,SLOTS
from simulate import fit,omitted,lut_predict,target_rgb,error_stats
import numpy as np


def main():
    guard();cm,_,_=modules();fs=cm.helper('fs')
    rr=read('research/body_lut/local/dataset.json')['rows'];nn=len(rr)
    nested=read('research/body_lut/local/nested_results.json')
    x=np.array([r['ycc'] for r in rr]);target=np.array([[r['targets'][s] for s in SLOTS] for r in rr])
    yg=rgb_to_ycc(np.clip(target_rgb(fs,target),0,255)).reshape(nn,12)
    rgb=np.array([r['rgb'] for r in rr]);lab=fs.lab_from_codes(rgb)
    base=np.stack([fs.delta_e00(lab,target[:,j]) for j in range(4)],axis=1)
    models={tuple(k):fit(x,yg,*k) for k in nested['candidates']}
    pairs=np.asarray([r['pairs_rgb'] for r in rr])
    ins=np.clip(np.floor(rgb_to_ycc(pairs)+.5),0,255)
    ins[:,:,:,1:]=np.floor(ins[:,:,:,1:].mean(axis=2,keepdims=True)+.5)
    report={'scope':'24 real adjacent horizontal pixel pairs per patch; mean decoded RGB after integer 4:2:2 processing',
        'baseline':'same trimmed patch-mean 04 baseline as the other tables', 'scores':{}}
    for mode,folds in nested['folds'].items():
        out={n:np.full((nn,4,3),np.nan) for n in (9,17,33)}
        held=np.zeros(nn,bool)
        for fold in folds:
            ii=np.asarray(fold['test'],int);held[ii]=True
            models_left={k:omitted(models[k],ii) for k in {tuple(k) for k in fold['parameters'].values()}}
            flat=ins[ii].reshape(-1,3)
            for j,s in enumerate(SLOTS):
                model=models_left[tuple(fold['parameters'][s])]
                for n in (9,17,33):
                    yy=lut_predict(model,flat,n,True,16,False)[:,j*3:j*3+3].reshape(len(ii),24,2,3)
                    yy[:,:,:,1:]=yy[:,:,:,1:].mean(axis=2,keepdims=True)
                    yy=np.floor(yy+.5)
                    out[n][ii,j]=np.clip(ycc_to_rgb(yy),0,255).mean(axis=(1,2))
        report['scores'][mode]={f'n{n}':{s:error_stats(fs.delta_e00(fs.lab_from_codes(pred[held,j]),
            target[held,j]),base[held,j]) for j,s in enumerate(SLOTS)} for n,pred in out.items()}
        np.savez(LOCAL/f'nested422_predictions_{mode}.npz',mask=held,target=target,baseline=base,
                 **{f'n{n}_rgb':v for n,v in out.items()})
        print('actual422',mode,{s:round(v['similarity']*100,2) for s,v in report['scores'][mode]['n33'].items()},flush=True)
    dump('nested422_results.json',report)


if __name__=='__main__':
    main()
