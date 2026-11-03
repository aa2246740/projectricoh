"""Conditional end-to-end two-ISP factorization, never a proven main-JPEG route."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import copy
import time
from types import SimpleNamespace
import runtime as rt
from runtime import np,ROOT,LOCAL,mm
from ceiling_model import Problem
from run import load_arrays,seed_from_entry,training_objective
from quality import fixtures,diagnostics
from scipy.optimize import least_squares

CONFIG=dict(key='L4_Y_post_add_after_Rbefore',level=4,axis='Y',tail_order='post',
            tint='add_after',rlut_order='before')

def body_camera(full_fields=False):
    from gxr_studio.engine.pretable import PreTable
    camera=rt.Camera();camera.E=copy.copy(camera.E)
    A=np.full(24,32);B=np.zeros(24)
    camera.E.ctx=SimpleNamespace(stock=np.c_[A,B],d0=np.zeros(24),d1=np.zeros(24),S_eff=np.ones(24,complex))
    ring=copy.deepcopy(camera.E.table.model)
    ring['k_coupling']=1.
    ring['gain']=1.
    ring['gain_per_sector']=[1.]*24
    camera.E.table=PreTable(ring,np.ones(24,complex))
    camera.curve=mm.Curve(np.r_[np.arange(32)*128.,4095.],np.r_[np.arange(32)*8.,255.])
    if full_fields:camera.curve=mm.Curve(camera.curve.xs,camera.curve.xs*255/4095)
    camera.row=mm.MatrixRow(np.array([[306,601,117],[-173,-339,512],[512,-429,-83]]),(0,128,128,0,0))
    camera.A,camera.B=A,B
    camera.initial_z=np.ones(24,complex)
    return camera

class Joint:
    def __init__(self,camera,x,want,sw,body_level=4,full_fields=False,axis='Y'):
        first_target=want.copy()
        if np.max(np.ptp(first_target,axis=1))<.5:
            first_target[:,0]=np.clip(first_target[:,0]+1.,0,255)
        config={**CONFIG,'axis':axis,'key':CONFIG['key'].replace('L4_Y_','L4_'+axis+'_')}
        firstconfig={**config,'full_fields':True,'asym_kernel':'physical_linear_H1'} if full_fields else config
        self.first=Problem(camera,x,first_target,sw,firstconfig)
        bodyconfig=dict(firstconfig,key='BODY_L4') if body_level==4 else dict(key='BODY_L1',level=1)
        self.second=Problem(body_camera(full_fields),x*0,want,sw,bodyconfig)
        self.code_scale=4095/255 if full_fields else 16.
        self.x,self.want,self.sw=x,want,sw
        self.split=self.first.np
        self.np=self.first.np+self.second.np
        self.cache=None
        self.lower=np.r_[self.first.lower,self.second.lower]
        self.upper=np.r_[self.first.upper,self.second.upper]

    def evaluate(self,p):
        if self.cache is not None and np.array_equal(p,self.cache[0]):return self.cache[1:]
        a,b=p[:self.split],p[self.split:]
        r1,j1=self.first.evaluate(a)
        _,raw1,jraw1=self.first.raw_state
        x2=np.clip(raw1,0,255)*self.code_scale
        self.second.x=x2
        self.second.H=rt.weights(x2,self.second.c.curve.xs)
        self.second.cache=None
        r2,j2=self.second.evaluate(b)
        _,raw2,_=self.second.raw_state
        state2=self.second.state(b)
        inputJ=np.empty((len(x2),3,3));eps=1e-3
        for ch in range(3):
            d=np.zeros_like(x2);d[:,ch]=eps
            inputJ[:,:,ch]=(self.second.predict_state(state2,x2+d,False,True)-
                            self.second.predict_state(state2,x2-d,False,True))/(2*eps)*self.code_scale
        inputJ*=((raw1>0)&(raw1<255))[:,None,:]
        firstJ=np.einsum('nrc,ncp->nrp',inputJ,jraw1)
        def loss(rgb):
            lab=rt.lab_from_codes(np.clip(rgb,0,255))
            if self.second.bw:
                mean=(self.second.tlab[:,0]+lab[:,0])/2
                scale=1+.015*(mean-50)**2/np.sqrt(20+(mean-50)**2)
                v=np.zeros_like(lab);v[:,0]=(lab[:,0]-self.second.tlab[:,0])/scale
                return v*self.second.sqrtw
            return rt.de00_components(self.second.tlab,lab)*self.second.sqrtw
        L=np.empty((len(x2),3,3))
        for ch in range(3):
            d=np.zeros_like(raw2);d[:,ch]=eps
            L[:,:,ch]=(loss(raw2+d)-loss(raw2-d))/(2*eps)
        n=3*len(x2)
        jd1=np.einsum('nrc,ncp->nrp',L,firstJ).reshape(n,self.first.np)
        residual=np.r_[r2[:n],r1[n:],r2[n:]]
        jac=np.zeros((len(residual),self.np))
        jac[:n,:self.split]=jd1;jac[:n,self.split:]=j2[:n]
        jac[n:n+len(r1)-n,:self.split]=j1[n:]
        jac[len(r1):,self.split:]=j2[n:]
        self.cache=(p.copy(),residual,jac)
        return residual,jac

    def predict(self,p,x,rounded=True,yuv_round=False):
        first=self.first.state(p[:self.split],True)
        second=self.second.state(p[self.split:],True)
        mid=self.first.predict_state(first,x,True)
        if yuv_round:
            y,c=mm.ycbcr(mid)
            y=np.clip(np.rint(y),0,255)
            c=np.clip(np.rint(c.real+128),0,255)-128+1j*(np.clip(np.rint(c.imag+128),0,255)-128)
            mid=np.clip(mm.rgb_from_ycc(y,c),0,255)
        return self.second.predict_state(second,mid*self.code_scale,rounded)

    def solve(self,start,nfev):
        t=time.monotonic()
        start=np.clip(start,self.lower+1e-9,self.upper-1e-9)
        opt=least_squares(lambda p:self.evaluate(p)[0],start,jac=lambda p:self.evaluate(p)[1],
            bounds=(self.lower,self.upper),max_nfev=nfev,ftol=2e-6,xtol=2e-6,gtol=2e-5,x_scale='jac')
        return opt.x,dict(success=bool(opt.success),status=int(opt.status),message=opt.message,
            nfev=int(opt.nfev),njev=int(opt.njev),cost=float(opt.cost),seconds=time.monotonic()-t)

def check(full_fields=False,axis='Y'):
    x=load_arrays(LOCAL/'samples_train.npz')['x'][:64]
    want=load_arrays(LOCAL/'target_00.npz')['train_target'][:64]
    P=Joint(rt.Camera(),x,want,np.ones(len(x)),full_fields=full_fields,axis=axis)
    rng=np.random.default_rng(20261103)
    p=np.r_[P.first.theta0,P.second.theta0]
    for off,Q in ((0,P.first),(P.split,P.second)):
        p[off:off+2]+=[.013,-.006]
        p[off+2:off+50]+=.003*rng.normal(size=48)
        p[off+Q.qstart:off+Q.qend]+=.03*rng.normal(size=Q.qend-Q.qstart)
    r,J=P.evaluate(p);checks=[]
    for name,sl in (('first',slice(0,P.split)),('second',slice(P.split,P.np))):
        d=np.zeros(P.np);d[sl]=rng.normal(size=sl.stop-sl.start);d/=np.linalg.norm(d)
        eps=2e-5
        numeric=(P.evaluate(p+eps*d)[0]-P.evaluate(p-eps*d)[0])/(2*eps)
        rel=float(np.linalg.norm(numeric-J@d)/np.linalg.norm(numeric))
        checks.append(dict(block=name,relative_error=rel));assert rel<.01,checks
    name='two_pass_full_checks.json' if full_fields else 'two_pass_checks.json'
    if axis=='C':name=name.removesuffix('.json')+'_C.json'
    rt.dump(name,checks)
    print(checks,flush=True)
    rt.finish('two_pass_checks')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--indices',default='0:27');parser.add_argument('--nfev',type=int,default=80)
    parser.add_argument('--check',action='store_true');parser.add_argument('--full-fields',action='store_true')
    parser.add_argument('--axis',choices=('Y','C'),default='Y');args=parser.parse_args()
    if args.check:check(args.full_fields,args.axis);return
    if ':' in args.indices:
        aa,bb=map(int,args.indices.split(':'));indices=range(aa,bb)
    else:indices=[int(v) for v in args.indices.split(',')]
    _,dat,_=rt.upstream.camera_model()
    for index in indices:
        meta=rt.read(LOCAL/f'target_{index:02d}.json');data=load_arrays(LOCAL/f'target_{index:02d}.npz')
        groups={key:load_arrays(LOCAL/meta.get('group_files',{}).get(key,'samples_'+key+'.npz'))
            for key in ('train','synthetic','a12-50','a12-28','mount-a12')}
        c=rt.camera_for_unit(meta.get('camera_ui',0));x=groups['train']['x'];sw=groups['train']['sw']
        suffix='_fullfields' if args.full_fields else ''
        reference_key='L4_'+args.axis+'_post_add_after_Rbefore'
        reference=rt.read(LOCAL/'fits'/f'{index:02d}'/(reference_key+suffix+'.json'))
        for body_level in (1,4):
            dirname='two_pass_full' if args.full_fields else 'two_pass'
            if args.axis=='C':dirname+='_C'
            path=LOCAL/dirname/f'{index:02d}'/('body_L'+str(body_level)+'.json')
            if path.exists():continue
            P=Joint(c,x,data['train_target'],sw,body_level,args.full_fields,args.axis)
            first=np.asarray(reference['theta'])
            if len(first)!=P.first.np:
                first=P.first.theta0.copy()
                q=np.asarray(reference['parameters']['curve_y_u8'])
                first[P.first.qstart:P.first.qend]=(q-c.curve.ys).ravel()
                C=np.asarray(reference['parameters']['matrix_q10'])
                first[:2]=(C[0,[0,2]]-c.row.coef[0,[0,2]])/1024
            starts=[np.r_[first,P.second.theta0]]
            identity=seed_from_entry(P.first,dat.entry_of(meta.get('camera_ui',0),4))
            starts.append(np.r_[identity,P.second.theta0])
            attempts=[];candidates=[]
            for start in starts:
                theta,status=P.solve(start,args.nfev);attempts.append(status)
                for candidate,tag in ((theta,'joint_refit'),(start,'initial_integer')):
                    pred=P.predict(candidate,x)
                    obj=training_objective(data['train_base'],pred,data['train_target'],sw)
                    candidates.append((obj,candidate.copy(),tag))
            objective,p,tag=min(candidates,key=lambda row:row[0])
            scores={};yuv={};predictions={}
            for key,g in groups.items():
                if not len(g['x']):scores[key]=None;yuv[key]=None;continue
                pp=P.predict(p,g['x']);yy=P.predict(p,g['x'],yuv_round=True)
                predictions[key]=pp.astype(np.uint8)
                scores[key]=rt.score(data[key+'_base'],pp,data[key+'_target'])
                yuv[key]=rt.score(data[key+'_base'],yy,data[key+'_target'])
            gradients,rings=fixtures(c)
            quality=diagnostics(c,lambda xx,r:P.predict(p,xx,r),gradients,rings)
            rt.dump(path,dict(label='电脑预测，双ISP假设',index=index,name=meta['name'],body_level=body_level,
                theta=p,first_parameters=P.first.packed(p[:P.split]),second_parameters=P.second.packed(p[P.split:]),
                scores=scores,yuv444_rounding_sensitivity=yuv,quality=quality,solver_attempts=attempts,
                training_only_selection=True,selection=tag,training_objective=objective,
                full_fields=args.full_fields,body_input_scale=P.code_scale,
                first_reference=reference_key,axis_hypothesis=args.axis,hardware_main_JPEG_path_closed=False,
                body_pixel_equation_verified=False,body_sector_response='identity baseline, k=1, transferred kernel geometry',
                intermediate='u8 RGB; YUV444 precision perturbation separately; real YUV422 spatial loss unmodelled',
                mathematical_upper_bound=False))
            np.savez_compressed(path.with_suffix('.npz'),**predictions)
            print(index,meta['name'],'second L'+str(body_level),'MOUNT',None if scores['mount-a12'] is None else scores['mount-a12']['similarity_percent'],
                  'seconds',round(sum(r['seconds'] for r in attempts),1),flush=True)
        rt.finish('two_pass_'+str(index))

if __name__=='__main__':main()
