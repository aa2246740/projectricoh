#!/usr/bin/env python3
"""Residual-corrected, bounded fits; all folds start from deployed round five."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
import numpy as np
from scipy.optimize import least_squares
import argparse
import time

CONFIG = dict(screen_chromatic_total_weight=18., real_chart_chromatic_weight_per_patch=1.,
              chart_gray_weight_per_patch=2., screen_gray_weight_multiplier=4.,
              hue_folds=6, hue_fold_width_deg=60, hue_training_buffer_deg=15,
              color_log_step=.22, color_angle_step_rad=.22, y_step=.12,
              ridge=.03, smooth=.15, beta_max=.25, beta_ridge=.12,
              T1_control_nodes=list(range(0,33,4)), T1_bound_codes=12.,
              T1_prior_unit_codes=8., T1_smooth_unit_codes=3.,
              gray_error_margin=.05, gray_guard_strength=45.,
              integer_trust_factor_by_slot={'01':.5,'02':1.},
              integer_trust_rule='01 fixed half step after full-step integer safety failures; same factor in every tier and fold; 02 full step',
              ring_weight=0., physical_weight=0., anchor_EV=0.,
              selection='simplest safe tier with lower blocked-hue CV mean; added tier requires >=0.05 DE00 CV mean gain and no >0.10 DE00 bastibe LOO mean regression')


class Problem:
    def __init__(self, slot, tier, ev=0., fold=None):
        self.D=r.Inputs(slot,ev);self.E=self.D.E;self.slot=slot;self.tier=tier;self.fold=fold
        self.shared=bool(ev!=0 and tier=='c')
        self.free=np.array([0,11,17,23] if tier in ('b','c') and not self.shared else [],int)
        self.nf=len(self.free);self.ib=50;self.ic=50+2*self.nf
        self.np=self.ic+((9 if self.shared else 27) if tier=='c' else 0)
        self.base=np.tile(self.D.curve.ys,(3,1)).astype(float)
        self.B=r.interp_weights(np.arange(33),np.arange(0,33,4))
        s,c=self.D.screen,self.D.chart[200]
        self.ns=len(s['x']);self.nc=len(c['x'])
        self.x=np.vstack([s['x'],c['x'],self.D.chart[1600]['x'][self.D.chart[1600]['gray']]])
        self.target=np.vstack([s['target'],c['target'],self.D.chart[1600]['target'][self.D.chart[1600]['gray']]])
        self.bias=np.vstack([s['bias'],np.zeros((self.nc+6,3))])
        self.w=np.r_[np.where(s['gray'],4.,1.)*18/max(1,int((~s['gray']).sum())),np.where(c['gray'],2.,1.),np.zeros(6)]
        self.screen_eval=np.zeros(self.ns,bool);self.chart_eval=None
        if fold is not None and fold.startswith('h'):
            k=int(fold[1:]);h=s['hue']%360
            self.screen_eval=(h>=60*k)&(h<60*(k+1))&~s['gray']
            center=60*k+30
            excluded=(abs((h-center+180)%360-180)<=45)&~s['gray']
            self.w[:self.ns][excluded]=0
        if fold is not None and fold.startswith('l'):
            k=int(fold[1:]);idx=np.flatnonzero(~c['gray'])[k]
            self.chart_eval=idx;self.w[self.ns+idx]=0
        self.sqrtw=np.sqrt(self.w)
        self.H=r.interp_weights(self.x,self.D.curve.xs)
        self.pre=np.einsum('ncj,cj->nc',self.H,self.base)
        self.initial=np.zeros(self.np)
        z=r.fs.Z_of_words(self.D.A,self.D.B,self.E.ctx)
        self.initial[2:26]=np.log(abs(z));self.initial[26:50]=np.angle(z)
        self.train_cached={}
        self.gray_idx=np.r_[self.ns+np.flatnonzero(c['gray']),np.arange(len(self.x)-6,len(self.x))]
        self.limits=r.fs.delta_e00(self.target[self.gray_idx],self.predict_lab(self.initial)[self.gray_idx])+.015
        self.R=self.reg_matrix()
        self.safety=r.common.helper('safety').Safety(self.E,step=3.,radii=(.1,1.,5.,20.,80.,180.))
        self.safety.min_derivative=.16;self.safety.max_log_chroma_slope=.046
        self.make_safety_geometry()

    def make_safety_geometry(self):
        # Include both sides of each node; narrow edge violations must enter training.
        near=(self.E.table.nodes[:,None]+[-.2,-.02,.02,.2]).ravel()%360
        h=np.unique(np.r_[np.arange(0,360,3.),near]);radii=[.05,.2,1.,5.,20.,50.,100.,180.]
        self.sh=np.tile(h,len(radii));sr=np.repeat(radii,len(h));self.sci=sr*np.exp(1j*np.deg2rad(self.sh))
        self.sg={};eps=.001
        for iso,E in self.D.engines.items():
            self.sg[iso]=(E.table.kernel_weights(self.sh,sr),(E.table.kernel_weights(self.sh+eps,sr)-E.table.kernel_weights(self.sh-eps,sr))/(2*eps))

    def reg_matrix(self):
        rows=[]
        def add(indices,values):
            v=np.zeros(self.np);v[indices]=values;rows.append(v)
        for k in range(2):add(k,np.sqrt(.03)/.08)
        for off,unit in ((2,.1),(26,np.deg2rad(5))):
            for k in range(24):
                add(off+k,np.sqrt(.03)/unit)
                add([off+k,off+(k+1)%24],np.array([-1,1])*np.sqrt(.15)/unit)
        for k in range(2*self.nf):add(self.ib+k,np.sqrt(.12)/.08)
        if self.tier=='c':
            for ch in range(1 if self.shared else 3):
                for k in range(9):add(self.ic+ch*9+k,np.sqrt(.02)/8)
                for k in range(7):add(self.ic+ch*9+np.arange(k,k+3),np.array([1,-2,1])*np.sqrt(.3)/3)
        return np.array(rows)

    def curves(self,t):
        if self.tier!='c':return self.base
        if self.shared:return self.base+(self.B@t[self.ic:])[None,:]
        return self.base+(self.B@t[self.ic:].reshape(3,9).T).T

    def coef(self,t):
        z=np.exp(t[2:26]+1j*t[26:50]);eff=np.exp(t[2:26]+1j*self.E.table.k*t[26:50])
        beta=np.zeros(24,complex)
        if self.nf:beta[self.free]=t[self.ib:self.ib+self.nf]+1j*t[self.ib+self.nf:self.ic]
        C=self.D.row.coef.astype(float).copy();C[0,[0,2]]+=1024*t[:2];C[0,1]=1024-C[0,0]-C[0,2]
        return z,eff,beta,C

    def parts(self,t,pre=None,jac=False):
        z,eff,beta,C=self.coef(t)
        pre=np.einsum('ncj,cj->nc',self.H,self.curves(t)) if pre is None and self.tier=='c' else self.pre if pre is None else pre
        _,ci=self.D.row.apply(pre)
        y=pre@(C[0]/1024)
        co=np.empty(len(pre),complex);dc=np.zeros((len(pre),self.np),complex)
        for iso,sel in [(200,slice(0,len(pre)-6)),(1600,slice(len(pre)-6,len(pre)))]:
            E=self.D.engines[iso];c=ci[sel]
            key=(iso,len(c))
            if self.tier!='c' and key in self.train_cached:W=self.train_cached[key]
            else:
                W=E.table.kernel_weights(r.mm.hue_deg(c),abs(c))
                if self.tier!='c':self.train_cached[key]=W
            # Same encoded words must be evaluated under each ISO's d0/d1 and S_eff.
            aa=(self.E.ctx.S_eff*z*32).real-self.E.ctx.d0
            bb=-(self.E.ctx.S_eff*z*32).imag-self.E.ctx.d1
            zz=((aa+E.ctx.d0)-1j*(bb+E.ctx.d1))/(32*E.ctx.S_eff)
            ee=np.exp(np.log(abs(zz))+1j*E.table.k*np.angle(zz))
            wg=W*E.table.gain
            co[sel]=c*(W@E.ctx.S_eff+wg@(E.ctx.S_eff*(ee-1)))+np.conj(c)*(wg@beta)
            if jac:
                # Chain encoded alpha from the ISO200 parameterisation to the cross ISO.
                dz=(self.E.ctx.S_eff/E.ctx.S_eff)*z
                u=dz/zz
                er=ee*(u.real+1j*E.table.k*u.imag)
                ep=ee*((1j*u).real+1j*E.table.k*(1j*u).imag)
                dc[sel,2:26]=c[:,None]*wg*(E.ctx.S_eff*er)[None,:]
                dc[sel,26:50]=c[:,None]*wg*(E.ctx.S_eff*ep)[None,:]
                if self.nf:
                    b=np.conj(c[:,None])*wg[:,self.free]
                    dc[sel,self.ib:self.ib+self.nf]=b;dc[sel,self.ib+self.nf:self.ic]=1j*b
        dy=np.zeros((len(pre),self.np));dy[:,:2]=np.c_[pre[:,0]-pre[:,1],pre[:,2]-pre[:,1]]
        return (y,co,dy,dc,pre) if jac else (y,co)

    def predict_lab(self,t):
        y,co=self.parts(t)
        return r.fs.lab_from_codes(np.clip(r.mm.rgb_from_ycc(y,co)+self.bias,0,255))

    def losses(self,y,co):
        lab=r.fs.lab_from_codes(np.clip(r.mm.rgb_from_ycc(y,co)+self.bias,0,255))
        data=r.fs.de00_components(self.target,lab)*self.sqrtw[:,None]
        errors=r.fs.delta_e00(self.target[self.gray_idx],lab[self.gray_idx])
        guard=45*np.maximum(errors-self.limits,0)
        return np.r_[data.ravel(),guard]

    def safe_one(self,t,iso,jac=False):
        z,_,beta,_=self.coef(t);E=self.D.engines[iso];S=E.ctx.S_eff;g=E.table.gain
        W,Wd=self.sg[iso]
        alpha=self.E.ctx.S_eff*z
        aa=alpha.real*32-self.E.ctx.d0;bb=-alpha.imag*32-self.E.ctx.d1
        zz=((aa+E.ctx.d0)-1j*(bb+E.ctx.d1))/(32*S)
        eff=np.exp(np.log(abs(zz))+1j*E.table.k*np.angle(zz))
        T=W@S+(W*g)@(S*(eff-1));Td=Wd@S+(Wd*g)@(S*(eff-1))
        U=(W*g)@beta;Ud=(Wd*g)@beta
        c=self.sci*T+np.conj(self.sci)*U
        cd=self.sci*(1j*np.pi/180*T+Td)+np.conj(self.sci)*(-1j*np.pi/180*U+Ud)
        den=np.where(abs(c)<1e-10,1e-10+0j,c);v=cd/den
        hd=v.imag*180/np.pi;sl=v.real;ratio=abs(c/(self.sci*(W@S)))
        mask=[hd<.24,sl>.044,sl<-.044,ratio<.28]
        values=160*np.r_[np.minimum(hd-.24,0),np.maximum(sl-.044,0),np.minimum(sl+.044,0),np.minimum(ratio-.28,0)]
        if not jac:return values
        dc=np.zeros((len(c),self.np),complex);dd=dc.copy()
        u=(self.E.ctx.S_eff/S)*z/zz
        for off,der in [(2,eff*(u.real+1j*E.table.k*u.imag)),(26,eff*((1j*u).real+1j*E.table.k*(1j*u).imag))]:
            fac=S*der
            dc[:,off:off+24]=self.sci[:,None]*(W*g)*fac
            dd[:,off:off+24]=self.sci[:,None]*(1j*np.pi/180*W+Wd)*g*fac
        if self.nf:
            b=np.conj(self.sci[:,None])*(W*g)[:,self.free]
            bd=np.conj(self.sci[:,None])*(-1j*np.pi/180*W+Wd)[:,self.free]*g[self.free]
            dc[:,self.ib:self.ib+self.nf]=b;dc[:,self.ib+self.nf:self.ic]=1j*b
            dd[:,self.ib:self.ib+self.nf]=bd;dd[:,self.ib+self.nf:self.ic]=1j*bd
        dv=(dd*den[:,None]-cd[:,None]*dc)/den[:,None]**2
        J=160*np.vstack([dv.imag*180/np.pi*mask[0][:,None],dv.real*mask[1][:,None],dv.real*mask[2][:,None],ratio[:,None]*np.real(dc/den[:,None])*mask[3][:,None]])
        return values,J

    def safe(self,t,jac=False):
        values=[self.safe_one(t,iso,jac) for iso in (200,1600)]
        if jac:return np.r_[values[0][0],values[1][0]],np.vstack([values[0][1],values[1][1]])
        return np.r_[values[0],values[1]]

    def extra(self,t):
        z,_,beta,_=self.coef(t);alpha=self.E.ctx.S_eff*z
        M=np.c_[alpha.real+beta.real,-alpha.imag+beta.imag,alpha.imag+beta.imag,alpha.real-beta.real]*32
        curves=self.curves(t)
        return np.r_[(30*np.maximum(abs(M)-126.5,0)).ravel(),
                     (10*np.minimum(np.diff(curves,axis=1),0)).ravel(),
                     (10*np.maximum(curves-255,0)).ravel(),(10*np.minimum(curves,0)).ravel(),
                     10*np.minimum(curves[:,-1]-128,0),
                     (40*np.maximum(abs(curves[[0,2]]-curves[1])-.25,0)).ravel()]

    def residual(self,t):
        y,co=self.parts(t)
        return np.r_[self.losses(y,co),self.R@(t-self.initial),self.safe(t),self.extra(t)]

    def jacobian(self,t):
        y,co,dy,dc,pre=self.parts(t,jac=True);eps=1e-6
        fy=(self.losses(y+eps,co)-self.losses(y-eps,co))/(2*eps)
        fb=(self.losses(y,co+eps)-self.losses(y,co-eps))/(2*eps)
        fr=(self.losses(y,co+1j*eps)-self.losses(y,co-1j*eps))/(2*eps)
        # Data rows can use analytic colour and Y derivatives; gray guards are few.
        n=len(y)*3
        J=(fy[:n].reshape(-1,3)[:,:,None]*dy[:,None,:]+fb[:n].reshape(-1,3)[:,:,None]*dc.real[:,None,:]+fr[:n].reshape(-1,3)[:,:,None]*dc.imag[:,None,:]).reshape(n,self.np)
        guard=np.zeros((len(self.gray_idx),self.np))
        extra=np.empty((len(self.extra(t)),self.np))
        if self.tier=='c':
            if self.shared:J[:,self.ic:]=0
            for ch in range(3):
                pp,pm=pre.copy(),pre.copy();pp[:,ch]+=eps;pm[:,ch]-=eps
                yp,cp=self.parts(t,pp);ym,cm=self.parts(t,pm)
                deriv=(self.losses(yp,cp)-self.losses(ym,cm))/(2*eps)
                dpre=self.H[:,ch]@self.B;cols=slice(self.ic,self.ic+9) if self.shared else slice(self.ic+9*ch,self.ic+9*(ch+1))
                J[:,cols]+=(deriv[:n].reshape(-1,3)[:,:,None]*dpre[:,None,:]).reshape(n,9) if self.shared else 0
                if self.shared:guard[:,cols]+=deriv[n:,None]*dpre[self.gray_idx]
                else:
                    J[:,cols]=(deriv[:n].reshape(-1,3)[:,:,None]*dpre[:,None,:]).reshape(n,9)
                    guard[:,cols]=deriv[n:,None]*dpre[self.gray_idx]
        for k in range(self.np):
            tp,tm=t.copy(),t.copy();tp[k]+=eps;tm[k]-=eps
            if k<2:
                yp,cp=self.parts(tp);ym,cm=self.parts(tm)
                guard[:,k]=(self.losses(yp,cp)[n:]-self.losses(ym,cm)[n:])/(2*eps)
            elif k<self.ic:
                idx=self.gray_idx
                guard[:,k]=fy[n:]*dy[idx,k]+fb[n:]*dc[idx,k].real+fr[n:]*dc[idx,k].imag
            extra[:,k]=(self.extra(tp)-self.extra(tm))/(2*eps)
        return np.vstack([J,guard,self.R,self.safe(t,True)[1],extra])

    def solve(self,nfev=60):
        low,high=self.initial.copy(),self.initial.copy()
        low[:2]=-.12;high[:2]=.12
        low[2:26]-=.22;high[2:26]+=.22;low[26:50]-=.22;high[26:50]+=.22
        if self.nf:low[self.ib:self.ic]=-.25;high[self.ib:self.ic]=.25
        if self.tier=='c':
            bound=28 if self.D.ev else 12
            low[self.ic:]=-bound;high[self.ic:]=bound
        sol=least_squares(self.residual,self.initial,jac=self.jacobian,bounds=(low,high),max_nfev=nfev,
                          x_scale='jac',ftol=2e-6,xtol=2e-6,gtol=2e-5)
        return sol

    def quantize(self,t):
        z,_,beta,C=self.coef(t)
        alpha=self.E.ctx.S_eff*z
        M=np.rint(32*np.c_[alpha.real+beta.real,-alpha.imag+beta.imag,alpha.imag+beta.imag,alpha.real-beta.real]).astype(int)
        assert abs(M).max()<=127
        # On all other sectors the camera writes the symmetric byte pattern.
        A=np.rint(alpha.real*32-self.E.ctx.d0).astype(float)
        B=np.rint(-alpha.imag*32-self.E.ctx.d1).astype(float)
        bs=[]
        for s in self.free:
            a,b,c,d=M[s]
            A[s]=(a+d)/2-self.E.ctx.d0[s];B[s]=(b-c)/2-self.E.ctx.d1[s]
            bs.append([int(s),(a-d)/64,(b+c)/64])
        Y=np.rint(C[0]).astype(int);Y[1]=1024-Y[0]-Y[2]
        curves=np.maximum.accumulate(np.clip(np.rint(self.curves(t)),0,255),axis=1).astype(int)
        return dict(Y=Y,A=A,B=B,beta=bs,curves=curves)


def fit(slot,tier,ev=0.,fold=None,nfev=60):
    started=time.monotonic();P=Problem(slot,tier,ev,fold);sol=P.solve(nfev);raw=P.quantize(sol.x)
    trust=CONFIG['integer_trust_factor_by_slot'][slot] if ev==0 else 1.
    q=r.blend_integer(P.D,raw,trust)
    cfg={**CONFIG,'anchor_EV':ev,'T1_bound_codes':28 if ev else 12,
         'backup_shared_curve_only':P.shared,'backup_free_2x2':False if P.shared else bool(P.nf)}
    out=dict(slot=slot,tier=tier,anchor_EV=ev,fold=fold,config=cfg,theta=sol.x,quantized=q,
             unblended_quantized=raw,integer_trust_factor=trust,
             solve=dict(success=bool(sol.success),status=int(sol.status),nfev=int(sol.nfev),cost=float(2*sol.cost),optimality=float(sol.optimality)),
             scores=r.score(P.D,q))
    if fold and fold.startswith('h'):
        e=out['scores']['screen']['error'][P.screen_eval]
        out['heldout']=dict(error=e,stats=r.stats(e),labels=P.D.screen['labels'][P.screen_eval],
                            baseline=P.D.screen['baseline'][P.screen_eval])
    elif fold:
        i=P.chart_eval
        out['heldout']={str(iso):float(out['scores'][str(iso)]['chart_errors'][i]) for iso in (200,1600)}
        out['heldout']['label']=P.D.chart[200]['labels'][i]
    out['seconds']=time.monotonic()-started
    suffix='full' if fold is None else fold
    dest=r.LOCAL/'fits'/f'{slot}_{tier}_{ev:+.1f}_{suffix}.json'
    r.dump(dest,out)
    print(r.jsonable(dict(path=str(dest.relative_to(r.HERE)),seconds=round(out['seconds'],2),solve=out['solve'],screen=out['scores']['screen']['stats'],physical=out['scores']['physical']['stats'])),flush=True)
    return out


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('slot',choices=['01','02']);ap.add_argument('tier',choices=['a','b','c'])
    ap.add_argument('--ev',type=float,default=0.,choices=[0.,-.3]);ap.add_argument('--fold');ap.add_argument('--nfev',type=int,default=60)
    args=ap.parse_args();fit(args.slot,args.tier,args.ev,args.fold,args.nfev)
