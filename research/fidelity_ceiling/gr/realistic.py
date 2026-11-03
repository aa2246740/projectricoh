#!/usr/bin/env python3
"""Mixed-integer 24-node GR study. Parameter arrays stay in local/realistic/.

No upstream entrypoints, firmware payloads, downloads, devices, or background
work. Coefficients and Y are refitted between integer node-search passes.
"""
import os
for _k in ('OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_k]='1'
import sys
sys.dont_write_bytecode=True
import argparse
import copy
from collections import OrderedDict
import importlib.util
import json
import time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LOCAL=HERE/'local/realistic'
spec=importlib.util.spec_from_file_location('ceil_base',HERE/'analyze.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
r5=a.load('realistic_r5',ROOT/'research/color_fit_v2/gr_round5/fit_round5.py')
g,e,fs,mm=r5.g,r5.e,r5.fs,r5.mm
RAD=np.pi/180
KINDS=('R0','R1','R2','R3','R4','R5')


def baseline(slot):
    return g.read(g.LOCAL/f'fit_{slot}_r5.json')


def stock_codes():
    rows=a.read(ROOT/'research/beyond24/local/front_rows.json')
    return np.array(next(r for r in rows if r['row']==1)['high'],int)


def valid_codes(c):
    c=np.asarray(c,int)
    return c.shape==(24,) and np.diff(np.r_[c,c[0]+256]).min()>=2


def nodes_for(c):return np.asarray(c,float)*360/256


def weights(data,c,h,r):
    table=copy.copy(data.table);table.nodes=nodes_for(c)
    return table.kernel_weights(np.asarray(h),np.asarray(r))


def coefficient_parts(data,t):
    z=(t[2:26]+data.ctx.d0/32-1j*(t[26:50]+data.ctx.d1/32))/data.ctx.S_eff
    z=np.where(abs(z)<1e-8,1e-8+0j,z)
    rho=np.log(abs(z));phi=np.angle(z)
    E=np.exp(rho+1j*data.table.k*phi)
    ra=1/(data.ctx.S_eff*z);rb=-1j*ra
    da=E*(ra.real+1j*data.table.k*ra.imag)
    db=E*(rb.real+1j*data.table.k*rb.imag)
    return z,E,da,db


class Problem:
    def __init__(self,slot,kind,fold=None,iso=200):
        self.slot,self.kind,self.fold=slot,kind,fold
        self.D=g.Data(slot,iso);self.D.current=baseline(slot)
        self.source_d0=self.D.ctx.d0.copy();self.source_d1=self.D.ctx.d1.copy()
        cfg=self.D.current['fit_config'];self.cfg=cfg
        self.P=r5.Problem(self.D,exclude=fold,smooth=cfg['smooth'],synth_factor=cfg['synth_factor'],
             y_ridge=cfg['y_ridge'],prior=cfg['prior'],safety_margin=cfg['safety_margin'],
             grey_margin=cfg['grey_training_margin'],grey_strength=cfg['grey_guard_strength'],
             dual_grey_guard=(slot=='01'))
        self.crossdata=self.P.cross
        self.free=np.array([0,11,17,23] if kind=='R2' else range(24) if kind=='R3' else [],int)
        self.nf=len(self.free);self.t2=kind in ('R4','R5');self.t1=kind=='R5'
        self.ib=50;self.ig=50+2*self.nf;self.ic=self.ig+(7 if self.t2 else 0)
        self.np=self.ic+(99 if self.t1 else 0)
        self.original=stock_codes();assert valid_codes(self.original)
        self.x=np.vstack([self.D.a['chart_x']*self.D.a['exposure'],
                         np.repeat(self.D.a['gray_x'][:,None],3,axis=1),
                         self.D.generated['aux_x']*self.D.a['exposure']])
        self.target=self.P.lt.copy();self.w=self.P.w.copy()
        if fold is not None:self.w[fold]=0
        self.limit=np.full(len(self.w),np.inf);self.strength=np.zeros(len(self.w))
        self.limit[self.P.protected]=self.P.limits
        self.strength[self.P.protected]=self.P.guard_weights
        if self.P.cross is not None:
            cross=self.P.cross;cross.current=baseline(slot)
            rr,aa,bb=e.f.unpack_solution(cross.current)
            pred=cross.forward(cross.a['chart_pre'],rr,fs.Z_of_words(aa,bb,cross.ctx))[0]
            limits=fs.delta_e00(cross.a['chart_target'],pred)[cross.greys]+cfg['grey_training_margin']
            self.x=np.vstack([self.x,cross.a['chart_x'][cross.greys]*cross.a['exposure']])
            self.target=np.vstack([self.target,cross.a['chart_target'][cross.greys]])
            self.w=np.r_[self.w,np.zeros(6)]
            self.limit=np.r_[self.limit,limits];self.strength=np.r_[self.strength,np.full(6,cfg['grey_guard_strength'])]
        if kind=='R3':
            # Clearing the five T masks also removes their neutral-setting
            # additive modifiers. Keep the calibrated stock reference, but
            # represent the four raw coefficients without those modifiers.
            for data in [self.D,*([self.crossdata] if self.crossdata is not None else [])]:
                data.ctx=copy.copy(data.ctx);data.ctx.d0=np.zeros(24);data.ctx.d1=np.zeros(24)
        if kind=='R2':
            assert np.all(self.source_d0[self.free]==0) and np.all(self.source_d1[self.free]==0)
        self.H=e.interp_weights(self.x,self.D.a['curve_x'])
        self.base=np.tile(self.D.a['curve_y'],(3,1)).astype(float)
        self.pre=np.einsum('ncj,cj->nc',self.H,self.base)
        self.stockY=self.D.rows['row1'].coef[0]/1024
        self.stockC=self.D.rows['row1'].coef[1:]/1024
        self.gain_nodes=np.linspace(0,255,7)
        self.sh=np.tile(np.arange(0,360,5.),4)
        self.sr=np.repeat([.25,3.,40.,180.],72)
        self.sci=self.sr*np.exp(1j*RAD*self.sh)
        self.stock_ref=weights(self.D,self.original,self.sh,self.sr)@self.D.ctx.S_eff
        self.cyc=np.roll(np.eye(24),-1,axis=1)-np.eye(24)
        self.cache={}
        self._geometry_memo=OrderedDict()
        self.codes=self.original.copy()
        self.geometry(self.codes)

    def geometry(self,codes):
        self.codes=np.asarray(codes,int).copy();assert valid_codes(self.codes)
        key=tuple(self.codes)
        if key in self._geometry_memo:
            attributes,self.cache=self._geometry_memo.pop(key)
            for name,value in attributes.items():setattr(self,name,value)
            self._geometry_memo[key]=(attributes,self.cache)
            return
        self.cache={}
        near=(nodes_for(self.codes)[:,None]+np.array([-.8,-.2,-.1,-.02,0.,.02,.1,.2,.8])).ravel()%360
        hue=np.unique(np.r_[np.arange(0,360,5.),near])
        self.sh=np.tile(hue,4);self.sr=np.repeat([.25,3.,40.,180.],len(hue))
        self.sci=self.sr*np.exp(1j*RAD*self.sh)
        self.stock_ref=weights(self.D,self.original,self.sh,self.sr)@self.D.ctx.S_eff
        self.sw=weights(self.D,self.codes,self.sh,self.sr)
        eps=.001
        self.swd=(weights(self.D,self.codes,self.sh+eps,self.sr)-weights(self.D,self.codes,self.sh-eps,self.sr))/(2*eps)
        self.sbase=self.sw@self.D.ctx.S_eff;self.sbased=self.swd@self.D.ctx.S_eff
        self.sG=self.sw*self.D.table.gain;self.sGd=self.swd*self.D.table.gain
        names=('sh','sr','sci','stock_ref','sw','swd','sbase','sbased','sG','sGd')
        self._geometry_memo[key]=({name:getattr(self,name) for name in names},self.cache)
        if len(self._geometry_memo)>8:self._geometry_memo.popitem(last=False)

    def initial(self):
        row,A,B=e.f.unpack_solution(self.D.current)
        t=np.zeros(self.np);t[:2]=row.coef[0,[0,2]]/1024
        t[2:26]=A/32;t[26:50]=B/32
        if self.kind=='R3':t[2:26]+=self.source_d0/32;t[26:50]+=self.source_d1/32
        if self.t2:t[self.ig:self.ic]=1
        if self.t1:
            inc=np.maximum(np.diff(self.base,prepend=0,axis=1),.01)
            t[self.ic:]=np.log(inc/np.maximum(255-self.base[:,-1,None],.1)).ravel()
        return t

    def curves(self,t,jac=False):
        if hasattr(self,'forced_curves'):
            return (self.forced_curves,np.zeros((3,33,33))) if jac else self.forced_curves
        if not self.t1:return (self.base,None) if jac else self.base
        v=t[self.ic:].reshape(3,33);ex=np.exp(np.clip(v,-30,30));p=ex/(1+ex.sum(1,keepdims=True))
        cum=np.cumsum(p,axis=1);q=255*cum
        if not jac:return q
        J=255*(np.tril(np.ones((33,33)))[None,:,:]*p[:,None,:]-cum[:,:,None]*p[:,None,:])
        return q,J

    def prepare(self,pre):
        yc=pre@self.stockC.T;ci=yc[:,0]+1j*yc[:,1]
        w=weights(self.D,self.codes,mm.hue_deg(ci),abs(ci))
        wg=w*self.D.table.gain
        if self.crossdata is not None and len(pre)==len(self.x):
            w[-6:]=weights(self.crossdata,self.codes,mm.hue_deg(ci[-6:]),abs(ci[-6:]))
            wg[-6:]=w[-6:]*self.crossdata.table.gain
        return ci,w,wg

    def parts(self,t,pre=None,want_jac=False):
        if pre is None:
            pre=np.einsum('ncj,cj->nc',self.H,self.curves(t)) if self.t1 else self.pre
            if not self.t1 and 'train' in self.cache:ci,w,wg=self.cache['train']
            else:
                ci,w,wg=self.prepare(pre)
                if not self.t1:self.cache['train']=(ci,w,wg)
        else:ci,w,wg=self.prepare(pre)
        yrow=np.array([t[0],1-t[0]-t[1],t[1]])
        Y=pre@yrow
        z,E,da,db=coefficient_parts(self.D,t)
        delta=self.D.ctx.S_eff*(E-1)
        beta=np.zeros(24,complex)
        if self.nf:beta[self.free]=t[self.ib:self.ib+self.nf]+1j*t[self.ib+self.nf:self.ig]
        before=ci*(w@self.D.ctx.S_eff+wg@delta)+np.conj(ci)*(wg@beta)
        cross=None
        if self.crossdata is not None and len(pre)==len(self.x):
            cross=self.crossdata;_,ec,dac,dbc=coefficient_parts(cross,t)
            before[-6:]=ci[-6:]*(w[-6:]@cross.ctx.S_eff+wg[-6:]@(cross.ctx.S_eff*(ec-1)))+np.conj(ci[-6:])*(wg[-6:]@beta)
        gain=np.ones(len(Y));gb=None;gs=np.zeros(len(Y))
        if self.t2:
            gb=e.interp_weights(Y,self.gain_nodes);gain=gb@t[self.ig:self.ic]
            seg=np.clip(np.searchsorted(self.gain_nodes,Y,side='right')-1,0,5)
            gs=np.diff(t[self.ig:self.ic])[seg]/np.diff(self.gain_nodes)[seg]
            gs[(Y<=0)|(Y>=255)]=0
        co=before*gain
        if not want_jac:return Y,co
        dy=np.zeros((len(Y),self.np));dy[:,0]=pre[:,0]-pre[:,1];dy[:,1]=pre[:,2]-pre[:,1]
        dc=before[:,None]*gs[:,None]*dy
        dc[:,2:26]+=ci[:,None]*wg*(self.D.ctx.S_eff*da)[None,:]*gain[:,None]
        dc[:,26:50]+=ci[:,None]*wg*(self.D.ctx.S_eff*db)[None,:]*gain[:,None]
        if cross is not None:
            dc[-6:,2:26]=ci[-6:,None]*wg[-6:]*(cross.ctx.S_eff*dac)[None,:]*gain[-6:,None]
            dc[-6:,26:50]=ci[-6:,None]*wg[-6:]*(cross.ctx.S_eff*dbc)[None,:]*gain[-6:,None]
        if self.nf:
            b=np.conj(ci[:,None])*wg[:,self.free]*gain[:,None]
            dc[:,self.ib:self.ib+self.nf]=b;dc[:,self.ib+self.nf:self.ig]=1j*b
        if self.t2:dc[:,self.ig:self.ic]=before[:,None]*gb
        return Y,co,dy,dc,pre

    def losses(self,y,co):
        lab=fs.lab_from_codes(np.clip(mm.rgb_from_ycc(y,co),0,255))
        dr=fs.de00_components(self.target,lab)*np.sqrt(self.w[:,None])
        err=fs.delta_e00(self.target,lab)
        guard=self.strength*np.maximum(err-self.limit,0)
        return np.column_stack([dr,guard])

    def safety(self,t,jac=False):
        z,E,da,db=coefficient_parts(self.D,t)
        de=self.D.ctx.S_eff*(E-1)
        beta=np.zeros(24,complex)
        if self.nf:beta[self.free]=t[self.ib:self.ib+self.nf]+1j*t[self.ib+self.nf:self.ig]
        T=self.sbase+self.sG@de;Td=self.sbased+self.sGd@de
        U=self.sG@beta;Ud=self.sGd@beta
        c=self.sci*T+np.conj(self.sci)*U
        cd=self.sci*(1j*RAD*T+Td)+np.conj(self.sci)*(-1j*RAD*U+Ud)
        den=np.where(abs(c)<1e-10,1e-10+0j,c)
        hd=(cd/den).imag/RAD;sl=(cd/den).real
        ming=float(np.min(t[self.ig:self.ic])) if self.t2 else 1.
        sc=abs(c/(self.sci*self.stock_ref))*ming
        htarget=.2+self.cfg['safety_margin']
        masks=[hd<htarget,sl>.045,sl<-.045,sc<.28]
        vals=[np.minimum(hd-htarget,0),np.maximum(sl-.045,0),np.minimum(sl+.045,0),np.minimum(sc-.28,0)]
        res=200*np.concatenate(vals)
        if not jac:return res
        Jc=np.zeros((len(c),self.np),complex);Jd=Jc.copy()
        for start,der in ((2,da),(26,db)):
            fac=self.D.ctx.S_eff*der
            Jc[:,start:start+24]=self.sci[:,None]*self.sG*fac
            Jd[:,start:start+24]=self.sci[:,None]*(1j*RAD*self.sG+self.sGd)*fac
        if self.nf:
            v=np.conj(self.sci[:,None])*self.sG[:,self.free]
            vd=np.conj(self.sci[:,None])*(-1j*RAD*self.sG[:,self.free]+self.sGd[:,self.free])
            Jc[:,self.ib:self.ib+self.nf]=v;Jc[:,self.ib+self.nf:self.ig]=1j*v
            Jd[:,self.ib:self.ib+self.nf]=vd;Jd[:,self.ib+self.nf:self.ig]=1j*vd
        jr=(Jd*den[:,None]-cd[:,None]*Jc)/den[:,None]**2
        jscale=sc[:,None]*np.real(Jc/den[:,None])
        if self.t2:
            k=self.ig+int(np.argmin(t[self.ig:self.ic]));jscale[:,k]+=sc/max(ming,1e-8)
        J=200*np.vstack([jr.imag/RAD*masks[0][:,None],jr.real*masks[1][:,None],
                        jr.real*masks[2][:,None],jscale*masks[3][:,None]])
        return res,J

    def regularization(self,t,jac=False):
        z,E,_,_=coefficient_parts(self.D,t)
        rho=np.log(abs(z));phi=np.angle(z)
        ra=1/(self.D.ctx.S_eff*z);rb=-1j*ra
        jr=np.zeros((24,self.np));jp=jr.copy()
        for start,d in ((2,ra),(26,rb)):
            jr[:,start:start+24]=np.diag(d.real);jp[:,start:start+24]=np.diag(d.imag)
        ks=np.sqrt(self.cfg['smooth']);kr=np.sqrt(.05)
        vals=[ks/.1*(self.cyc@rho),ks/np.deg2rad(5)*(self.cyc@phi),kr/.1*rho,kr/np.deg2rad(5)*phi]
        js=[ks/.1*self.cyc@jr,ks/np.deg2rad(5)*self.cyc@jp,kr/.1*jr,kr/np.deg2rad(5)*jp]
        Y=np.array([t[0],1-t[0]-t[1],t[1]])
        jy=np.zeros((3,self.np));jy[:,:2]=[[1,0],[-1,-1],[0,1]]
        vals.append(np.sqrt(self.cfg['y_ridge'])/.05*(Y-self.stockY));js.append(np.sqrt(self.cfg['y_ridge'])/.05*jy)
        # All four signed coefficients must fit seven magnitude bits.
        ae=t[2:26]+self.D.ctx.d0/32;be=t[26:50]+self.D.ctx.d1/32
        M=np.column_stack([ae,be,-be,ae])
        mj=np.zeros((24,4,self.np));ii=np.arange(24)
        mj[ii,0,2+ii]=1;mj[ii,3,2+ii]=1;mj[ii,1,26+ii]=1;mj[ii,2,26+ii]=-1
        if self.nf:
            f=self.free;u=t[self.ib:self.ib+self.nf];v=t[self.ib+self.nf:self.ig]
            M[f,0]+=u;M[f,3]-=u;M[f,1]+=v;M[f,2]+=v
            mj[f,0,self.ib+np.arange(self.nf)]=1;mj[f,3,self.ib+np.arange(self.nf)]=-1
            mj[f,1,self.ib+self.nf+np.arange(self.nf)]=1;mj[f,2,self.ib+self.nf+np.arange(self.nf)]=1
            full=np.zeros((24,2));full[f,0]=u;full[f,1]=v
            bj=np.zeros((24,2,self.np));bj[f,0,self.ib+np.arange(self.nf)]=1;bj[f,1,self.ib+self.nf+np.arange(self.nf)]=1
            scale=np.abs(self.D.ctx.S_eff)[:,None]
            vals.extend([(ks/.1*(self.cyc@(full/scale))).ravel(),(kr/.1*full/scale).ravel()])
            js.extend([(ks/.1*np.einsum('ij,jkp->ikp',self.cyc,bj/scale[:,:,None])).reshape(-1,self.np),
                       (kr/.1*bj/scale[:,:,None]).reshape(-1,self.np)])
        over=abs(M)>127/32
        vals.append((100*np.maximum(abs(M)-127/32,0)).ravel())
        js.append((100*np.sign(M)[:,:,None]*over[:,:,None]*mj).reshape(-1,self.np))
        vals.append(100*np.maximum(abs(Y)-2047/1024,0))
        js.append(100*np.sign(Y)[:,None]*(abs(Y)>2047/1024)[:,None]*jy)
        if self.t2:
            gain=t[self.ig:self.ic];G=np.zeros((7,self.np));G[:,self.ig:self.ic]=np.eye(7)
            vals.extend([np.sqrt(.05)/.3*(gain-1),np.sqrt(.3)/.3*np.diff(gain,n=2)])
            js.extend([np.sqrt(.05)/.3*G,np.sqrt(.3)/.3*np.diff(G,n=2,axis=0)])
        if self.t1:
            q,qj=self.curves(t,True);delta=q-self.base
            v=np.r_[np.sqrt(.02)/8*delta.ravel(),np.sqrt(.3)/2*np.diff(delta,n=2,axis=1).ravel(),20*np.minimum(q[:,-1]-130,0)]
            jj=np.zeros((195,self.np))
            for ch in range(3):
                cols=slice(self.ic+33*ch,self.ic+33*(ch+1))
                jj[ch*33:(ch+1)*33,cols]=np.sqrt(.02)/8*qj[ch]
                jj[99+ch*31:99+(ch+1)*31,cols]=np.sqrt(.3)/2*np.diff(qj[ch],n=2,axis=0)
                jj[192+ch,cols]=20*qj[ch,-1]*(q[ch,-1]<130)
            vals.append(v);js.append(jj)
        # Geometry penalty uses only physical displacement, never held-out data.
        delta=(self.codes-self.original+128)%256-128
        vals.append(.05*delta/8);js.append(np.zeros((24,self.np)))
        rr=np.concatenate(vals)
        return (rr,np.vstack(js)) if jac else rr

    def residual(self,t):
        y,co=self.parts(t)
        return np.r_[self.losses(y,co).ravel(),self.safety(t),self.regularization(t)]

    def jacobian(self,t):
        y,co,dy,dc,pre=self.parts(t,want_jac=True);eps=1e-4
        ly=(self.losses(y+eps,co)-self.losses(y-eps,co))/(2*eps)
        lb=(self.losses(y,co+eps)-self.losses(y,co-eps))/(2*eps)
        lr=(self.losses(y,co+1j*eps)-self.losses(y,co-1j*eps))/(2*eps)
        J=(ly[:,:,None]*dy[:,None,:]+lb[:,:,None]*dc.real[:,None,:]+lr[:,:,None]*dc.imag[:,None,:]).reshape(-1,self.np)
        if self.t1:
            _,qj=self.curves(t,True)
            for ch in range(3):
                pp,pm=pre.copy(),pre.copy();pp[:,ch]+=eps;pm[:,ch]-=eps
                yp,cp=self.parts(t,pp);ym,cm=self.parts(t,pm)
                deriv=(self.losses(yp,cp)-self.losses(ym,cm))/(2*eps)
                dpre=self.H[:,ch]@qj[ch]
                J[:,self.ic+33*ch:self.ic+33*(ch+1)]=(deriv[:,:,None]*dpre[:,None,:]).reshape(-1,33)
        return np.vstack([J,self.safety(t,True)[1],self.regularization(t,True)[1]])

    def solve(self,t,nfev=75):
        lo=np.full(self.np,-127/32.);hi=np.full(self.np,127/32.)
        lo[:2]=self.stockY[[0,2]]-.4;hi[:2]=self.stockY[[0,2]]+.4
        if self.t2:lo[self.ig:self.ic]=.25;hi[self.ig:self.ic]=1.6
        if self.t1:lo[self.ic:]=-20;hi[self.ic:]=10
        sol=least_squares(self.residual,np.clip(t,lo+1e-8,hi-1e-8),jac=self.jacobian,
             bounds=(lo,hi),max_nfev=nfev,x_scale='jac',ftol=2e-6,xtol=2e-6,gtol=1e-5)
        return sol.x,dict(success=bool(sol.success),status=int(sol.status),nfev=int(sol.nfev),
                          optimality=float(sol.optimality),cost=float(2*sol.cost))

    def quantize(self,t):
        q=t.copy();yn=np.rint(t[:2]*1024).astype(int);q[:2]=yn/1024
        q[2:50]=np.rint(q[2:50]*32)/32
        if self.nf:
            f=self.free;A=t[2:26][f];B=t[26:50][f]
            u=t[self.ib:self.ib+self.nf];v=t[self.ib+self.nf:self.ig]
            m=np.clip(np.rint(32*np.column_stack([A+u,B+v,-B+v,A-u])),-127,127)/32
            q[2+f]=(m[:,0]+m[:,3])/2;q[26+f]=(m[:,1]-m[:,2])/2
            q[self.ib:self.ib+self.nf]=(m[:,0]-m[:,3])/2
            q[self.ib+self.nf:self.ig]=(m[:,1]+m[:,2])/2
        curves=np.maximum.accumulate(np.clip(np.rint(self.curves(t)),0,255),axis=1)
        if self.t2:q[self.ig:self.ic]=np.rint(t[self.ig:self.ic]*64)/64
        return q,curves

    def integer_polish(self,q,curves,passes=1):
        self.forced_curves=curves.copy()
        best=float(np.sum(self.residual(q)**2));moves=0
        # Every trial is scored only on this fold's declared training loss.
        for turn in range(passes):
            for d0,d1 in ((1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)):
                v=q.copy();v[:2]+=np.array([d0,d1])/1024
                cost=float(np.sum(self.residual(v)**2))
                if cost<best-1e-8:q,best=v,cost;moves+=1
            for sector in range(24):
                trials=[]
                if sector not in set(self.free):
                    for col in (2+sector,26+sector):
                        for s in (-1,1):
                            v=q.copy();v[col]+=s/32;trials.append(v)
                else:
                    j=int(np.where(self.free==sector)[0][0])
                    for mode in range(4):
                        for sign in (-1,1):
                            v=q.copy();d=sign/64
                            if mode in (0,3):
                                v[2+sector]+=d;v[self.ib+j]+=d if mode==0 else -d
                            else:
                                v[26+sector]+=d if mode==1 else -d
                                v[self.ib+self.nf+j]+=d
                            trials.append(v)
                for v in trials:
                    ae=v[2:26]+self.D.ctx.d0/32;be=v[26:50]+self.D.ctx.d1/32
                    M=np.c_[ae,be,-be,ae]
                    if self.nf:
                        f=self.free;u=v[self.ib:self.ib+self.nf];w=v[self.ib+self.nf:self.ig]
                        M[f,0]+=u;M[f,3]-=u;M[f,1]+=w;M[f,2]+=w
                    if abs(M).max()>127/32+1e-10:continue
                    cost=float(np.sum(self.residual(v)**2))
                    if cost<best-1e-8:q,best=v,cost;moves+=1
            if self.t2:
                for j in range(self.ig,self.ic):
                    for sign in (-1,1):
                        v=q.copy();v[j]+=sign/64
                        if not .25<=v[j]<=1.6:continue
                        cost=float(np.sum(self.residual(v)**2))
                        if cost<best-1e-8:q,best=v,cost;moves+=1
            if self.t1:
                for ch in range(3):
                    for node in range(33):
                        for sign in (-1,1):
                            old=self.forced_curves.copy();v=old.copy();v[ch,node]+=sign
                            if v.min()<0 or v.max()>255 or np.diff(v,axis=1).min()<0:continue
                            self.forced_curves=v;cost=float(np.sum(self.residual(q)**2))
                            if cost<best-1e-8:best=cost;moves+=1
                            else:self.forced_curves=old
        curves=self.forced_curves.copy();del self.forced_curves
        return q,curves,dict(passes=passes,accepted_moves=moves,cost=best)

    def render(self,t,x,codes=None,curves=None,details=False,data=None):
        d=self.D if data is None else data
        codes=self.codes if codes is None else codes
        curves=self.curves(t) if curves is None else np.asarray(curves)
        x=np.asarray(x);pre=np.column_stack([np.interp(x[:,j],d.a['curve_x'],curves[j]) for j in range(3)])
        cc=d.rows['row1'].coef[1:]/1024;yc=pre@cc.T;ci=yc[:,0]+1j*yc[:,1]
        w=weights(d,codes,mm.hue_deg(ci),abs(ci));wg=w*d.table.gain
        z,E,_,_=coefficient_parts(d,t)
        be=np.zeros(24,complex)
        if self.nf:be[self.free]=t[self.ib:self.ib+self.nf]+1j*t[self.ib+self.nf:self.ig]
        co=ci*(w@d.ctx.S_eff+wg@(d.ctx.S_eff*(E-1)))+np.conj(ci)*(wg@be)
        Y=pre@np.array([t[0],1-t[0]-t[1],t[1]])
        if self.t2:co*=np.interp(Y,self.gain_nodes,t[self.ig:self.ic])
        raw=mm.rgb_from_ycc(Y,co);rgb=np.clip(raw,0,255);lab=fs.lab_from_codes(rgb)
        return (lab,dict(y=Y,ci=ci,co=co,rgb=rgb,unclipped_rgb=raw)) if details else lab


def fit(slot,kind,fold=None,passes=2,nfev=75,resume=False):
    start=time.monotonic();p=Problem(slot,kind,fold);theta=p.initial();history=[]
    stem='full' if fold is None else f'fold{fold:02d}'
    checkpoint=LOCAL/f'{slot}_{kind}_{stem}.json'
    if resume:
        previous=a.read(checkpoint);theta=np.array(previous['theta'])
        p.geometry(np.array(previous['node_codes']));history=previous['history']
    theta,info=p.solve(theta,nfev);history.append(dict(stage='initial_coefficients',**info))
    if kind!='R0':
        for sweep in range(passes):
            original=p.codes.copy();best=float(np.sum(p.residual(theta)**2));moves=0
            # Ring-wide phase and local code moves preserve identity and order.
            candidates=[]
            for shift in (-8,-4,-2,2,4,8):candidates.append((None,p.codes+shift))
            for i in range(24):
                for shift in (-4,-2,-1,1,2,4):
                    c=p.codes.copy();c[i]+=shift
                    if valid_codes(c):candidates.append((i,c))
            for i,c in candidates:
                old=p.codes.copy()
                if i is not None:
                    delta=c[i]-original[i];c=old.copy();c[i]+=delta
                if not valid_codes(c):continue
                p.geometry(c);cost=float(np.sum(p.residual(theta)**2))
                if cost<best-1e-7:best=cost;moves+=1
                else:p.geometry(old)
            theta,info=p.solve(theta,nfev)
            history.append(dict(stage=f'node_pass_{sweep+1}',accepted_node_moves=moves,**info))
            if not moves:break
    for retry in range(2):
        if history[-1]['success']:break
        theta,info=p.solve(theta,max(nfev,120))
        history.append(dict(stage=f'bounded_convergence_retry_{retry+1}',**info))
    qt,curves=p.quantize(theta)
    qt,curves,polish=p.integer_polish(qt,curves)
    chart=p.render(qt,p.D.a['chart_x']*p.D.a['exposure'],curves=curves)
    rr=p.render(qt,p.D.a['ring_x']*p.D.a['exposure'],curves=curves)
    ce=fs.delta_e00(p.D.a['chart_target'],chart)
    out=dict(slot=slot,kind=kind,fold=fold,theta=theta,quantized_theta=qt,curves=curves,
       node_codes=p.codes,node_codes_u8=p.codes%256,history=history,fit_config=p.cfg,
       actual_training_config=p.P.config,actual_total_data_weight=float(p.w.sum()),
       integer_polish=polish,
       chart_lab=chart,ring_lab=rr,
       metrics=dict(chart_colour=a.stats(ce[p.D.chrom]),greys=a.stats(ce[p.D.greys]),
         hue_interpolated_ring=a.stats(fs.delta_e00(p.D.a['ring_target'],rr)),
         firmware_ring=a.stats(fs.delta_e00(p.D.generated['ring_target'],rr))),
       held_out=None if fold is None else float(ce[fold]),
       min_node_gap_codes=int(np.diff(np.r_[p.codes,p.codes[0]+256]).min()),
       number_nodes=24,free_T3_sectors=p.free,T3_requires_T_writes=(kind=='R3'),
       firmware_ready=False,camera_acceptance=False,seconds=time.monotonic()-start)
    a.save(LOCAL/f'{slot}_{kind}_{stem}.json',out)
    print(slot,kind,stem,'train',round(out['metrics']['chart_colour']['median'],4),
          'holdout',None if fold is None else round(out['held_out'],4),
          'firmware ring',round(out['metrics']['firmware_ring']['median'],4),
          'nfev',sum(h['nfev'] for h in history),'success',history[-1]['success'],
          'seconds',round(out['seconds'],2),flush=True)


def check(slot,kind):
    p=Problem(slot,kind);t=p.initial();rng=np.random.default_rng(20261021)
    v=rng.normal(size=p.np);v/=np.linalg.norm(v)
    eps=2e-6
    actual=(p.residual(t+eps*v)-p.residual(t-eps*v))/(2*eps)
    predicted=p.jacobian(t)@v
    err=float(np.linalg.norm(actual-predicted)/max(np.linalg.norm(actual),1e-12))
    print(slot,kind,'directional relative error',err,flush=True)
    assert err<5e-4,err
    return err


def snapshot():
    paths=[]
    folder=ROOT/'research/color_fit_v2/gr_round5'
    for p in folder.rglob('*'):
        if p.is_file() and p.suffix in ('.py','.json','.npz'):paths.append(p)
    paths.extend(ROOT/f'research/beyond24/{s}' for s in ('REPORT.md','local/front_rows.json','local/verification.json'))
    a.save(LOCAL/'inputs.json',{str(p.relative_to(ROOT)):dict(sha256=a.sha(p),size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns) for p in sorted(set(paths))})
    print('realistic source snapshot',len(set(paths)),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['fit','check','snapshot'])
    ap.add_argument('--slot',choices=['01','02']);ap.add_argument('--kind',choices=KINDS)
    ap.add_argument('--fold',type=int);ap.add_argument('--start',type=int);ap.add_argument('--stop',type=int)
    ap.add_argument('--passes',type=int,default=2);ap.add_argument('--nfev',type=int,default=75)
    ap.add_argument('--resume',action='store_true')
    ar=ap.parse_args();a.guard();LOCAL.mkdir(exist_ok=True)
    if ar.command=='snapshot':snapshot()
    elif ar.command=='check':check(ar.slot,ar.kind)
    else:
        for fold in range(ar.start,ar.stop) if ar.start is not None else [ar.fold]:
            fit(ar.slot,ar.kind,fold,ar.passes,ar.nfev,ar.resume)
