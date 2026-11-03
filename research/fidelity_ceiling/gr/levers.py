#!/usr/bin/env python3
"""Conditional model ablations, never emits a firmware representation.

The hardware/T1 fits use the original round-4 objective. Richer fits hold the
training-fold T1 curves fixed, and refit Y and smooth angular fields. These are
best-found conditional fits, not certified optima or proven hardware features.
"""
import os
for _key in ('OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key] = '1'
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import importlib.util
import argparse
import time
spec = importlib.util.spec_from_file_location('ceiling_base', Path(__file__).with_name('analyze.py'))
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
np, opt = a.np, a.optimize


def state():
    n,p = a.imports(); tags=a.datasets(n,p)
    return n,tags


def source_record(slot, fold=None, t1=False):
    if slot == '01':
        folder=a.ROOT/'research/color_fit_v2/01_gr_positive/local'
        return a.read(folder/'candidate_full.json') if fold is None else a.read(folder/'loo_solutions.json')[fold]['quantized']
    folder=a.ROOT/'research/color_fit_v2/02_gr_negative/round4/local'
    prefix='B_k5' if t1 else 'A_s03'
    return a.read(folder/(f'{prefix}_full.json' if fold is None else f'{prefix}_fold_{fold:02d}.json'))


def curve_freedom(slot,kind,fold=None,max_nfev=160):
    neg,tags=state();wide=kind=='T1_33';nk=33 if wide else 5
    p=neg.Problem(tags[slot],t1=True,smooth=.3,curve_basis=nk,curve_ridge=.3,curve_smooth=3.,
                  grey_axis_weight=1. if slot=='02' else 3.,grey_limits=(slot=='02'))
    if wide:p.curve_basis=np.eye(33)
    stem='full' if fold is None else f'fold{fold:02d}'
    h=a.read(a.LOCAL/f'{slot}_H24_{stem}.json')
    start=np.r_[h['theta'],np.zeros(3*nk if wide else nk)]
    def expand(t):
        return t if wide else np.r_[t[:50],np.tile(t[50:],3)]
    idx=np.array([i for i in range(24) if fold is None or i!=p.chrom[fold]])
    lo,hi=p.bounds()
    if not wide:lo=np.r_[lo[:50],lo[50:50+nk]];hi=np.r_[hi[:50],hi[50:50+nk]]
    saved=a.LOCAL/f'{slot}_{kind}_{stem}.json'
    if saved.exists():start=np.array(a.read(saved)['theta'])
    if wide and (a.LOCAL/f'{slot}_T1_{stem}.json').exists():
        old=a.read(a.LOCAL/f'{slot}_T1_{stem}.json')
        nested=np.r_[old['theta'][:50],(np.array(old['curves'])-p.base_curve).ravel()]
        if np.sum(p.residual(nested,idx)**2)<np.sum(p.residual(start,idx)**2):start=nested
    now=time.monotonic()
    sol=opt.least_squares(lambda t:p.residual(expand(t),idx),np.clip(start,lo+1e-9,hi-1e-9),
         bounds=(lo,hi),max_nfev=max_nfev,ftol=1e-6,xtol=1e-6,gtol=1e-7,x_scale='jac')
    theta=expand(sol.x);lab=p.predict(theta);ring=p.predict(theta,'ring');c,z,cv=p.unpack(theta)
    info=dict(success=bool(sol.success),nfev=int(sol.nfev),status=int(sol.status),
              optimality=float(sol.optimality),cost=float(np.sum(sol.fun**2)),seconds=time.monotonic()-now,
              ftol=1e-6,xtol=1e-6)
    a.save(saved,dict(slot=slot,kind=kind,fold=fold,theta=sol.x,expanded_theta=theta,solver=info,
          chart_lab=lab,ring_lab=ring,curves=cv,c=c,z_real=z.real,z_imag=z.imag,
          chart=a.grouped(neg,p,lab),ring=a.stats(neg.fs.delta_e00(p.d['ring_target'],ring)),
          shared_curve=not wide,independent_output_nodes=wide,quantized=False))
    print(slot,kind,stem,'median',round(a.grouped(neg,p,lab)['colour']['median'],4),
          'success',sol.success,'nfev',sol.nfev,'sec',round(info['seconds'],2),flush=True)


def hardware(slot, kind, fold=None, max_nfev=160):
    neg,tags=state()
    t1=kind=='T1'
    p=neg.Problem(tags[slot], t1=t1, smooth=.3, curve_basis=5,
                  curve_ridge=.3, curve_smooth=3.,grey_axis_weight=1. if slot=='02' else 3.,
                  grey_limits=(t1 and slot=='02'))
    rec=source_record(slot,fold,t1)
    initial=p.theta_int(rec)
    if t1 and slot=='02':
        # The archived continuous vector uses this exact five-control basis.
        theta=np.array(rec['theta_continuous'])
        info=rec['solve']
        info={**info,'reused_archived_fit':True}
    else:
        if t1:
            previous=a.read(a.LOCAL/f'{slot}_H24_{"full" if fold is None else f"fold{fold:02d}"}.json')
            initial=np.r_[previous['theta'], np.zeros(15)]
            if fold is not None and (a.LOCAL/f'{slot}_T1_full.json').exists():
                initial[50:]=a.read(a.LOCAL/f'{slot}_T1_full.json')['theta'][50:]
        idx=np.array([i for i in range(24) if fold is None or i!=p.chrom[fold]])
        saved=a.LOCAL/f'{slot}_{kind}_{"full" if fold is None else f"fold{fold:02d}"}.json'
        if saved.exists() and not a.read(saved)['solver']['success']:
            initial=np.array(a.read(saved)['theta'])
            before=a.read(saved)['solver'];lo,hi=p.bounds();now=time.monotonic()
            sol=opt.least_squares(lambda th:p.residual(th,idx),np.clip(initial,lo+1e-9,hi-1e-9),
                bounds=(lo,hi),jac='3-point',x_scale='jac',max_nfev=max_nfev,
                ftol=1e-6,xtol=1e-6,gtol=1e-7)
            theta=sol.x
            info=dict(success=bool(sol.success),status=int(sol.status),nfev=int(sol.nfev),
                      optimality=float(sol.optimality),cost=float(np.sum(sol.fun**2)),
                      seconds=time.monotonic()-now,checkpoint_retry=True,previous_solver=before,
                      jac='3-point',ftol=1e-6,xtol=1e-6,gtol=1e-7)
        else:
            theta,info=p.solve(start=initial,idx=idx,max_nfev=max_nfev)
    c,z,curves=p.unpack(theta)
    lab=p.predict(theta); ring=p.predict(theta,'ring')
    out=dict(slot=slot,kind=kind,fold=fold,theta=theta,solver=info,
             chart_lab=lab,ring_lab=ring,curves=curves,c=c,z_real=z.real,z_imag=z.imag,
             chart=a.grouped(neg,p,lab),ring=a.stats(neg.fs.delta_e00(p.d['ring_target'],ring)),
             exact_round4_constraints=True,quantized=False)
    a.save(a.LOCAL/f'{slot}_{kind}_{"full" if fold is None else f"fold{fold:02d}"}.json',out)
    print(slot,kind,'full' if fold is None else f'fold {fold}',
          'median',round(out['chart']['colour']['median'],4),'success',info['success'],
          'nfev',info['nfev'],flush=True)


def circular_interp(nodes, vals, new):
    nodes=np.array(nodes); order=np.argsort(nodes%360); x=nodes[order]%360
    v=np.array(vals)[order]
    return np.interp(new%360,np.r_[x-360,x,x+360],np.tile(v,3))


class Rich:
    """Y plus a general angular chroma field, optional seven-node gain in Y.

    alpha*z + beta*conj(z) spans all real 2x2 maps. We retain the measured
    stock 24-sector field, and interpolate a smooth correction on 24/48/96
    nodes. Original blur in degrees and chroma remains fixed at every density.
    """
    def __init__(self, neg, p, source, nsec=24, gain=False):
        self.neg,self.p,self.n,self.gain=neg,p,nsec,gain
        self.curves=np.array(source['curves'])
        self.seed_y=np.array(source['c'])[0]
        z=np.array(source['z_real'])+1j*np.array(source['z_imag'])
        self.original_nodes=p.tab.nodes
        factor=nsec//24
        self.nodes=np.array([self.original_nodes[i]+(j/factor)*(np.r_[self.original_nodes[1:],self.original_nodes[0]+360][i]-self.original_nodes[i]) for i in range(24) for j in range(factor)])
        self.alpha0=p.ctx.S_eff*(neg.sm.effective(z,p.tab.k)-1)*p.tab.gain
        alpha=circular_interp(self.original_nodes,self.alpha0.real,self.nodes)+1j*circular_interp(self.original_nodes,self.alpha0.imag,self.nodes)
        self.start=np.r_[self.seed_y[[0,2]],alpha.real,alpha.imag,np.zeros(2*self.n),np.zeros(7) if gain else []]
        self.ynodes=np.linspace(0,255,7)
        self.chart=self.prepare(p.x)
        self.ring=self.prepare(np.array(p.d['ring_x'])*p.d['e'])
        self.gray_sensor=np.repeat(np.geomspace(8.,3500.,65)[:,None],3,axis=1)
        self.gray=self.prepare(self.gray_sensor)
        self.gray_target=p.forward_raw(self.gray_sensor,p.stock,np.ones(24,complex),np.tile(p.base_curve,(3,1)))[0]
        # Coarse engineering guards constrain interpolated total field. These
        # are model guards, not the original encoded round4 integer checks.
        h=np.arange(0.,360.,5.)
        radius=np.array([.5,5.,40.,120.])
        self.sh=np.tile(h,len(radius));self.sr=np.repeat(radius,len(h));self.nh=len(h)
        self.sci=self.sr*np.exp(1j*np.deg2rad(self.sh))
        self.sW=self.weights(self.sh,self.sr)
        self.sbase=p.tab.S_of(self.sh,self.sr)
        self.sA0=p.tab.kernel_weights(self.sh,self.sr)@self.alpha0
        self.identity=self.stock_coeff()

    def stock_coeff(self):
        return np.r_[self.p.stock[0,[0,2]],np.zeros(4*self.n),np.zeros(7) if self.gain else []]

    def weights(self,h,r):
        # Reuse the calibrated periodic Gaussian-convolved linear hats. The
        # broad low-chroma Fourier branch is copied algebraically from PreTable.
        tab=self.p.tab; h=np.array(h);r=np.array(r)
        sigma=np.sqrt(tab.s0**2+(tab.kappa/np.maximum(r,1e-12))**2)
        w=np.zeros((len(h),self.n));small=sigma<=30
        if small.any():
            w[small]=self.neg.sm.weights(h[small],self.nodes,tab.kernel,np.maximum(sigma[small],1e-4))
        if (~small).any():
            n=self.nodes;lo=np.r_[n[-1]-360,n[:-1]];hi=np.r_[n[1:],n[0]+360]
            om=2*np.pi*np.arange(1,33)/360
            coef=-(np.exp(-1j*om[:,None]*lo)/(n-lo)-np.exp(-1j*om[:,None]*n)*(1/(n-lo)+1/(hi-n))+np.exp(-1j*om[:,None]*hi)/(hi-n))/(360*om[:,None]**2)
            dc=(hi-lo)/720
            phase=np.exp(1j*h[~small,None]*om)*np.exp(-.5*(sigma[~small,None]*om)**2)
            w[~small]=dc[None,:]+2*np.real(phase@coef)
        w=np.maximum(w,0.)
        return w/np.maximum(w.sum(axis=1,keepdims=True),1e-12)

    def prepare(self,x):
        rp=self.p.curves_apply(np.asarray(x),self.curves)
        yc=rp@self.p.stock.T;ci=yc[:,1]+1j*yc[:,2]
        h=self.neg.mm.hue_deg(ci);w=self.weights(h,abs(ci))
        return dict(rp=rp,ci=ci,W=w,base=ci*self.p.tab.S_of(h,abs(ci)))

    def split(self,t):
        n=self.n
        y=np.array([t[0],1-t[0]-t[1],t[1]])
        alpha=t[2:2+n]+1j*t[2+n:2+2*n]
        beta=t[2+2*n:2+3*n]+1j*t[2+3*n:2+4*n]
        return y,alpha,beta,t[2+4*n:]

    def prediction(self,t,which='chart',detail=False):
        d=getattr(self,which) if isinstance(which,str) else which
        y,al,be,g=self.split(t)
        Y=d['rp']@y
        co=d['base']+d['ci']*(d['W']@al)+np.conj(d['ci'])*(d['W']@be)
        if self.gain:co*=np.exp(np.interp(Y,self.ynodes,g))
        rgb=np.clip(self.neg.mm.rgb_from_ycc(Y,co),0,255)
        lab=self.neg.fs.lab_from_codes(rgb)
        return (lab,Y,co) if detail else lab

    def safety(self,t):
        _,al,be,_=self.split(t)
        co=self.sci*(self.sbase+self.sW@al)+np.conj(self.sci)*(self.sW@be)
        rel=(abs(co)/np.maximum(abs(self.sci*self.sbase),1e-12)).reshape(-1,self.nh)
        q=co.reshape(-1,self.nh)
        deriv=np.angle(np.roll(q,-1,axis=1)/q,deg=True)/5.
        slope=np.log(np.maximum(abs(np.roll(q,-1,axis=1)),1e-12)/np.maximum(abs(q),1e-12))/5.
        return rel,deriv,slope

    def residual(self,t,idx):
        y,al,be,g=self.split(t);n=self.n
        r=[self.neg.fs.de00_components(self.p.target[idx],self.prediction(t)[idx]).ravel(),
           # Scale first differences by angular spacing; comparable smoothing
           # energy when the same angular field is represented at more nodes.
           np.sqrt(.3*n/24)*np.r_[np.diff(np.r_[al.real,al.real[0]]),np.diff(np.r_[al.imag,al.imag[0]])]/.15,
           np.sqrt(.3*n/24)*np.r_[np.diff(np.r_[be.real,be.real[0]]),np.diff(np.r_[be.imag,be.imag[0]])]/.15,
           np.sqrt(.05*24/n)*np.r_[al.real,al.imag,be.real,be.imag]/.3,
           np.sqrt(.001)*(y-self.p.stock[0])/.05,
           3*self.neg.fs.de00_components(self.gray_target,self.prediction(t,'gray')).ravel(),
           300*np.maximum(abs(y)-2047/1024,0)]
        rel,deriv,slope=self.safety(t)
        r.extend([300*np.maximum(.2-rel,0).ravel(),300*np.maximum(.1-deriv,0).ravel(),
                  300*np.maximum(abs(slope)-.12,0).ravel()])
        if self.gain:
            r.extend([np.sqrt(.3)*g/.3,np.sqrt(1.)*np.diff(g,n=2)/.3])
        return np.concatenate(r)

    def solve(self,idx,max_nfev=120):
        lo=np.r_[[-2047/1024]*2,[-4.]* (4*self.n),[-1.6]*7 if self.gain else []]
        hi=np.r_[[2047/1024]*2,[4.]* (4*self.n),[1.]*7 if self.gain else []]
        start=np.clip(self.start,lo+1e-8,hi-1e-8)
        now=time.monotonic()
        result=opt.least_squares(lambda t:self.residual(t,idx),start,bounds=(lo,hi),max_nfev=max_nfev,
                                ftol=1e-5,xtol=1e-5,gtol=1e-5,x_scale='jac')
        info=dict(success=bool(result.success),status=int(result.status),nfev=int(result.nfev),
                  optimality=float(result.optimality),seconds=time.monotonic()-now,
                  cost=float(np.sum(result.fun**2)))
        return result.x,info


def richer(slot,kind,fold=None,max_nfev=120):
    neg,tags=state();p=neg.Problem(tags[slot])
    stem='full' if fold is None else f'fold{fold:02d}'
    src=a.read(a.LOCAL/f'{slot}_T1_{stem}.json')
    ns={'T3':24,'T2':24,'D48':48,'D96':96}[kind]
    rich=Rich(neg,p,src,ns,kind!='T3')
    predecessor={'T2':'T3','D48':'T2','D96':'D48'}.get(kind)
    if predecessor and (a.LOCAL/f'{slot}_{predecessor}_{stem}.json').exists():
        old=a.read(a.LOCAL/f'{slot}_{predecessor}_{stem}.json')
        old_n=old.get('sectors',24)
        old_rich=Rich(neg,p,src,old_n,predecessor!='T3')
        yy,al,be,gg=old_rich.split(np.array(old['theta']))
        al2=circular_interp(old_rich.nodes,al.real,rich.nodes)+1j*circular_interp(old_rich.nodes,al.imag,rich.nodes)
        be2=circular_interp(old_rich.nodes,be.real,rich.nodes)+1j*circular_interp(old_rich.nodes,be.imag,rich.nodes)
        rich.start=np.r_[yy[[0,2]],al2.real,al2.imag,be2.real,be2.imag,
                         gg if len(gg) else np.zeros(7)]
    prior=a.LOCAL/f'{slot}_{kind}_{stem}.json'
    idx=np.array([i for i in range(24) if fold is None or i!=p.chrom[fold]])
    if prior.exists():
        prev=np.array(a.read(prior)['theta'])
        if np.sum(rich.residual(prev,idx)**2)<np.sum(rich.residual(rich.start,idx)**2):
            rich.start=prev
    theta,info=rich.solve(idx,max_nfev)
    lab=rich.prediction(theta);ring=rich.prediction(theta,'ring')
    rel,deriv,slope=rich.safety(theta)
    out=dict(slot=slot,kind=kind,fold=fold,theta=theta,solver=info,chart_lab=lab,ring_lab=ring,
        chart=a.grouped(neg,p,lab),ring=a.stats(neg.fs.delta_e00(p.d['ring_target'],ring)),
        frozen_T1_curves=True,conditional_fit=True,sectors=ns,
        coarse_safety=dict(min_relative_chroma=float(rel.min()),min_hue_derivative=float(deriv.min()),
                           max_log_slope=float(abs(slope).max())))
    a.save(a.LOCAL/f'{slot}_{kind}_{stem}.json',out)
    print(slot,kind,stem,'median',round(out['chart']['colour']['median'],4),
          'ring',round(out['ring']['median'],4),'success',info['success'],'nfev',info['nfev'],
          'sec',round(info['seconds'],2),flush=True)


def upper(slot):
    neg,tags=state();p=neg.Problem(tags[slot]);q=a.read(a.LOCAL/'q1_colour_arrays.json')[slot]
    X=np.array(q['predictions']['a_stock04'])/100
    T=p.target;ref=np.array(q['predictions']['a_stock04'])
    projected=np.array(a.read(a.LOCAL/f'{slot}_gamut_parameters.json')['nearest_lab'])
    def clip_lab(lab):
        lin=neg.fs.lab_to_xyz(lab,neg.fs.D65)@np.linalg.inv(neg.fs.M709).T
        return neg.fs.lab_from_codes(np.clip(neg.fs.linear_to_srgb(lin)*255,0,255))
    XR=np.array(q['ring']['a_stock04'])/100
    # Fits target change as a smooth function of Standard Lab, not patch label.
    results=[]
    for smoothing in (0.,.0001,.001,.01,.1,1.):
        f=a.RBFInterpolator(X,projected-ref,kernel='thin_plate_spline',smoothing=smoothing,degree=1)
        lab=clip_lab(ref+f(X));ring=clip_lab(XR*100+f(XR))
        lp=[]
        for i in p.chrom:
            idx=np.array([j for j in range(24) if j!=i])
            fi=a.RBFInterpolator(X[idx],projected[idx]-ref[idx],kernel='thin_plate_spline',smoothing=smoothing,degree=1)
            lp.append(clip_lab(ref[i]+fi(X[i:i+1])[0]))
        out=dict(smoothing=smoothing,chart=a.grouped(neg,p,lab),ring=a.stats(neg.fs.delta_e00(p.d['ring_target'],ring)),
                 loo=a.stats(neg.fs.delta_e00(T[p.chrom],np.array(lp))))
        results.append(out)
        a.save(a.LOCAL/f'{slot}_3D_{smoothing}.json',dict(**out,chart_lab=lab,ring_lab=ring,loo_lab=lp))
    best=min(results,key=lambda r:r['loo']['mean'])
    a.save(a.LOCAL/f'{slot}_upper_stats.json',dict(sweep=results,selected=best,
        selection_note='LOO-selected smoothing; selection-biased, not nested CV. Zero smoothing is interpolation floor.'))
    print(slot,'3D',best,flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('kind',choices=['H24','Hshared','T1','T1_33','T3','T2','D48','D96','3D','batch'])
    ap.add_argument('--slot',choices=['01','02'],required=True);ap.add_argument('--fold',type=int)
    ap.add_argument('--kinds',default='H24,T1')
    ap.add_argument('--start',type=int);ap.add_argument('--stop',type=int)
    ap.add_argument('--max-nfev',type=int,default=160)
    ar=ap.parse_args();a.guard()
    for fold in (range(ar.start,ar.stop) if ar.start is not None else [ar.fold]):
        for kind in (ar.kinds.split(',') if ar.kind=='batch' else [ar.kind]):
            if kind in ('H24','T1'):hardware(ar.slot,kind,fold,ar.max_nfev)
            elif kind in ('Hshared','T1_33'):curve_freedom(ar.slot,kind,fold,ar.max_nfev)
            elif kind=='3D':upper(ar.slot)
            else:richer(ar.slot,kind,fold,ar.max_nfev)
