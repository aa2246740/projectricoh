"""Grouped held-out smooth LUT simulation; no firmware or patch generation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LOCAL, guard, read, dump
from prepare import modules, rgb_to_ycc, ycc_to_rgb, SLOTS
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.spatial.distance import cdist

WIDTH = 48.0
RIDGE = .03


def kernel(a,b,width=WIDTH):
    return np.exp(-cdist(np.asarray(a),np.asarray(b),'sqeuclidean')/(2*width*width))


def target_rgb(fs, lab):
    xyz = fs.lab_to_xyz(lab, fs.D65)
    return fs.linear_to_srgb(xyz @ np.linalg.inv(fs.M709).T)*255


def fit(x,y,width=WIDTH,ridge=RIDGE):
    k=kernel(x,x,width)
    c=cho_factor(k+ridge*np.eye(len(x)),lower=True)
    q=cho_solve(c,np.eye(len(x)))
    a=q@(y-np.tile(x,(1,len(SLOTS))))
    return {'x':x,'a':a,'q':q,'width':width,'ridge':ridge}


def predict(model,x):
    return np.tile(x,(1,len(SLOTS)))+kernel(x,model['x'],model['width'])@model['a']


def omitted(model, test):
    q,a=model['q'],model['a']
    block=q[np.ix_(test,test)]
    aa=a-q[:,test]@np.linalg.solve(block,a[test])
    # Algebraic deletion, not a fit containing held-out targets. Values must be exactly zero.
    assert np.max(np.abs(aa[test]))<1e-7
    aa[test]=0
    return {**model,'a':aa}


def vertices(x,n,fixed=False):
    x=np.clip(np.asarray(x),0,255)
    coords=x*((n-1)/255)
    if fixed:
        coords=np.floor(coords*256+.5)/256
    ix=np.minimum(np.floor(coords).astype(int),n-2)
    f=coords-ix
    order=np.argsort(-f,axis=1,kind='stable')
    delta=np.eye(3,dtype=int)[order]
    vv=np.stack([ix,ix+delta[:,0],ix+delta[:,0]+delta[:,1],ix+1],axis=1)
    ff=np.take_along_axis(f,order,axis=1)
    w=np.stack([1-ff[:,0],ff[:,0]-ff[:,1],ff[:,1]-ff[:,2],ff[:,2]],axis=1)
    if fixed:
        w=np.rint(w*256).astype(np.int64)
        assert np.all(w.sum(axis=1)==256)
    return vv,w


def lut_predict(model,x,n,fixed=False,node_bits=16,round_output=True):
    vv,w=vertices(x,n,fixed)
    node=vv.reshape(-1,3)*(255/(n-1))
    yy=np.clip(predict(model,node),0,255).reshape(len(x),4,12)
    if fixed:
        scale=256 if node_bits==16 else 1
        yy=np.floor(yy*scale+.5).astype(np.int64)
        numer=np.sum(w[:,:,None]*yy,axis=1)
        if not round_output:
            return numer/(scale*256)
        return np.clip(np.floor((numer+(scale*256)//2)/(scale*256)),0,255)
    return np.sum(w[:,:,None]*yy,axis=1)


def lut_array(model,n):
    v=np.stack(np.meshgrid(*([np.linspace(0,255,n)]*3),indexing='ij'),axis=-1).reshape(-1,3)
    out=np.empty((len(v),12))
    for start in range(0,len(v),2048):
        out[start:start+2048]=np.clip(predict(model,v[start:start+2048]),0,255)
    return out.reshape(n,n,n,4,3)


def table_apply(table,x,fixed=True,round_output=True):
    shape=x.shape
    flat=np.asarray(x).reshape(-1,3)
    n=table.shape[0]
    vv,w=vertices(flat,n,fixed)
    vals=table[vv[...,0],vv[...,1],vv[...,2]]
    if fixed:
        vals=np.floor(vals*256+.5).astype(np.int64)
        val=np.sum(w[:,:,None]*vals,axis=1)/65536
    else:
        val=np.sum(w[:,:,None]*vals,axis=1)
    if round_output:
        val=np.floor(val+.5)
    return np.clip(val,0,255).reshape(shape)


def apply422(table,pairs):
    ycc=np.clip(np.floor(rgb_to_ycc(pairs)+.5),0,255)
    # The two input luminances remain separate; both reads use one shared, rounded chroma pair.
    ycc[:,:,1:]=np.floor(np.mean(ycc[:,:,1:],axis=1,keepdims=True)+.5)
    out=table_apply(table,ycc,fixed=True,round_output=False)
    out[:,:,1:]=np.mean(out[:,:,1:],axis=1,keepdims=True)
    return np.clip(np.floor(out+.5),0,255)


def stats(fs,pred,target,base):
    err=fs.delta_e00(fs.lab_from_codes(np.clip(ycc_to_rgb(pred),0,255)),target)
    return error_stats(err,base)


def error_stats(err,base):
    return {'n':len(err),'similarity':float(1-np.median(err)/np.median(base)),
        'median':float(np.median(err)),'p90':float(np.percentile(err,90)),
        'max':float(np.max(err)), 'baseline_median':float(np.median(base)),
        **{f'under_{k}':float(np.mean(err<k)) for k in (1,2,3)}}


def main():
    guard()
    _,mm,_=modules()
    fs=mm.Engine.__init__.__globals__['helper']('fs') if 'helper' in mm.Engine.__init__.__globals__ else None
    assert fs is not None
    ds=read('research/body_lut/local/dataset.json')
    rows=ds['rows'];x=np.asarray([r['ycc'] for r in rows])
    target=np.stack([[r['targets'][s] for s in SLOTS] for r in rows])
    targetrgb=target_rgb(fs,target)
    yg=rgb_to_ycc(np.clip(targetrgb,0,255)).reshape(len(x),12)
    rgb=np.array([r['rgb'] for r in rows])
    lab=fs.lab_from_codes(rgb)
    base=np.stack([fs.delta_e00(lab,target[:,j]) for j in range(4)],axis=1)
    isp=np.stack([[r['isp_rgb'][s] for s in SLOTS] for r in rows])
    ispde=np.stack([fs.delta_e00(fs.lab_from_codes(isp[:,j]),target[:,j]) for j in range(4)],axis=1)
    groups=np.array([r['group'] for r in rows])
    domain=np.array([r['domain'] for r in rows])
    gray=np.array([r['gray'] for r in rows])
    hue=np.array([r['dng_hue'] for r in rows])
    segments=np.zeros(len(x),int)
    for group in np.unique(groups):
        ii=np.flatnonzero(groups==group)
        angle=np.degrees(np.angle(np.mean(np.exp(1j*np.radians(hue[ii])))))%360
        segments[ii]=12 if gray[ii[0]] else int(angle//30)
    full=fit(x,yg)
    modes={
        'patch_loo':[np.flatnonzero(groups==g) for g in np.unique(groups)],
        'hue_30deg':[np.flatnonzero(segments==g) for g in np.unique(segments)],
        'screen_to_physical':[np.flatnonzero(domain=='physical')],
        'resubstitution':[np.array([],int)]}
    report={'schema':'body-lut-simulation/1','width_codes':WIDTH,'ridge':RIDGE,
        'n_rows':len(rows),'groups':len(np.unique(groups)),
        'method':'Gaussian kernel ridge on YCbCr correction, identity mean; hyperparameters fixed before scores',
        'folds':{},'scores':{},'diagnostics':{},'implementation':{}}
    np.savez(LOCAL/'full_model.npz',x=x,a=full['a'],width=WIDTH,ridge=RIDGE)
    for mode,folds in modes.items():
        pred={name:np.full((len(x),12),np.nan) for name in
              ['smooth']+[f'n{n}_{v}' for n in (9,17,33) for v in ('float','fixed16','fixed8')]}
        held=np.zeros(len(x),bool)
        foldnotes=[]
        for ii in folds:
            if mode=='resubstitution':
                model=full;ii=np.arange(len(x))
            else:
                model=omitted(full,ii)
            held[ii]=True
            pred['smooth'][ii]=predict(model,x[ii])
            for n in (9,17,33):
                pred[f'n{n}_float'][ii]=lut_predict(model,x[ii],n)
                for bits in (8,16):
                    pred[f'n{n}_fixed{bits}'][ii]=lut_predict(model,x[ii],n,True,bits)
            foldnotes.append({'test':ii.tolist(),'train_n':len(x)-len(ii) if mode!='resubstitution' else len(x)})
        report['folds'][mode]=foldnotes
        report['scores'][mode]={}
        for name,yy in pred.items():
            report['scores'][mode][name]={s:stats(fs,yy[held,j*3:j*3+3],target[held,j],base[held,j])
                for j,s in enumerate(SLOTS)}
        report['scores'][mode]['frozen_isp_model']={s:error_stats(ispde[held,j],base[held,j])
            for j,s in enumerate(SLOTS)}
        report['scores'][mode]['gamut_floor']={s:error_stats(fs.delta_e00(
            fs.lab_from_codes(np.clip(targetrgb[held,j],0,255)),target[held,j]),base[held,j])
            for j,s in enumerate(SLOTS)}
        np.savez(LOCAL/f'predictions_{mode}.npz',mask=held,target=target,baseline=base,isp_de=ispde,
            **pred)
        print(mode, {s:round(report['scores'][mode]['n17_fixed16'][s]['similarity']*100,2)
                     for s in SLOTS},flush=True)
    # Store all candidates; these are sensitivity checks, not a search on the reported test folds.
    sensitivity={}
    for width in (24.,48.,96.):
        for ridge in (.01,.1,1.):
            model=fit(x,yg,width,ridge)
            yy=np.empty_like(yg)
            for g in np.unique(groups):
                ii=np.flatnonzero(groups==g)
                aa=model['a'][ii]
                residual=np.linalg.solve(model['q'][np.ix_(ii,ii)],aa)
                yy[ii]=yg[ii]-residual
            sensitivity[f'w{width:g}_r{ridge:g}']={s:stats(fs,yy[:,j*3:j*3+3],target[:,j],base[:,j])
                for j,s in enumerate(SLOTS)}
    report['diagnostics']['sensitivity_smooth_patch_loo']=sensitivity
    # Collision evidence: exact 8-bit triples require one output irrespective of scene/domain.
    _,inv=np.unique(x,axis=0,return_inverse=True)
    collisions=[]
    for key in np.unique(inv):
        ii=np.flatnonzero(inv==key)
        if len(ii)>1:
            spread={s:float(np.max(cdist(target[ii,j],target[ii,j]))) for j,s in enumerate(SLOTS)}
            maxde={s:float(max(fs.delta_e00(target[a,j],target[b,j]) for a in ii for b in ii))
                   for j,s in enumerate(SLOTS)}
            collisions.append({'indices':ii.tolist(),'ycc':x[ii[0]],'target_pair_max_de00':maxde,
                'target_pair_max_lab_l2':spread})
    report['diagnostics']['exact_8bit_collisions']=collisions
    report['diagnostics']['jpeg_clipped_patch_n']=sum(r['jpeg_clip']>.01 for r in rows)
    report['diagnostics']['raw_clipped_patch_n']=sum(r['raw_clip']>.001 for r in rows)
    report['diagnostics']['physical_ISO500_uses_ISO200_ISP_model']=True
    report['diagnostics']['all_flags_included']=True
    for n in (9,17,33):
        table=lut_array(full,n)
        np.save(LOCAL/f'lut{n}_float.npy',table)
        np.save(LOCAL/f'lut{n}_q8_8.npy',np.floor(table*256+.5).astype('>u2'))
    # Actual neighbouring pixels, not identical patch-centre duplicates.
    pairs=np.asarray([r['pairs_rgb'] for r in rows])
    for n in (9,17,33):
        table=np.load(LOCAL/f'lut{n}_float.npy')
        slots={}
        for j,s in enumerate(SLOTS):
            out=apply422(table[:,:,:,j],pairs.reshape(-1,2,3)).reshape(pairs.shape)
            mapped=np.clip(ycc_to_rgb(out),0,255)
            means=mapped.mean(axis=(1,2))
            direct=table_apply(table[:,:,:,j],np.clip(np.floor(rgb_to_ycc(pairs)+.5),0,255),
                               fixed=False,round_output=False)
            delta=fs.delta_e00(fs.lab_from_codes(mapped.reshape(-1,3)),
                              fs.lab_from_codes(np.clip(ycc_to_rgb(direct),0,255).reshape(-1,3)))
            slots[s]={'resub_actual_pairs':error_stats(fs.delta_e00(fs.lab_from_codes(means),target[:,j]),base[:,j]),
                'implementation_vs_float444_pixel_de00':{'median':float(np.median(delta)),
                    'p90':float(np.percentile(delta,90)),'max':float(delta.max())}}
        report['implementation'][str(n)]=slots
    dump('results.json',report)


if __name__=='__main__':
    main()
