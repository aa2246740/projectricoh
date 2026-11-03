"""Nested integer-parameter colour models. Unmeasured pixel equations are hypotheses.

The L0/L1 parameterization and regularizer follow film_look_routes/fit.py.
C120/offset alternatives follow hw_refit_r1/model.py, with explicit order branches.
No function exports a camera DAT or performs device I/O.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np, weights, mm
from scipy.optimize import least_squares
import time

INTERNAL = np.asarray(rt.read(rt.LOCAL/'hardware_constants.json')['c120_internal_nodes_u14'],float)
TAIL_NODES = np.r_[0., INTERNAL, 16383.] / 16383
RLUT_X = np.r_[np.arange(32)*128., 4095.]
INPUT_INV = np.array([[0.,1.402],[-.344136,-.714136],[1.772,0.]])

def rgbj(z):
    return np.stack([1.402*z.imag, -.344136*z.real-.714136*z.imag, 1.772*z.real], axis=1)

def physical_weights(h,nodes):
    """Unblurred cyclic linear nodes used by the previously measured H1 c/d basis."""
    nodes=np.asarray(nodes,float)
    hh=(np.asarray(h)-nodes[0])%360+nodes[0]
    ext=np.r_[nodes,nodes[0]+360]
    ix=np.clip(np.searchsorted(ext,hh,side='right')-1,0,23)
    t=(hh-ext[ix])/(ext[ix+1]-ext[ix])
    W=np.zeros((len(hh),24));rows=np.arange(len(hh))
    W[rows,ix]=1-t;W[rows,(ix+1)%24]=t
    return W

def interpolate(values, nodes, table):
    """Three independent linear tables, plus exact local slopes and basis weights."""
    H = weights(values, nodes)
    out = np.einsum('ncj,cj->nc', H, table)
    ix = np.clip(np.searchsorted(nodes, np.clip(values,nodes[0],nodes[-1]), side='right')-1,0,len(nodes)-2)
    slopes = np.stack([(np.diff(table[ch])/np.diff(nodes))[ix[:,ch]] for ch in range(3)],axis=1)
    slopes[(values < nodes[0]) | (values > nodes[-1])] = 0
    return out, H, slopes

def variants():
    yield dict(key='L0', level=0)
    yield dict(key='L1', level=1)
    for axis in ('Y','C'):
        for order in ('post','pre'):
            k = axis+'_'+order
            yield dict(key='L2_'+k,level=2,axis=axis,tail_order=order,parent='L1')
            for tint in ('add_after','Y_before'):
                kk = k+'_'+tint
                yield dict(key='L3_'+kk,level=3,axis=axis,tail_order=order,tint=tint,parent='L2_'+k)
                for ro in ('before','after'):
                    yield dict(key='L4_'+kk+'_R'+ro,level=4,axis=axis,tail_order=order,
                               tint=tint,rlut_order=ro,parent='L3_'+kk)

class Problem:
    def __init__(self,camera,x,target,sw,config):
        self.c,self.x,self.want,self.sw = camera,np.asarray(x),np.asarray(target),np.asarray(sw)
        self.config = dict(config)
        self.level = config['level']
        self.bw = bool(np.max(np.ptp(target,axis=1)) < .5)
        self.legacy = rt.LegacyProblem(camera,x,target,variant='safe' if self.level==0 else 't1',
                                      bw=self.bw,sample_weights=sw)
        self.base_n = self.legacy.np
        self.qstart,self.qend = self.legacy.qstart,self.legacy.t2start
        self.nc = 1 if self.level==0 else 3
        self.blocks = {'base':slice(0,self.base_n)}
        self.np = self.base_n
        self.theta0 = self.legacy.theta0.copy()
        lo,hi = np.full(self.base_n,-255.),np.full(self.base_n,255.)
        lo[:2],hi[:2] = -.8,.8
        if not self.bw:
            lo[2:26],hi[2:26] = np.log(.25),np.log(2.3)
            lo[26:50],hi[26:50] = self.theta0[26:50]-.75,self.theta0[26:50]+.75
        self.lower,self.upper = lo.tolist(),hi.tolist()
        self.extra_ridges = []
        if self.level>=2 and not self.bw: self.add('gains',9,-48,128,.002)
        if self.level>=3:
            self.add('matrix',1 if self.bw else 7,-.8,.8,.025)
            self.add('offsets',1 if self.bw else 5,-32,32,.004)
            if not self.bw: self.add('tint',2,-32,32,.004)
        if self.level>=4:
            self.add('rlut',99,-160,160,.0008)
            if not self.bw: self.add('asym',48,-64,64,.004)
        if config.get('full_fields'):
            if 'gains' in self.blocks:
                sl=self.blocks['gains']
                self.lower[sl]=[-64.]*9;self.upper[sl]=[191.]*9
            if 'matrix' in self.blocks:
                self.lower[:2]=[-3.]*2;self.upper[:2]=[3.]*2
                sl=self.blocks['matrix']
                self.lower[sl]=[-8.]+[-3.]*(sl.stop-sl.start-1)
                self.upper[sl]=[8.]+[3.]*(sl.stop-sl.start-1)
            for key,limit in (('offsets',255.),('tint',127.),('rlut',255.),('asym',254.)):
                if key in self.blocks:
                    sl=self.blocks[key];self.lower[sl]=[-limit]*(sl.stop-sl.start);self.upper[sl]=[limit]*(sl.stop-sl.start)
            if 'offsets' in self.blocks and not self.bw:
                sl=self.blocks['offsets']
                self.lower[sl]=[-255.,-383.,-383.,-255.,-255.]
                self.upper[sl]=[255.,127.,127.,255.,255.]
            if self.level>=4 and not self.bw:
                self.lower[2:26]=[float(np.log(1e-5))]*24;self.upper[2:26]=[float(np.log(32.))]*24
                self.lower[26:50]=[-np.pi]*24;self.upper[26:50]=[np.pi]*24
        self.theta0 = np.r_[self.theta0,np.zeros(self.np-self.base_n)]
        self.R = np.zeros((len(self.legacy.R)+self.np-self.base_n,self.np))
        self.R[:len(self.legacy.R),:self.base_n] = self.legacy.R
        for i,r in enumerate(self.extra_ridges): self.R[len(self.legacy.R)+i,self.base_n+i] = r
        regs = [self.R]
        eye = np.eye(self.np)
        for key,block in self.blocks.items():
            if key=='rlut':
                for ch in range(3):
                    off=block.start+ch*33
                    regs += [(eye[off+j]-2*eye[off+j+1]+eye[off+j+2])[None]*.012 for j in range(31)]
            if key=='gains':
                regs += [(eye[block.start+j]-2*eye[block.start+j+1]+eye[block.start+j+2])[None]*.012 for j in range(7)]
            if key=='asym':
                for ch in range(2):
                    off=block.start+ch*24
                    regs += [(eye[off+j]-eye[off+(j+1)%24])[None]*.012 for j in range(24)]
        self.R = np.vstack(regs)
        self.H = weights(self.x,camera.curve.xs)
        self.sqrtw = np.sqrt(sw/np.mean(sw)/len(sw))[:,None]
        self.tlab = rt.lab_from_codes(self.want)
        self.cache = None
        self.calls=0

    def add(self,key,n,low,high,ridge):
        self.blocks[key]=slice(self.np,self.np+n)
        self.np+=n
        self.lower.extend(np.broadcast_to(low,(n,)))
        self.upper.extend(np.broadcast_to(high,(n,)))
        self.extra_ridges.extend([ridge]*n)

    def get(self,p,key,default):
        return p[self.blocks[key]] if key in self.blocks else default

    def promote(self,previous,p):
        out = self.theta0.copy()
        out[:self.qstart] = p[:previous.qstart]
        q = p[previous.qstart:previous.qend].reshape(previous.nc,33)
        out[self.qstart:self.qend] = np.tile(q,(3 if previous.nc==1 and self.nc==3 else 1,1)).ravel()
        for key,block in self.blocks.items():
            if key!='base' and key in previous.blocks:
                out[block]=p[previous.blocks[key]]
        return out

    def promote_integer(self,previous,p):
        """Embed the previous actual integer model, including its rounding remainder."""
        out=self.promote(previous,p)
        s=previous.state(p,True)
        out[:2]=(s['C'][0,[0,2]]-self.c.row.coef[0,[0,2]])/1024
        q=s['q'] if self.nc==3 else s['q'][1:2]
        if len(q)==1 and self.nc==3:q=np.repeat(q,3,axis=0)
        out[self.qstart:self.qend]=(q-self.c.curve.ys).ravel()
        if not self.bw:
            z=self.c.fs.Z_of_words(s['A'],s['B'],self.c.E.ctx)
            out[2:26]=np.log(np.maximum(abs(z),1e-15));out[26:50]=np.angle(z)
        if 'matrix' in self.blocks:
            C,_=self.legacy.parameters(out[:self.base_n])
            values=[(s['C'][0,1]-C[0,1])/1024]
            if not self.bw:values.extend(((s['C'][1:]-C[1:])/1024).ravel())
            out[self.blocks['matrix']]=values
        for key,value in (('offsets',s['offsets'][:1] if self.bw else s['offsets']),('tint',s['tint']),
                          ('gains',s['gains']-64),('rlut',(s['rlut']-RLUT_X[None,:]).ravel()*255/4095),
                          ('asym',s['asym'].ravel())):
            if key in self.blocks and key in previous.blocks:out[self.blocks[key]]=value
        return out

    def state(self,p,quant=False):
        C,q = self.legacy.parameters(p[:self.base_n])
        extra=self.get(p,'matrix',np.zeros(7))
        if 'matrix' in self.blocks:
            C[0,1]+=extra[0]*1024
            if not self.bw: C[1:]+=extra[1:].reshape(2,3)*1024
        off=self.get(p,'offsets',np.zeros(5)).copy()
        if len(off)==1: off=np.r_[off,np.zeros(4)]
        tint=self.get(p,'tint',np.zeros(2)).copy()
        gains=64+self.get(p,'gains',np.zeros(9)).copy()
        rlut=RLUT_X[None,:]+self.get(p,'rlut',np.zeros(99)).reshape(3,33)*4095/255
        asym=self.get(p,'asym',np.zeros(48)).reshape(2,24).copy()
        A,B=self.c.A.copy(),self.c.B.copy()
        z=None if self.bw else np.exp(p[2:26]+1j*self.c.E.table.k*p[26:50])
        if quant:
            C=np.rint(np.clip(C,-2047,2047)).astype(int)
            if self.level<3: C[0,1]=1024-C[0,0]-C[0,2]
            q=np.rint(np.clip(q,0,255)).astype(int)
            if not self.config.get('free_curves'):q=np.maximum.accumulate(q,axis=1)
            off,tint,gains=[np.rint(v).astype(int) for v in (off,tint,gains)]
            rlut=np.rint(np.clip(rlut,0,4095)).astype(int)
            if not self.config.get('free_curves'):rlut=np.maximum.accumulate(rlut,axis=1)
            if not self.bw:
                ordinary=np.exp(p[2:26]+1j*p[26:50])
                A,B,clipped=self.c.fs.to_words(ordinary,self.c.E.ctx)
                actual=self.c.fs.Z_of_words(A,B,self.c.E.ctx)
                z=abs(actual)*np.exp(1j*self.c.E.table.k*np.angle(actual))
                # Four signed-magnitude bytes. Preserve a,b and quantize c,d separately.
                cd=np.rint(np.vstack([-B,A])+asym)
                cd=np.clip(cd,-127,127)
                asym=cd-np.vstack([-B,A])
        return dict(C=C,q=q,offsets=off,tint=tint,gains=gains,rlut=rlut,asym=asym,
                    z=z,A=A,B=B,quantized=bool(quant))

    def pre(self,s,x,jac=False):
        x=np.asarray(x)
        if 'rlut' not in self.blocks:
            H=self.H if x is self.x else weights(x,self.c.curve.xs)
            q=np.repeat(s['q'],3,axis=0) if len(s['q'])==1 else s['q']
            return np.einsum('ncj,cj->nc',H,q), H, None, None
        if self.config.get('rlut_order')=='before':
            inp,HR,_=interpolate(x,RLUT_X,s['rlut'])
            out,HQ,slope=interpolate(inp,self.c.curve.xs,s['q'])
            return out,HQ,HR,slope
        intermediate,HQ,_=interpolate(x,self.c.curve.xs,s['q'])
        out,HR,slope=interpolate(intermediate,RLUT_X*255/4095,s['rlut']*255/4095)
        return out,HQ,HR,slope

    def sector(self,s,ci):
        table=self.c.E.table
        W=table.kernel_weights(mm.hue_deg(ci),abs(ci))
        G=W*table.gain
        co=ci*(W@self.c.E.ctx.S_eff+G@(self.c.E.ctx.S_eff*(s['z']-1)))
        if 'asym' in self.blocks:
            extra=physical_weights(mm.hue_deg(ci),table.nodes) if self.config.get('asym_kernel')=='physical_linear_H1' else G
            co+=1j/32*(ci.real*(extra@s['asym'][0])+ci.imag*(extra@s['asym'][1]))
        return co,G

    def core(self,s,y,ci,details=False):
        if self.bw:
            raw=np.repeat(y[:,None],3,axis=1)
            return (raw,{}) if details else raw
        tint=s['tint'][0]+1j*s['tint'][1]
        before=self.config.get('tint')=='Y_before'
        c0=ci+tint*np.clip(y/255,0,1) if before else ci
        axis=y/255 if self.config.get('axis','Y')=='Y' else abs(c0)/(128*np.sqrt(2))
        TH=weights(axis,TAIL_NODES)
        gain=TH@s['gains']/64 if 'gains' in self.blocks else np.ones(len(y))
        pre=self.config.get('tail_order')=='pre'
        cs=c0*gain if pre else c0
        sec,G=self.sector(s,cs)
        co=sec if pre else sec*gain
        if not before: co+=tint
        raw=mm.rgb_from_ycc(y,co)
        return (raw,dict(cs=cs,sec=sec,G=G,gain=gain,TH=TH,c0=c0)) if details else raw

    def forward_pre(self,s,pre,details=False):
        inp=pre+INPUT_INV@s['offsets'][3:]
        ycc=inp@(s['C']/1024).T+self.c.row.offsets+s['offsets'][:3]
        y,ci=ycc[:,0],ycc[:,1]-128+1j*(ycc[:,2]-128)
        if details:
            raw,d=self.core(s,y,ci,True)
            return raw,y,ci,inp,d
        return self.core(s,y,ci)

    def predict_state(self,s,x,round_output=True,unclipped=False):
        pre=self.pre(s,x)[0]
        out=self.forward_pre(s,pre)
        if unclipped: return out
        out=np.clip(out,0,255)
        return np.rint(out) if round_output else out

    def constraints(self,p):
        if self.config.get('full_fields'):
            _,qq=self.legacy.parameters(p[:self.base_n])
            mono=0. if self.config.get('free_curves') else 2.
            r=[(mono*np.minimum(np.diff(qq,axis=1),0)).ravel(),(2*np.minimum(qq,0)).ravel(),
               (2*np.maximum(qq-255,0)).ravel()]
            if not self.bw:
                physical=self.c.E.ctx.S_eff*np.exp(p[2:26]+1j*p[26:50])*32
                aa,bb=physical.real-self.c.E.ctx.d0,-physical.imag-self.c.E.ctx.d1
                r += [2*np.maximum(abs(np.r_[aa,bb])-126.8,0)]
        else:r=[self.legacy.constraints(p[:self.base_n])]
        s=self.state(p)
        if 'rlut' in self.blocks:
            mono=0. if self.config.get('free_curves') else 3.
            r += [(mono*np.minimum(np.diff(s['rlut'],axis=1),0)*255/4095).ravel(),
                  (3*np.minimum(s['rlut'],0)*255/4095).ravel(),
                  (3*np.maximum(s['rlut']-4095,0)*255/4095).ravel()]
        if 'matrix' in self.blocks: r += [5*np.maximum(abs(s['C'].ravel())-2047,0)/1024]
        if 'asym' in self.blocks:
            phys=self.c.E.ctx.S_eff*np.exp(p[2:26]+1j*p[26:50])*32
            aa,bb=phys.real-self.c.E.ctx.d0,-phys.imag-self.c.E.ctx.d1
            cd=np.vstack([-bb,aa])+s['asym']
            r += [2*np.maximum(abs(cd)-126.8,0).ravel()]
        return np.concatenate(r)

    def evaluate(self,p):
        if self.cache is not None and np.array_equal(self.cache[0],p): return self.cache[1:]
        self.calls+=1
        s=self.state(p)
        pre,HQ,HR,rslope=self.pre(s,self.x,True)
        raw,y,ci,inp,d=self.forward_pre(s,pre,True)
        def loss(v):
            lab=rt.lab_from_codes(np.clip(v,0,255))
            if self.level==0 and not self.bw:
                lab[np.ptp(self.x,axis=1)<1e-8,1:]=0
            if self.bw:
                mean=(self.tlab[:,0]+lab[:,0])/2
                scale=1+.015*(mean-50)**2/np.sqrt(20+(mean-50)**2)
                v=np.zeros_like(lab);v[:,0]=(lab[:,0]-self.tlab[:,0])/scale
                return v*self.sqrtw
            return rt.de00_components(self.tlab,lab)*self.sqrtw
        residual=loss(raw)
        eps=1e-3
        L=np.empty((len(raw),3,3))
        for ch in range(3):
            v=np.zeros_like(raw);v[:,ch]=eps
            L[:,:,ch]=(loss(raw+v)-loss(raw-v))/(2*eps)
        # Derivatives with respect to the three actual inputs of the colour core.
        coreJ=np.empty((len(raw),3,3))
        coreJ[:,:,0]=(self.core(s,y+eps,ci)-self.core(s,y-eps,ci))/(2*eps)
        coreJ[:,:,1]=(self.core(s,y,ci+eps)-self.core(s,y,ci-eps))/(2*eps)
        coreJ[:,:,2]=(self.core(s,y,ci+1j*eps)-self.core(s,y,ci-1j*eps))/(2*eps)
        J=np.zeros((len(raw),3,self.np))
        J[:,:,0]=coreJ[:,:,0]*(inp[:,0]-inp[:,1])[:,None]
        J[:,:,1]=coreJ[:,:,0]*(inp[:,2]-inp[:,1])[:,None]
        if not self.bw:
            z=s['z']; fac=d['gain'] if self.config.get('tail_order')!='pre' else np.ones(len(y))
            dc=d['cs'][:,None]*d['G']*(self.c.E.ctx.S_eff*z)[None,:]*fac[:,None]
            J[:,:,2:26]=rgbj(dc)
            J[:,:,26:50]=rgbj(1j*self.c.E.table.k*dc)
        dpre=np.einsum('nrc,cd->nrd',coreJ,s['C']/1024)
        if 'rlut' in self.blocks and self.config.get('rlut_order')=='after':
            qgrad=dpre*rslope[:,None,:]
        else: qgrad=dpre
        for ch in range(3):
            start=self.qstart+(ch*33 if self.nc==3 else 0)
            J[:,:,start:start+33]+=qgrad[:,:,ch,None]*HQ[:,ch,None,:]
        if 'rlut' in self.blocks:
            sl=self.blocks['rlut']
            factor=rslope*4095/255 if self.config.get('rlut_order')=='before' else np.ones_like(pre)
            for ch in range(3):
                J[:,:,sl.start+ch*33:sl.start+(ch+1)*33]=dpre[:,:,ch,None]*factor[:,None,ch,None]*HR[:,ch,None,:]
        if 'matrix' in self.blocks:
            sl=self.blocks['matrix']
            J[:,:,sl.start]=coreJ[:,:,0]*inp[:,1,None]
            if not self.bw:
                for row in range(2):
                    for ch in range(3): J[:,:,sl.start+1+row*3+ch]=coreJ[:,:,row+1]*inp[:,ch,None]
        if 'offsets' in self.blocks:
            sl=self.blocks['offsets']
            if self.bw: J[:,:,sl.start]=coreJ[:,:,0]
            else:
                J[:,:,sl.start:sl.start+3]=coreJ
                J[:,:,sl.start+3:sl.stop]=np.einsum('nrc,cd->nrd',dpre,INPUT_INV)
        if 'tint' in self.blocks:
            sl=self.blocks['tint']
            for j in range(2):
                sp={**s,'tint':s['tint'].copy()};sm={**s,'tint':s['tint'].copy()}
                sp['tint'][j]+=eps;sm['tint'][j]-=eps
                J[:,:,sl.start+j]=(self.core(sp,y,ci)-self.core(sm,y,ci))/(2*eps)
        if 'gains' in self.blocks:
            sl=self.blocks['gains']
            if self.config.get('tail_order')=='pre':
                cs=d['cs']; ed=eps
                sx=(self.sector(s,cs+ed)[0]-self.sector(s,cs-ed)[0])/(2*ed)
                sy=(self.sector(s,cs+1j*ed)[0]-self.sector(s,cs-1j*ed)[0])/(2*ed)
                direction=sx*d['c0'].real+sy*d['c0'].imag
            else: direction=d['sec']
            J[:,:,sl]=rgbj(direction[:,None]*d['TH']/64)
        if 'asym' in self.blocks:
            sl=self.blocks['asym']
            fac=d['gain'] if self.config.get('tail_order')!='pre' else np.ones(len(y))
            extra=physical_weights(mm.hue_deg(d['cs']),self.c.E.table.nodes) if self.config.get('asym_kernel')=='physical_linear_H1' else d['G']
            k=extra*fac[:,None]/32
            J[:,:,sl.start:sl.start+24]=rgbj(1j*d['cs'].real[:,None]*k)
            J[:,:,sl.start+24:sl.stop]=rgbj(1j*d['cs'].imag[:,None]*k)
        jd=np.einsum('nrc,ncp->nrp',L,J).reshape(-1,self.np)
        con=self.constraints(p)
        jc=np.empty((len(con),self.np));ec=1e-5
        for j in range(self.np):
            v=np.zeros(self.np);v[j]=ec
            jc[:,j]=(self.constraints(p+v)-self.constraints(p-v))/(2*ec)
        out=np.r_[residual.ravel(),self.R@(p-self.theta0),con]
        jac=np.vstack([jd,self.R,jc])
        self.raw_state=(p.copy(),raw.copy(),J.copy())
        self.cache=(p.copy(),out,jac)
        return out,jac

    def solve(self,start=None,nfev=100):
        t=time.monotonic()
        start=self.theta0 if start is None else start
        p=np.clip(start,np.array(self.lower)+1e-9,np.array(self.upper)-1e-9)
        opt=least_squares(lambda a:self.evaluate(a)[0],p,jac=lambda a:self.evaluate(a)[1],
            bounds=(self.lower,self.upper),max_nfev=nfev,x_scale='jac',ftol=2e-6,xtol=2e-6,gtol=2e-5)
        return opt.x,dict(success=bool(opt.success),status=int(opt.status),nfev=int(opt.nfev),njev=int(opt.njev),
            cost=float(opt.cost),optimality=float(opt.optimality),seconds=time.monotonic()-t,message=opt.message)

    def packed(self,p):
        s=self.state(p,True)
        return dict(config=self.config,bw=self.bw,curve_x_u12=self.c.curve.xs.astype(int),
            curve_y_u8=s['q'],matrix_q10=s['C'],matrix_offset_integer_hypothesis=s['offsets'],
            sector_a=s['A'],sector_b=s['B'],sector_cd=np.vstack([-s['B'],s['A']])+s['asym'],
            c120_nodes_u14=INTERNAL.astype(int),c120_gains_u8=s['gains'],c004_signed_integer=s['tint'],
            rlut_input_u12=RLUT_X.astype(int),rlut_output_u12=s['rlut'],
            hardware_bit_exact=False,deployable=False)

    def unpack(self,doc):
        A,B=np.asarray(doc['sector_a']),np.asarray(doc['sector_b'])
        z=None
        if not self.bw:
            ordinary=self.c.fs.Z_of_words(A,B,self.c.E.ctx)
            z=abs(ordinary)*np.exp(1j*self.c.E.table.k*np.angle(ordinary))
        return dict(C=np.asarray(doc['matrix_q10']),q=np.asarray(doc['curve_y_u8']),
            offsets=np.asarray(doc['matrix_offset_integer_hypothesis']),tint=np.asarray(doc['c004_signed_integer']),
            gains=np.asarray(doc['c120_gains_u8']),rlut=np.asarray(doc['rlut_output_u12']),
            asym=np.asarray(doc['sector_cd'])-np.vstack([-B,A]),A=A,B=B,z=z,quantized=True)
