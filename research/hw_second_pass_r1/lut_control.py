"""Complete 17^3/33^3 controls on the exact two-pass folds and frozen targets.

Both the frozen published first output and the calibrated 04 model are used.
Q8.8 nodes and Q8 tetrahedral weights; main evaluation uses patch means.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import *
from scipy.linalg import cho_factor, cho_solve
from scipy.spatial.distance import cdist
import argparse
import json


def target_rgb(m, target):
    xyz=m.fs.lab_to_xyz(target,m.fs.D65)
    return np.clip(m.fs.linear_to_srgb(xyz@np.linalg.inv(m.fs.M709).T)*255,0,255)


def kernel(a,b,width):
    return np.exp(-cdist(a,b,'sqeuclidean')/(2*width**2))


def fit(x,y,width=48.,ridge=.03):
    K=kernel(x,x,width)
    alpha=cho_solve(cho_factor(K+ridge*np.eye(len(x)),lower=True),y-x)
    return dict(x=x,alpha=alpha,width=width,ridge=ridge)


def predict(model,x):
    return x+kernel(x,model['x'],model['width'])@model['alpha']


def choose(m,x,target,train,groups):
    rows=[]
    for width in (24.,48.,96.):
        for ridge in (.01,.1,1.):
            errors=[]
            for group in np.unique(groups[train]):
                a=train&(groups!=group);b=train&(groups==group)
                if a.sum()<20 or not b.any():continue
                model=fit(x[a],target_rgb(m,target[a]),width,ridge)
                pred=np.clip(predict(model,x[b]),0,255)
                errors.extend(m.fs.delta_e00(m.fs.lab_from_codes(pred),target[b]))
            rows.append(dict(width=width,ridge=ridge,inner_n=len(errors),inner_median=float(np.median(errors)) if errors else 1e20))
    selected=min(rows,key=lambda r:r['inner_median'])
    return selected,rows


def grid(model,n):
    x=np.stack(np.meshgrid(*([np.linspace(0,255,n)]*3),indexing='ij'),axis=-1).reshape(-1,3)
    y=np.empty_like(x)
    for start in range(0,len(x),2048):
        y[start:start+2048]=np.clip(predict(model,x[start:start+2048]),0,255)
    return np.floor(y.reshape(n,n,n,3)*256+.5).astype(np.uint16)


def apply(table,x,strict_u8=False):
    if strict_u8:x=np.floor(np.clip(x,0,255)+.5)
    n=table.shape[0]
    xx=np.floor(np.clip(x,0,255)*((n-1)/255)*256+.5)/256
    ix=np.minimum(np.floor(xx).astype(int),n-2);frac=xx-ix
    order=np.argsort(-frac,axis=1,kind='stable');delta=np.eye(3,dtype=int)[order]
    vv=np.stack([ix,ix+delta[:,0],ix+delta[:,0]+delta[:,1],ix+1],axis=1)
    ff=np.take_along_axis(frac,order,axis=1)
    weights=np.rint(np.stack([1-ff[:,0],ff[:,0]-ff[:,1],ff[:,1]-ff[:,2],ff[:,2]],axis=1)*256).astype(np.int64)
    assert np.all(weights.sum(1)==256)
    nodes=table[vv[:,:,0],vv[:,:,1],vv[:,:,2]].astype(np.int64)
    output=(nodes*weights[:,:,None]).sum(axis=1)/65536
    return np.floor(output+.5) if strict_u8 else output


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--slots',default=','.join(SLOTS));ap.add_argument('--folds',default=','.join(FOLDS))
    args=ap.parse_args();m=rt.model()
    rows=[]
    for slot in args.slots.split(','):
        for fold in args.folds.split(','):
            d=old.prepare_data(m,slot,fold)
            first=old.Problem(m,slot,d).predict(np.zeros(0))
            for source,x in [('current',first),('04model',m.predict('04',d['x']))]:
                path=rt.LOCAL/f'lut/{slot}/{source}/{fold}.json'
                if path.exists():
                    rows.extend(rt.read(path)['rows']);continue
                groups=d['hue_group'] if fold.startswith('hue') else d['pages']
                choice,inner=choose(m,x,d['target'],d['train'],groups)
                mdl=fit(x[d['train']],target_rgb(m,d['target'][d['train']]),choice['width'],choice['ridge'])
                held=d['held'] if fold!='full' else d['score_mask']
                outputs={};report=[]
                for n in (17,33):
                    table=grid(mdl,n)
                    for strict in (False,True):
                        pred=apply(table,x,strict)
                        error=m.fs.delta_e00(m.fs.lab_from_codes(pred),d['target'])
                        route=f'LUT{n}_{source}'+('_u8means' if strict else '')
                        row=dict(slot=slot,fold=fold,source=source,n=n,route=route,strict_u8means=strict,
                                 prediction_label='电脑预测',score=old.score(error[held],d['baseline'][held]))
                        report.append(row);rows.append(row)
                        key=f'{n}_'+('u8means' if strict else 'main')
                        outputs['prediction_'+key]=pred;outputs['error_'+key]=error
                    outputs[f'nodes_{n}_q8_8']=table
                smooth=np.clip(predict(mdl,x),0,255)
                outputs.update(input=x,target=d['target'],held=held,train=d['train'],baseline=d['baseline'],
                               prediction_smooth=smooth,error_smooth=m.fs.delta_e00(m.fs.lab_from_codes(smooth),d['target']))
                rt.dump(path,dict(slot=slot,fold=fold,source=source,choice=choice,inner=inner,heldout_used_for_choice=False,
                                  rows=report,source_domain='frozen first output' if source=='current' else 'frozen calibrated 04 model without recipe-specific residual'))
                np.savez_compressed(path.with_suffix('.npz'),**outputs)
                print(json.dumps(dict(slot=slot,fold=fold,source=source,width=choice['width'],ridge=choice['ridge'],
                   lut17=round(report[0]['score']['similarity']*100,3),lut33=round(report[2]['score']['similarity']*100,3))),flush=True)
    rt.dump('lut_completed.json',rows)
    rt.finish('lut_control')


if __name__=='__main__':main()
