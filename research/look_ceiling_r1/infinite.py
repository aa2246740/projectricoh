"""Finite learned 3D LUT references and explicit oracle/calibration controls.

The learned 33^3 Q8.8 tables use only the declared training samples. They are
achieved references, not mathematical upper bounds. The oracle controls use the
declared target function directly and are identified separately.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
from functools import lru_cache
import hashlib
import runtime as rt
from runtime import np,ROOT,LOCAL
from scipy.linalg import cho_factor,cho_solve
from scipy.spatial.distance import cdist
from quality import fixtures,diagnostics

def arrays(path):
    with np.load(path,allow_pickle=False) as z:return dict(z)

def warp(x,maximum):
    return np.arcsinh(np.clip(x,0,maximum)/128)/np.arcsinh(maximum/128)

def unwarp(u,maximum):
    return 128*np.sinh(np.clip(u,0,1)*np.arcsinh(maximum/128))

def tetra(table,x,maximum):
    u=warp(x,maximum)
    n=len(table);pos=u*(n-1)
    b=np.minimum(pos.astype(int),n-2)
    frac=np.rint((pos-b)*256)/256
    order=np.argsort(-frac,axis=1,kind='stable')
    rows=np.arange(len(x))
    v=[table[b[:,0],b[:,1],b[:,2]].astype(float)]
    q=b.copy()
    for j in range(3):
        q[rows,order[:,j]]+=1
        v.append(table[q[:,0],q[:,1],q[:,2]].astype(float))
    f=np.take_along_axis(frac,order,axis=1)
    out=v[0].copy()
    for j in range(3):out+=f[:,j,None]*(v[j+1]-v[j])
    return np.clip(out/256,0,255)

def kernel(x,z,sigma):
    d=cdist(x,z,'sqeuclidean')
    return np.exp(-d/(2*sigma*sigma))

def fit_rbf(x,delta,sw,original_index):
    # Exact duplicate inputs never occur on opposite sides of the inner split.
    unique,first,inv=np.unique(np.round(x,12),axis=0,return_index=True,return_inverse=True)
    counts=np.bincount(inv,weights=sw)
    y=np.column_stack([np.bincount(inv,weights=sw*delta[:,ch])/counts for ch in range(3)])
    weights=counts/np.mean(counts)
    original=np.asarray(original_index)[first]
    fold=original%3
    # Original three whole training photographs each stay in one inner fold.
    photo=original>=528
    fold[photo]=np.minimum((original[photo]-528)//140,2)
    best=None;cv=[]
    for sigma in (.10,.22,.45):
        K=kernel(unique,unique,sigma)
        for ridge in (1e-5,1e-3,1e-1):
            err=[]
            for group in range(3):
                train=fold!=group;held=~train
                A=K[np.ix_(train,train)]+np.diag(ridge/weights[train])
                coef=cho_solve(cho_factor(A,lower=True,check_finite=False),y[train],check_finite=False)
                pred=K[np.ix_(held,train)]@coef
                err.append(np.sum(weights[held,None]*(pred-y[held])**2))
            value=float(sum(err)/np.sum(weights))
            cv.append(dict(sigma=sigma,ridge=ridge,rgb_squared_error=value))
            if best is None or value<best[0]:best=(value,sigma,ridge)
    _,sigma,ridge=best
    K=kernel(unique,unique,sigma)+np.diag(ridge/weights)
    coef=cho_solve(cho_factor(K,lower=True,check_finite=False),y,check_finite=False)
    return unique,coef,dict(sigma=sigma,ridge=ridge,inner_cv=cv,unique_train_n=len(unique),
                           inner_split='3 folds; exact duplicates grouped; declared training photos blocked')

def grid_raw(n,maximum):
    u=np.stack(np.meshgrid(*([np.linspace(0,1,n)]*3),indexing='ij'),axis=-1).reshape(-1,3)
    return unwarp(u,maximum)

def bake(function,n,maximum):
    x=grid_raw(n,maximum)
    out=[]
    for start in range(0,len(x),4096):out.append(function(x[start:start+4096]))
    return np.rint(np.clip(np.vstack(out),0,255)*256).astype(np.uint16).reshape(n,n,n,3)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--indices',default='0:51')
    parser.add_argument('--oracle-fixed',action='store_true')
    args=parser.parse_args()
    a,b=map(int,args.indices.split(':'))
    model,dat152,_=rt.upstream.camera_model()
    from gxr_studio.camdata.datcodec import parse
    dat155=parse((ROOT/'firmware/package_v310_g155/local/SD_ROOT/GXRCE.DAT').read_bytes())
    standard_groups={k:arrays(LOCAL/('samples_'+k+'.npz')) for k in ('train','synthetic','a12-50','a12-28','mount-a12')}
    protocol=rt.read(LOCAL/'protocol_private.json')
    ref=protocol['scene_inventory'][0]
    c0=rt.Camera()
    neutral=np.asarray(ref['neutral']);matrix=np.asarray(ref['matrix'])
    for index in range(a,b):
        meta=rt.read(LOCAL/f'target_{index:02d}.json')
        data=arrays(LOCAL/f'target_{index:02d}.npz')
        ui=meta.get('camera_ui',0)
        c=rt.camera_for_unit(ui)
        dat=dat155 if meta.get('builtin_slot') else dat152
        groups={k:arrays(LOCAL/meta['group_files'][k]) if k in meta.get('group_files',{}) else standard_groups[k]
                for k in standard_groups}
        entry=dat.entry_of(ui,4)
        basefn=lambda x:model.predict(entry,x,bw_chroma='zero')
        x=groups['train']['x'];sw=groups['train']['sw']
        origin_lookup={tuple(row):i for i,row in reversed(list(enumerate(standard_groups['train']['x'])))}
        original_index=np.array([origin_lookup[tuple(row)] for row in x])
        results=[]
        for maximum,tag in ((4095,'raw12'),(16380,'raw16_headroom')):
            path=LOCAL/'infinite'/f'{index:02d}'/(tag+'.json')
            if path.exists():results.append(rt.read(path));continue
            u=warp(x,maximum)
            delta=(data['train_target']-data['train_base'])/255
            centres,coef,info=fit_rbf(u,delta,sw,original_index)
            def function(query):
                return basefn(query)+255*(kernel(warp(query,maximum),centres,info['sigma'])@coef)
            table=bake(function,33,maximum)
            scores={};direct={};predictions={}
            for key,g in groups.items():
                if not len(g['x']):scores[key]=None;direct[key]=None;continue
                predicted=np.rint(tetra(table,g['x'],maximum))
                scores[key]=rt.score(data[key+'_base'],predicted,data[key+'_target'])
                dp=[]
                for start in range(0,len(g['x']),4096):dp.append(function(g['x'][start:start+4096]))
                direct[key]=rt.score(data[key+'_base'],np.rint(np.clip(np.vstack(dp),0,255)),data[key+'_target'])
                predictions[key]=predicted.astype(np.uint8)
            gradients,rings=fixtures(c)
            quality=diagnostics(c,lambda q,r:np.rint(tetra(table,q,maximum)) if r else tetra(table,q,maximum),gradients,rings)
            doc=dict(label='电脑预测',name=meta['name'],index=index,key='Linf_fit33_'+tag,
                scores=scores,direct_regressor_scores=direct,quality=quality,fit=info,
                training_only_selection=True,grid=33,node_format='u16 Q8.8',fraction_format='Q8',
                input_maximum=maximum,input_shaper='asinh(x/128)/asinh(maximum/128)',
                mathematical_upper_bound=False,hardware_operator=False,
                interpretation='Same training samples, learned 3D reference. Not a proof of an ideal LUT ceiling.')
            rt.dump(path,doc)
            np.savez_compressed(path.with_suffix('.npz'),table_q8_8=table,centres=centres,coefficients=coef,**predictions)
            results.append(doc)
            print(index,meta['name'],tag,'MOUNT',None if scores['mount-a12'] is None else scores['mount-a12']['similarity_percent'],flush=True)
        # A direct target-function control does not estimate unknown sensor accuracy.
        oracle={}
        for key,g in groups.items():
            if not len(g['x']):oracle[key]=None;continue
            target=data[key+'_target']
            q16=np.rint(np.clip(target,0,255)/255*65535)*255/65535
            oracle[key]=rt.score(data[key+'_base'],np.rint(q16),target)
        rt.dump(LOCAL/'infinite'/f'{index:02d}'/'oracle_dynamic.json',dict(label='电脑预测',index=index,name=meta['name'],
            scores=oracle,key='Linf_target_function_q16',training_result=False,
            description='The declared target is applied with per-photo metadata. Precision control, not held-out learning or real cross-camera accuracy.',
            physical_sensor_error_identifiable=False))
        if args.oracle_fixed and index<27:
            job=dict(path=ROOT/meta['source'],input=meta['input'],output=meta['output'],
                     interpretation=meta.get('interpretation','declared'))
            target=rt.fit_adapter.target_of(job)
            def fixed(query):return target.render(basefn(query),c0.xyz(query,neutral,matrix))
            tab=bake(fixed,65,16380)
            fixed_scores={};continuous_scores={};metadata_shift={}
            for key,g in groups.items():
                if not len(g['x']):fixed_scores[key]=None;continuous_scores[key]=None;continue
                fixed_scores[key]=rt.score(data[key+'_base'],np.rint(tetra(tab,g['x'],16380)),data[key+'_target'])
                continuous_scores[key]=rt.score(data[key+'_base'],np.rint(fixed(g['x'])),data[key+'_target'])
                metadata_shift[key]=rt.stats(rt.delta_e00(rt.lab_from_codes(fixed(g['x'])),rt.lab_from_codes(data[key+'_target'])))
            rt.dump(LOCAL/'infinite'/f'{index:02d}'/'oracle_fixed65.json',dict(label='电脑预测',index=index,
                name=meta['name'],key='Linf_known_target_fixed_metadata65',scores=fixed_scores,
                continuous_fixed_metadata_scores=continuous_scores,training_result=False,
                metadata_target_shift_de00=metadata_shift,
                fixed_reference_photo=ref['path'],physical_sensor_error_identifiable=False,
                input_maximum=16380,grid=65,node_format='Q8.8',fraction_format='Q8'))
            np.savez_compressed(LOCAL/'infinite'/f'{index:02d}'/'oracle_fixed65.npz',table_q8_8=tab)
        rt.finish('infinite_'+str(index))

if __name__=='__main__':main()
