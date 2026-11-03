"""RGB software LUT and residual LUT, with 8-bit I/O and Q8.8 nodes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from scipy.linalg import cho_factor,cho_solve
from scipy.spatial.distance import cdist
import argparse
from style import Dense,PAIRS
from scipy.interpolate import RBFInterpolator


def kernel(a,b,width):
    return np.exp(-cdist(np.asarray(a),np.asarray(b),'sqeuclidean')/(2*width**2))


def fit(x,y,width=48.,ridge=.03):
    x=np.asarray(x);K=kernel(x,x,width)
    alpha=cho_solve(cho_factor(K+ridge*np.eye(len(x)),lower=True),y-x)
    return dict(x=x,alpha=alpha,width=width,ridge=ridge)


def predict(model,x):
    return x+kernel(x,model['x'],model['width'])@model['alpha']


def vertices(x,n,fixed=True):
    # Same tetrahedral ordering and fixed weights as body_lut/simulate.py.
    xx=np.clip(np.asarray(x),0,255)*((n-1)/255)
    if fixed:xx=np.floor(xx*256+.5)/256
    ix=np.minimum(np.floor(xx).astype(int),n-2);frac=xx-ix
    order=np.argsort(-frac,axis=1,kind='stable');delta=np.eye(3,dtype=int)[order]
    vv=np.stack([ix,ix+delta[:,0],ix+delta[:,0]+delta[:,1],ix+1],axis=1)
    ff=np.take_along_axis(frac,order,axis=1)
    w=np.stack([1-ff[:,0],ff[:,0]-ff[:,1],ff[:,1]-ff[:,2],ff[:,2]],axis=1)
    if fixed:w=np.rint(w*256).astype(np.int64)
    assert np.max(abs(w.sum(axis=1)-(256 if fixed else 1)))<1e-8
    return vv,w


def apply(model,x,n):
    x=np.floor(np.clip(x,0,255)+.5)
    vv,w=vertices(x,n)
    v=vv.reshape(-1,3)*(255/(n-1))
    unique,inv=np.unique(v,axis=0,return_inverse=True)
    y=np.clip(predict(model,unique),0,255)
    nodes=np.floor(y*256+.5).astype(np.int64)[inv].reshape(len(x),4,3)
    numer=(nodes*w[:,:,None]).sum(axis=1)
    return np.clip((numer+32768)//65536,0,255).astype(np.uint8)


def choose(x,target,train,groups):
    grid=[(w,r) for w in (24.,48.,96.) for r in (.01,.1,1.)]
    records=[]
    for width,ridge in grid:
        errors=[]
        for group in np.unique(groups[train]):
            inner=train & (groups!=group);held=train & (groups==group)
            if inner.sum()<30 or not held.any():continue
            model=fit(x[inner],np.clip(rt.rgb(target[inner]),0,255),width,ridge)
            pred=np.clip(predict(model,x[held]),0,255)
            errors.extend(rt.cm.delta_e00(rt.lab(pred),target[held]))
        records.append(dict(width=width,ridge=ridge,error=rt.stats(errors)))
    eligible=[r for r in records if r['error']['n']]
    choice=min(eligible,key=lambda r:r['error']['median']) if eligible else dict(width=48.,ridge=.03)
    return choice,records


def r7():
    result=[]
    for slot,style in [('01','positive'),('02','negative')]:
        d=rt.arrays(PAIRS[style]+'/local/fit/data.npz')
        x=np.floor(np.clip(d['observed_rgb'],0,255)+.5)
        target=d['new_target'];valid=d['supported']
        base=rt.cm.delta_e00(rt.lab(d['base_rgb']),target)
        for scheme,groups in [('page',d['pages']),('hue',d['hue_group'])]:
            predictions={n:np.zeros_like(x) for n in (17,33)}
            continuous=np.zeros_like(x);choices=[]
            for group in np.unique(groups):
                train=(groups!=group)&valid&d['fit_usable'];held=(groups==group)&valid
                choice,inner=choose(x,target,train,groups)
                mdl=fit(x[train],np.clip(rt.rgb(target[train]),0,255),choice['width'],choice['ridge'])
                for n in predictions:predictions[n][held]=apply(mdl,x[held],n)
                continuous[held]=np.clip(predict(mdl,x[held]),0,255)
                choices.append(dict(fold=int(group),train=int(train.sum()),test=int(held.sum()),choice=choice,inner=inner))
            for n,pred in list(predictions.items())+[('float',continuous)]:
                error=rt.cm.delta_e00(rt.lab(pred[valid]),target[valid])
                row=dict(dataset='r7_actual_old_recipe_JPEG',slot=slot,scheme=scheme,route=f'LUT{n}',
                         **rt.score(error,base[valid]),camera_acceptance=False)
                result.append(row)
                print('r7',slot,scheme,n,round(row['similarity_median']*100,2),flush=True)
                np.savez_compressed(rt.LOCAL/f'lut/r7_{slot}_{scheme}_{n}.npz',prediction=pred[valid],
                                    target=target[valid],error=error,baseline=base[valid],index=np.flatnonzero(valid))
            rt.dump(f'lut/r7_{slot}_{scheme}_selection.json',choices)
    rt.dump('lut/r7_summary.json',result)


def prepare_body():
    from isp import model
    m=model()
    ds=rt.read('research/body_lut/local/dataset.json');rows=ds['rows']
    frames={}
    for source in ('research/closed_loop/local/dry_ring_measurement.json','research/closed_loop/local/dry_2e_measurement.json'):
        for f in rt.read(source)['frames']:
            if f['slot']=='04':frames[f['id']]=f
    matrix={stem:rt.read(f'research/matrix_test_onbody/local/{stem}.json') for stem in ('R8051171','R8051174')}
    inputs=np.zeros((len(rows),3));bad=np.ones(len(rows),bool);raws=np.zeros_like(inputs)
    for item in ds['frames']:
        ident=item['id'];take=np.flatnonzero(np.array([r['frame']==ident for r in rows]))
        if ident in frames:
            f=frames[ident];look={str(p['label']):i for i,p in enumerate(f['patches'])}
            raw=np.array([f['raw_wb'][look[r['label']]] for r in np.array(rows,dtype=object)[take]])
        else:
            look={str(p['id']):p for p in matrix[ident]['samples']['30']}
            raw=np.array([look[r['label']]['cam_wb'] for r in np.array(rows,dtype=object)[take]])
        xx,bb=m.inverse04(np.array([rows[i]['rgb'] for i in take]),raw)
        inputs[take]=xx;bad[take]=bb;raws[take]=raw
        print('body inverse',ident,len(take),int(bb.sum()),flush=True)
    base_rgb=np.array([r['rgb'] for r in rows]);base_lab=rt.lab(base_rgb)
    target=[];supported=[]
    for style in ('positive','negative'):
        tt,ss,_=Dense(style).target(inputs,base_lab)
        target.append(tt);supported.append(ss&~bad)
    out=dict(x=inputs,raw=raws,base_rgb=base_rgb,targets=np.stack(target,axis=1),supported=np.stack(supported,axis=1),
             groups=np.array([r['group'] for r in rows]),domain=np.array([r['domain'] for r in rows]),
             frames=np.array([r['frame'] for r in rows]),hue=(np.array([r['dng_hue'] for r in rows])//30).astype(int),
             pairs=np.array([r['pairs_rgb'] for r in rows]))
    np.savez_compressed(rt.LOCAL/'lut/body_data.npz',**out)
    rt.dump('lut/body_source_protocol.json',dict(n=len(rows),same_frame_04_and_RAW=True,
              sensor_bridge='same frozen common-white ColorMatrix approximation as target.py',
              gray_anchor='Standard-only 118',source='body_lut/local/dataset.json',new_GR_IV_targets=True,
              actual_GR_IV_same_scene_pixels=False,no_camera_acceptance=True))


def body():
    path=rt.LOCAL/'lut/body_data.npz'
    if not path.exists():prepare_body()
    d=rt.arrays(path);base_rgb=d['base_rgb'];x=np.floor(base_rgb+.5)
    result=[]
    for k,slot in enumerate(('01','02')):
        target=d['targets'][:,k];valid=d['supported'][:,k]
        baseline=rt.cm.delta_e00(rt.lab(base_rgb),target)
        for scheme in ('patch','hue','screen_to_physical'):
            predictions={n:np.zeros_like(x) for n in (17,33)};smooth=np.zeros_like(x);use=np.zeros(len(x),bool)
            pixel_predictions={n:np.zeros_like(x) for n in (17,33)}
            groups=d['groups'] if scheme=='patch' else d['hue'] if scheme=='hue' else np.array(['physical'])
            for group in np.unique(groups):
                held=(d['domain']=='physical')&valid if scheme=='screen_to_physical' else (groups==group)&valid
                train=(d['domain']=='screen')&valid if scheme=='screen_to_physical' else (groups!=group)&valid
                if not held.any():continue
                mdl=fit(x[train],np.clip(rt.rgb(target[train]),0,255),48.,.03)
                pixels=d['pairs'][held].reshape(-1,3)
                for n in predictions:
                    predictions[n][held]=apply(mdl,x[held],n)
                    pixel_predictions[n][held]=apply(mdl,pixels,n).reshape(int(held.sum()),-1,3).mean(1)
                smooth[held]=np.clip(predict(mdl,x[held]),0,255);use|=held
            for n,pred in list(predictions.items())+[('float',smooth)]:
                error=rt.cm.delta_e00(rt.lab(pred[use]),target[use])
                row=dict(dataset='same_frame_04',slot=slot,scheme=scheme,route=f'LUT{n}',**rt.score(error,baseline[use]),
                         fixed_width=48.,fixed_ridge=.03,unsupported=int((~valid).sum()))
                result.append(row)
                np.savez_compressed(rt.LOCAL/f'lut/body_{slot}_{scheme}_{n}.npz',prediction=pred[use],target=target[use],
                                    error=error,baseline=baseline[use],index=np.flatnonzero(use))
                print('body',slot,scheme,n,round(row['similarity_median']*100,2),'n',row['error']['n'],flush=True)
            for n,pred in pixel_predictions.items():
                error=rt.cm.delta_e00(rt.lab(pred[use]),target[use])
                row=dict(dataset='same_frame_04',slot=slot,scheme=scheme,route=f'pixel_LUT{n}',**rt.score(error,baseline[use]),
                         fixed_width=48.,fixed_ridge=.03,unsupported=int((~valid).sum()),actual_RGB_pixels_per_patch=48)
                result.append(row)
                np.savez_compressed(rt.LOCAL/f'lut/body_{slot}_{scheme}_pixel{n}.npz',prediction=pred[use],target=target[use],
                                    error=error,baseline=baseline[use],index=np.flatnonzero(use))
                print('body pixels',slot,scheme,n,round(row['similarity_median']*100,2),flush=True)
        mdl=fit(x[valid],np.clip(rt.rgb(target[valid]),0,255),48.,.03)
        for n in (17,33):
            nodes=np.stack(np.meshgrid(*([np.linspace(0,255,n)]*3),indexing='ij'),axis=-1).reshape(-1,3)
            values=np.empty_like(nodes)
            for start in range(0,len(nodes),2048):values[start:start+2048]=np.clip(predict(mdl,nodes[start:start+2048]),0,255)
            np.savez_compressed(rt.LOCAL/f'lut/host_only_RGB_Q8_8_{slot}_{n}.npz',
                                nodes=np.floor(values*256+.5).astype(np.uint16).reshape(n,n,n,3))
    rt.dump('lut/body_summary.json',result)


def hybrid():
    from isp import model,fold_data,candidate_predict
    m=model()
    result=[]
    for slot in ('01','02'):
        for scheme,folds in [('page',[f'page{i}' for i in range(1,7)]),('hue',[f'hue{i}' for i in range(3)])]:
            pooled={n:[] for n in (9,17)};baselines=[];base_errors=[]
            selections=[]
            for fold in folds:
                options={route:rt.arrays(rt.LOCAL/f'isp/{slot}/{route}/{fold}.npz') for route in ('D2','D4','D8','safe_all')}
                dd=fold_data(m,slot,fold)
                pred=np.clip(candidate_predict(m,slot,dd['current'],dd['x'])+dd['bias'],0,255)
                err=rt.cm.delta_e00(rt.lab(pred),dd['target'])
                options['current']=dict(prediction=pred,error=err,target=dd['target'],train=dd['train'],held=dd['held'],baseline=dd['baseline'])
                training_scores={name:float(np.mean(value['error'][value['train']]**2)) for name,value in options.items()}
                selected=min(training_scores,key=training_scores.get)
                d=options[selected]
                selections.append(dict(fold=fold,selected=selected,training_mean_squared_DE00=training_scores,heldout_used=False))
                x=np.floor(d['prediction']+.5);target=d['target'];train=d['train'];held=d['held']
                data=rt.arrays(PAIRS['positive' if slot=='01' else 'negative']+'/local/fit/data.npz')
                groups=data['pages'] if scheme=='page' else data['hue_group']
                choice,inner=choose(x,target,train,groups)
                mdl=fit(x[train],np.clip(rt.rgb(target[train]),0,255),choice['width'],choice['ridge'])
                for n in pooled:
                    pred=apply(mdl,x[held],n);error=rt.cm.delta_e00(rt.lab(pred),target[held]);pooled[n].extend(error)
                    np.savez_compressed(rt.LOCAL/f'lut/hybrid_{slot}_{fold}_{n}.npz',prediction=pred,target=target[held],
                                       error=error,baseline=d['baseline'][held])
                baselines.extend(d['baseline'][held]);base_errors.extend(d['error'][held])
                rt.dump(f'lut/hybrid_{slot}_{fold}_selection.json',dict(choice=choice,inner=inner))
            for n,error in pooled.items():
                row=dict(slot=slot,scheme=scheme,route=f'best_safe_LUT{n}',**rt.score(error,baselines),
                         ISP_without_LUT=rt.score(base_errors,baselines),model_only=True)
                result.append(row);print('hybrid',slot,scheme,n,round(row['similarity_median']*100,2),flush=True)
            rt.dump(f'lut/hybrid_{slot}_{scheme}_ISP_selection.json',selections)
    rt.dump('lut/hybrid_summary.json',result)


def dense_oracle():
    """Representation experiment; it deliberately assumes the sensor bridge is exact."""
    from isp import model
    from style import relative
    m=model();result=[]
    for slot,style in [('01','positive'),('02','negative')]:
        d=Dense(style);a=d.a
        x=a['raw_wb']@np.linalg.inv(d.T).T*(320/d.anchor)
        base=m.predict('04',x);target=relative(rt.lab(base),a['standard'],a[style])
        valid=(x>0).all(1)&(x<4095).all(1)&(base>2).all(1)&(base<253).all(1)
        targetrgb=np.clip(rt.rgb(target),0,255)
        baseline=rt.cm.delta_e00(rt.lab(base),target)
        hue=(np.degrees(np.arctan2(a['standard'][:,2],a['standard'][:,1]))%360//15).astype(int)%3
        for scheme,groups in [('page',a['band']),('hue',hue)]:
            pred={n:np.zeros_like(base) for n in (17,33)};direct=np.zeros_like(base);use=np.zeros(len(base),bool)
            relative_error=[]
            for group in np.unique(groups):
                held=(groups==group)&valid
                keys={tuple(q) for q in np.round(a['feature'][held],9)}
                train=np.array([not h and tuple(q) not in keys for h,q in zip(groups==group,np.round(a['feature'],9))])&valid
                # Preserve the exact no-extrapolation RAW support of target.py.
                from style import Function,feature,grouped
                hull=Function(a['feature'][train],np.c_[a['standard'][train],a[style][train]])
                yy,supported,_=hull(a['feature'][held]);indices=np.flatnonzero(held)[supported]
                expected=relative(rt.lab(base[indices]),yy[supported,:3],yy[supported,3:])
                relative_error.extend(rt.cm.delta_e00(expected,target[indices]))
                xx,values=grouped(base[train]/64.,targetrgb[train]-base[train])
                f=RBFInterpolator(xx,values,neighbors=64,smoothing=.001,kernel='thin_plate_spline',degree=1)
                direct[indices]=np.clip(base[indices]+f(base[indices]/64.),0,255)
                for n in pred:
                    query=np.floor(base[indices]+.5);vv,w=vertices(query,n)
                    nodes=vv.reshape(-1,3)*(255/(n-1));unique,inv=np.unique(nodes,axis=0,return_inverse=True)
                    nodeout=np.clip(unique+f(unique/64.),0,255)
                    nodeout=np.floor(nodeout*256+.5).astype(np.int64)[inv].reshape(len(indices),4,3)
                    pred[n][indices]=np.clip(((nodeout*w[:,:,None]).sum(1)+32768)//65536,0,255)
                use[indices]=True
            for n,value in list(pred.items())+[('float',direct)]:
                error=rt.cm.delta_e00(rt.lab(value[use]),target[use])
                row=dict(slot=slot,scheme=scheme,route=f'dense_oracle_LUT{n}',**rt.score(error,baseline[use]),
                         assumes_exact_sensor_bridge=True,actual_GXR_pixels=False,unsupported=int((~use).sum()),
                         sampling_relative_error=rt.stats(relative_error),full_points=len(base))
                result.append(row);print('dense oracle',slot,scheme,n,round(row['similarity_median']*100,2),flush=True)
                np.savez_compressed(rt.LOCAL/f'lut/dense_{slot}_{scheme}_{n}.npz',prediction=value[use],target=target[use],
                                    error=error,baseline=baseline[use],index=np.flatnonzero(use))
    rt.dump('lut/dense_oracle_summary.json',result)


def main():
    (rt.LOCAL/'lut').mkdir(exist_ok=True)
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['r7','body','hybrid','dense'])
    a=ap.parse_args();{'r7':r7,'body':body,'hybrid':hybrid,'dense':dense_oracle}[a.action]()


if __name__=='__main__':main()
