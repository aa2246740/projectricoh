#!/usr/bin/env python3
"""T-only model diagnostics with sealed V/card evaluation and no record edits."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import np,ROOT,LOCAL,dump,read,de,stats
import os
import types
import ast
import hashlib
import time


def load_solver():
    """Use the shipped fit_fast guarded_normal policy, without its shared I/O."""
    rt=types.ModuleType('blue_solver_runtime')
    rt.np=np;rt.LOCAL=LOCAL;rt.hashlib=hashlib
    def output(path,value):
        p=Path(path).resolve();assert p.is_relative_to(LOCAL)
        dump(p.relative_to(LOCAL),value)
    rt.dump=output
    sys.modules[rt.__name__]=rt
    aliases={'runtime':rt.__name__,'solver':'blue_fit_fast_solver'}
    def relocated(name,source):
        tree=ast.parse(source.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):
                for item in n.names:
                    if item.name in aliases:
                        old=item.name;item.name=aliases[old];item.asname=item.asname or old
            if isinstance(n,ast.ImportFrom) and n.module in aliases:n.module=aliases[n.module]
        ast.fix_missing_locations(tree)
        m=types.ModuleType(name);m.__file__=str(source);sys.modules[name]=m
        exec(compile(tree,str(source),'exec'),m.__dict__)
        return m
    relocated('blue_fit_fast_solver',ROOT/'tools/fit_fast/solver.py')
    guarded=relocated('blue_fit_fast_guarded',ROOT/'tools/fit_fast/guarded.py')
    os.environ['FIT_FAST_GUARD_FACTOR']='normal'
    os.environ['FIT_FAST_SOLVER']='guarded_normal'
    return guarded


class LeastProblem:
    def __init__(self,fn,start,lower,upper,key,x,want,ref):
        self.fn=fn;self.np=len(start);self.lower=np.array(lower);self.upper=np.array(upper)
        self.x=x;self.want=want;self.config={'key':key};self.c=types.SimpleNamespace(row=ref.row)
        self.cache=None
    def residual(self,p):return self.fn(p)
    def evaluate(self,p):
        value=self.fn(p);J=np.empty((len(value),len(p)))
        for j in range(len(p)):
            eps=1e-4;hi=p.copy();lo=p.copy();hi[j]+=eps;lo[j]-=eps
            J[:,j]=(self.fn(hi)-self.fn(lo))/(2*eps)
        return value,J


class Data:
    def __init__(self,ref,rows):
        self.ref=ref;self.rows=[r for r in rows if r['setting'] not in ('04 Std','03 HC BW')]
        self.x=np.array([r['conditioned_input'] for r in self.rows])
        self.obs=np.array([r['observed_rgb'] for r in self.rows])
        self.y=np.array([r['y'] for r in self.rows]);self.ci=np.array([r['ci'] for r in self.rows])
        self.h=np.angle(self.ci,deg=True)%360;self.cm=abs(self.ci)
        self.table=ref.model.engine.table;self.S=self.table.S;self.nodes=self.table.nodes
        self.W=self.table.kernel_weights(self.h,self.cm)
        D=a.module('blue_dat_extra',ROOT/'research/v39_g153/dat_format.py')
        raw=(ROOT/'firmware/package_v310_g156_test/GXRCE.DAT').read_bytes()
        row50=ref.mm.MatrixRow.from_bytes(D.expand(raw,0,4)[216:244])
        self.route50=np.angle(row50.apply(np.array([r['pre'] for r in self.rows]))[1],deg=True)%360
        self.route04=np.angle(ref.row.apply(ref.model.pre(ref.entries['04 Std'],self.x))[1],deg=True)%360
        rgbp=np.array([r['pre'] for r in self.rows])
        lo=rgbp.min(1);hi=rgbp.max(1);den=np.maximum(hi-lo,1e-9)
        # A physically different routing coordinate is tested before calibration.
        self.route_raw=np.angle(ref.row.apply(self.x/16)[1],deg=True)%360
        official=read(ROOT/'research/module_adapt/local/official_parameters.json')['units']['50mm']
        ab50=np.array([ref.fs.decode_word(D.expand(raw,0,4)[i:i+4]) for i in range(115,211,4)])
        disp=read(ROOT/'research/stage2e_verification/local/measurements.json')['frames']['R8051160']['meta']['display']
        d0=np.zeros(24);d1=np.zeros(24)
        for j,color in enumerate(('orange','green','blue','red','magenta')):
            ix=np.array([bool(int(official['mask'][j])&(1<<s)) for s in range(24)])
            level=int(disp[color+'_hue'])-1
            d0[ix]=np.array(official['d0_levels'])[level,ix];d1[ix]=np.array(official['d1_levels'])[level,ix]
        S50=((ab50[:,0]+d0)-1j*(ab50[:,1]+d1))/32
        self.route_transfer=self.h+np.angle((self.W@self.S)/(self.W@S50),deg=True)
        self.route_transfer_inverse=self.h-np.angle((self.W@self.S)/(self.W@S50),deg=True)
        self.route_stock=self.h+np.angle(self.W@self.S,deg=True)
        self.W=self.table.kernel_weights(self.h,self.cm)
        self.Z=np.zeros((len(self.rows),24),complex)
        for name,b in ref.entries.items():
            if name in ('04 Std','03 HC BW'):continue
            ab=np.array([ref.fs.decode_word(b[i:i+4]) for i in range(115,211,4)])
            z=ref.fs.Z_of_words(ab[:,0],ab[:,1],ref.model.engine.ctx)
            self.Z[np.array([r['setting']==name for r in self.rows])]=z
        self.base=self.ci*(self.W@self.S)
        self.old=self.predict('old',np.zeros(0))
        assert np.max(abs(self.old-np.array([r['predicted_rgb'] for r in self.rows])))<1e-8
        self.train=np.array([r['split']=='T' for r in self.rows])
        self.train_lab=ref.fs.lab_from_codes(self.obs[self.train])
    def predict(self,kind,p):
        W=self.W;Z=self.Z;gain=self.table.gain;k=self.table.k;h=self.h.copy()
        if kind in ('k','k_gain'): k=p[0]
        if kind=='k_gain':gain=gain*p[1]
        if kind in ('shift','shift_scale','nodes'):
            if kind.startswith('shift'):h+=p[0]
            else:
                # Periodic displacement, six knots; no V or card values enter.
                hh=self.h%360
                step=360/len(p)
                h+=np.interp(hh,np.arange(-1,len(p)+2)*step,np.r_[p[-1],p,p[0],p[1]])
            W=self.table.kernel_weights(h,self.cm)
        if kind=='shift_scale':gain=gain*p[1]
        if kind in ('route50','route04','route_raw','route_transfer','route_transfer_inverse','route_stock'):
            h=getattr(self,kind);W=self.table.kernel_weights(h,self.cm)
        if kind=='ellipse':
            mapped=np.exp(1j*np.deg2rad(p[0]))*(self.ci+(p[1]+1j*p[2])*self.ci.conjugate())
            W=self.table.kernel_weights(np.angle(mapped,deg=True)%360,self.cm)
        if kind=='hard':
            t=self.table;old=t.kernel;t.kernel='hard'
            try:W=t.kernel_weights(h,self.cm)
            finally:t.kernel=old
        if kind=='quant_pre':
            ci=[];y=[]
            for r in self.rows:
                b=self.ref.entries[r['setting']]
                yy,cc=self.ref.mm.MatrixRow.from_bytes(b[216:244]).apply(np.rint(r['pre'])[None,:])
                ci.append(cc[0]);y.append(yy[0])
            ci=np.array(ci);W=self.table.kernel_weights(np.angle(ci,deg=True)%360,abs(ci))
            z=np.abs(Z)*np.exp(1j*k*np.angle(Z))
            co=ci*(W@self.S+np.sum(W*gain*self.S*(z-1),axis=1))
            return np.clip(self.ref.mm.rgb_from_ycc(np.array(y),co),0,255)
        if kind=='clip_ci':
            ci=np.clip(self.ci.real,-128,127)+1j*np.clip(self.ci.imag,-128,127)
            W=self.table.kernel_weights(np.angle(ci,deg=True)%360,abs(ci))
        if kind=='polar_mix':
            z=np.abs(Z)*np.exp(1j*k*np.angle(Z))
            ratio=np.exp(np.sum(W*gain*np.log(z),axis=1))
            co=self.base*ratio
        else:
            z=np.abs(Z)*np.exp(1j*k*np.angle(Z))
            delta=np.sum(W*gain*self.S*(z-1),axis=1)/(W@self.S)
            co=self.base*(1+delta)
            if kind=='delta_linear':
                change=co-self.base
                co=self.base+(p[0]+1j*p[1])*change+(p[2]+1j*p[3])*change.conjugate()
        return np.clip(self.ref.mm.rgb_from_ycc(self.y,co),0,255)
    def score(self,pred):
        error=de(pred,self.obs);out={}
        for name in sorted(set(r['setting'] for r in self.rows)):
            for split in ('T','V','card'):
                ix=np.array([r['setting']==name and r['split']==split for r in self.rows])
                if ix.any():out[name+' '+split]=stats(error[ix])
        return out
    def residual(self,kind,p):
        pred=self.predict(kind,p)[self.train]
        # Frozen engine's exact DE00 components; scoring uses noon D50 DE00.
        loss=self.ref.fs.de00_components(self.train_lab,self.ref.fs.lab_from_codes(pred)).ravel()/np.sqrt(self.train.sum())
        ridge=(p*.003 if kind=='nodes' else p*0)
        return np.r_[loss,ridge]


def main():
    _,ref,rows=a.load();d=Data(ref,rows);g=load_solver()
    models={}
    for kind,start,lo,hi in [
        ('old',[],[],[]),('hard',[],[],[]),('quant_pre',[],[],[]),('clip_ci',[],[],[]),
        ('polar_mix',[],[],[]),('route50',[],[],[]),('route04',[],[],[]),('route_raw',[],[],[]),
        ('route_transfer',[],[],[]),('route_transfer_inverse',[],[],[]),('route_stock',[],[],[]),
        ('k',[d.table.k],[.3],[1.7]),
        ('k_gain',[d.table.k,1.],[.3,.3],[1.7,1.7]),
        ('shift',[0.],[-25.],[25.]),('shift_scale',[0.,1.],[-25.,.3],[25.,1.7]),
        ('ellipse',[0.,0.,0.],[-30.,-.6,-.6],[30.,.6,.6]),
        ('nodes',[0.]*6,[-35.]*6,[35.]*6)]:
        if len(start):
            start=np.array(start);P=LeastProblem(lambda p:d.residual(kind,p),start,lo,hi,kind,d.x[d.train],d.obs[d.train],ref)
            p,receipt=g.solve(P,start,90)
        else:p=np.array([]);receipt={}
        result=dict(parameters=p,receipt=receipt,scores=d.score(d.predict(kind,p)))
        models[kind]=result;dump('model-experiments.json',models)
        print(kind,np.round(p,5),[(n,round(s['median'],3),round(s['p95'],3)) for n,s in result['scores'].items() if n.endswith(' V')],flush=True)
    dump('candidate_policy.json',dict(training='all seven colour recipes, T1-T4, central 40%',
        holdout='V1-V4 and all nine card frames',solver='fit_fast guarded_normal',
        reference_sources={str(p.relative_to(ROOT)):a.sha(p) for p in [ROOT/'tools/fit_fast/guarded.py',ROOT/'tools/fit_fast/solver.py']},
        caveat='candidate family comparisons do not make V/card a second independent final validation'))


if __name__=='__main__':main()
