"""Bounded signed-node refinement and full-start exact confirmation for MOUNT."""
import argparse
import hashlib
from pathlib import Path
import signal
import struct
import sys
import time
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from scipy.optimize import least_squares
from entry_codec import predict as original_predict,record_checks,CRC_FIELDS,OFFSETS,ROW_BYTES
from report import select
from g155c_baseline import records
import fit_one as fit
import full_confirm_support as fc
from probe2_response import OUT,LocalResponse,curves,YCC,RGB,NODES


def prepare():
    root=OUT/'anchors';root.mkdir(exist_ok=False)
    profiles=[]
    for index in range(35):
        path,doc=select((rt.LOCAL/'fits/mount-a12'/f'{index:02d}').glob('L1_*.json'))
        anchor=path.with_suffix('.record552').read_bytes()
        assert hashlib.sha256(anchor).hexdigest()==doc['record']['sha256']
        (root/f'{index:02d}.record552').write_bytes(anchor)
        target=rt.LOCAL/'targets/mount-a12'/f'{index:02d}.json';meta=rt.read(target)
        profile=dict(index=index,name=doc['name'],source_fit=str(path.relative_to(rt.HERE)),source_fit_sha256=rt.sha(path),
            anchor_file=str((root/f'{index:02d}.record552').relative_to(rt.HERE)),anchor_sha256=doc['record']['sha256'],
            target_file=str(target.relative_to(rt.HERE)),target_sha256=rt.sha(target),gray=doc.get('gray',False),
            skipped_shared_or_native=not bool(anchor[1]&4),flags=anchor[1],
            model_scope='Signed local derivative transfer to a frozen non-Standard recipe is model extrapolation')
        groups={group:str((target.parent/f'{index:02d}_{group}.npz').relative_to(rt.HERE)) for group in meta['input_file_sha256']
            if (target.parent/f'{index:02d}_{group}.npz').exists()}
        bank=rt.read(rt.HERE/'new7_raw_holdout_summary_L1.json')['artifact_root']
        groups['photo_new7_RAW_diagnostic']=str((rt.HERE/bank/f'{index:02d}.npz').relative_to(rt.HERE))
        profile['groups']=groups;profile['input_sha256']={g:rt.sha(rt.HERE/p) for g,p in groups.items()}
        source_template=next((r for r in records()['mount-a12'] if r['name']==doc['name']),None)
        if source_template is None:source_template=next(r for r in records()['mount-a12'] if r['kind']=='builtin' and r['slot']==5)
        profile['g155c_reference']=source_template
        rt.dump(root/f'{index:02d}.json',profile);profiles.append(profile)
    rt.dump(OUT/'plan.json',dict(profiles=profiles,expected_profiles=35,
        calibration_sha256=rt.sha(OUT/'calibration.json'),policy_sha256=rt.sha(OUT/'policy.json')))
    print('PROBE2 PREPARED35',sum(not p['skipped_shared_or_native'] for p in profiles),'independent-curve refinements',flush=True)


class Flow:
    def __init__(self,index):
        self.index=index;self.meta=rt.read(OUT/'anchors'/f'{index:02d}.json')
        self.anchor=(rt.HERE/self.meta['anchor_file']).read_bytes()
        self.model=LocalResponse(self.anchor,self.meta['gray'])
        self.groups={g:rt.arrays(rt.HERE/p) for g,p in self.meta['groups'].items()}
        assert all(rt.sha(rt.HERE/self.meta['groups'][g])==v for g,v in self.meta['input_sha256'].items())
        self.train=self.groups['train'];self.P=self.model.problem(self.train['x'],self.train['want'],self.train['sw'])
        self.p0=fit.seed(self.P,self.anchor)
        self.columns=np.array([self.P.qstart+ch*33+node for ch,node in self.model.columns])
        self.low=[];self.high=[]
        for ch,node in self.model.columns:
            q=self.model.q[ch];lo,hi=((0.,2.) if node in (8,19) else (-2.,0.))
            self.low.append(max(lo,q[node-1]-q[node],-q[node]))
            self.high.append(min(hi,q[node+1]-q[node],255-q[node]))
        self.low,self.high=np.array(self.low),np.array(self.high)
        self.active=np.flatnonzero(self.high-self.low>1e-8)
        self.correction=self.model.correction_jac(self.train['x'])
        self.tlab=rt.lab_from_codes(self.train['want']);self.sqrtw=np.sqrt(self.train['sw'])[:,None]
        self.current=(rt.HERE/self.meta['g155c_reference']['record_file']).read_bytes()
        self.camera=rt.Camera(2);self.gradients,self.rings=fit.quality.fixtures(self.camera)
        self.before_masks=fit.ring_masks(self.camera,lambda x,r:original_predict(self.current,x,2,round_output=r),self.rings)
        self.last=None

    def project(self,vector):return np.clip(np.asarray(vector),self.low,self.high)

    def encode(self,vector):
        vector=np.rint(self.project(vector)).astype(int);out=bytearray(self.anchor)
        for j,(ch,node) in enumerate(self.model.columns):
            offset=(379,82,412)[ch]+node;out[offset]=int(self.model.q[ch,node])+int(vector[j])
            if ch==1:out[518+node]=out[offset]
        if self.index<27:
            content=bytes(out[:2])+bytes(out[445:447])+b'\x04'
            content+=b''.join(out[o:o+n] for o,n in zip(OFFSETS,ROW_BYTES))
            struct.pack_into('>I',out,4,zlib.crc32(content)&0xffffffff)
        for offset,size,crc in CRC_FIELDS:struct.pack_into('>I',out,crc,zlib.crc32(out[offset:offset+size])&0xffffffff)
        result=bytes(out);check=record_checks(result)
        assert check['row_crcs_valid'] and check['existing_row_domain_checks_pass'] and result[1]==self.anchor[1]
        return result

    def forward(self,vector):
        theta=self.p0.copy();theta[self.columns]+=vector
        self.P.evaluate(theta);raw,jac=self.P.raw_state[1:]
        clipped=np.clip(raw,0,255);jac=jac[:,:,self.columns]*((raw>0)&(raw<255))[:,:,None]
        value=clipped+np.einsum('ncp,p->nc',self.correction,vector)
        return value,jac+self.correction

    def loss(self,rgb):
        lab=rt.lab_from_codes(np.clip(rgb,0,255))
        return rt.de00_components(self.tlab,lab)*self.sqrtw

    def evaluate(self,active):
        vector=np.zeros(9);vector[self.active]=active
        if self.last is not None and np.array_equal(vector,self.last[0]):return self.last[1:]
        rgb,jac=self.forward(vector);residual=self.loss(rgb)
        gradient=np.empty((len(rgb),3,3));epsilon=1e-3
        for ch in range(3):
            step=np.zeros_like(rgb);step[:,ch]=epsilon
            gradient[:,:,ch]=(self.loss(rgb+step)-self.loss(rgb-step))/(2*epsilon)
        J=np.einsum('nrc,ncp->nrp',gradient,jac)[:,:,self.active].reshape(-1,len(self.active))
        result=np.r_[residual.ravel(),.002*active]
        J=np.vstack((J,.002*np.eye(len(self.active))))
        self.last=(vector.copy(),result,J)
        return result,J

    def guard(self,entry,branch='0.5'):
        fn=lambda x,r:self.model.predict(entry,x,branch,round_output=r)
        value=fit.quality.diagnostics(self.camera,fn,self.gradients,self.rings)
        masks=fit.ring_masks(self.camera,fn,self.rings)
        new=[int((a&~b).sum()) for a,b in zip(masks,self.before_masks)]
        value.update(new_reverse_intervals_by_ring=new,new_reverse_hue_intervals=sum(new),
            no_new_hue_reversals=sum(new)==0,gray_output_intent=self.meta['gray'],
            passes=sum(new)==0 and value['max_integer_gradient_step_de00']<=2)
        return value

    def objective(self,entry):return fit.objective(self.model.predict(entry,self.train['x']),self.train['want'],self.train['sw'])

    def starts(self):
        declarations=[('selected_L1_anchor',np.zeros(9))]
        target=rt.read(rt.HERE/self.meta['target_file'])
        parents=[('declared_current',bytes.fromhex(target['template_hex']))]
        for path in sorted((rt.LOCAL/'fits/mount-a12'/f'{self.index:02d}').glob('L[01]_*.json')):
            doc=rt.read(path)
            if doc['quality']['passes'] and doc.get('parameters'):
                parents.append((str(path.relative_to(rt.HERE)),path.with_suffix('.record552').read_bytes()))
        for name,entry in parents:
            xs=np.array([0,*struct.unpack_from('>31H',entry,20),4095]);q=curves(entry)
            vector=np.array([np.interp(self.model.xs[node],xs,q[ch])-self.model.q[ch,node] for ch,node in self.model.columns])
            declarations.append((name,self.project(vector)))
        neutral=np.ptp(self.train['x'],axis=1)<1e-8
        if neutral.any():
            wanted=self.train['want'][neutral]
            vector=np.array([np.interp(self.model.xs[node],self.train['x'][neutral,0],wanted[:,ch])-self.model.q[ch,node]
                for ch,node in self.model.columns])
            declarations.append(('declared_target_gray_axis',self.project(vector)))
        return declarations

    def scores(self,entry,branch='0.5'):
        out={};scenes={};info=rt.read(rt.LOCAL/'inputs/mount-a12/photos.json')
        for group,data in self.groups.items():
            if not len(data['x']):out[group]=None;continue
            prediction=self.model.predict(entry,data['x'],branch)
            before=original_predict(self.current,data['x'],2)
            out[group]=dict(candidate=rt.score(data['base'],prediction,data['want']),
                current=rt.score(data['base'],before,data['want']),
                anchor=rt.score(data['base'],original_predict(self.anchor,data['x'],2),data['want']))
            if group=='photo_iso200':
                names=np.array([info[int(k)]['scene_group'] for k in data['photo_id']]);scenes[group]={}
                for name in sorted(set(names)):
                    use=names==name;scenes[group][name]=dict(
                        candidate=rt.score(data['base'][use],prediction[use],data['want'][use]),
                        current=rt.score(data['base'][use],before[use],data['want'][use]))
            elif group=='photo_new7_RAW_diagnostic':scenes[group]={'whole_collection':out[group]}
        return out,scenes


def run(index,phase,nfev):
    meta=rt.read(OUT/'anchors'/f'{index:02d}.json');root=OUT/'fits'/f'{index:02d}';root.mkdir(parents=True,exist_ok=True)
    destination=root/phase;assert not destination.with_suffix('.json').exists()
    if meta['skipped_shared_or_native']:
        destination.with_suffix('.record552').write_bytes((rt.HERE/meta['anchor_file']).read_bytes())
        rt.dump(destination.with_suffix('.json'),dict(**meta,phase=phase,status='retained_shared_or_native',
            full_start_confirmation=phase=='exact',no_independent_curve_increment=True,
            record_sha256=meta['anchor_sha256'],record_file=str(destination.with_suffix('.record552').relative_to(rt.HERE))))
        return
    snapshot=rt.freeze_task_code();flow=Flow(index)
    assert flow.encode(np.zeros(9))==flow.anchor,'Zero increment changed the anchor bytes'
    declarations=flow.starts();kept=[np.zeros(9)]
    if phase=='exact':
        iteration=rt.read(root/'iterate.json');record=(root/'iterate.record552').read_bytes()
        declarations.append(('iteration_extra_integer',flow.model.delta(record)));kept.append(flow.model.delta(record))
    distinct={}
    for name,vector in declarations:
        vector=flow.project(vector);identity=hashlib.sha256(np.asarray(vector,dtype='<f8').tobytes()).hexdigest()
        distinct.setdefault(identity,dict(vector=vector,names=[]))['names'].append(name)
    manifest=dict(starts=list(distinct.values()),low=flow.low,high=flow.high,active=flow.active,
        nfev=nfev,all_original_declared_and_parent_starts_projected_into_signed_local_domain=True,
        all_existing_feasible_integer_candidates_kept=True,anchor_sha256=meta['anchor_sha256'],
        policy_sha256=rt.sha(OUT/'policy.json'),calibration_sha256=rt.sha(OUT/'calibration.json'))
    rt.dump(root/(phase+'_starts.json'),manifest)
    selected=flow.anchor;best=flow.objective(selected);attempts=[];rejections=0;started=time.monotonic()
    def consider(vector):
        nonlocal selected,best,rejections
        entry=flow.encode(vector);value=flow.objective(entry)
        if value>=best-1e-10:return
        quality=flow.guard(entry)
        if not quality['passes']:rejections+=1;return
        selected,best=entry,value
    for vector in kept:consider(vector)
    for identity,start in distinct.items():
        vector=start['vector'];consider(vector)
        if len(flow.active):
            first=np.clip(vector[flow.active],flow.low[flow.active]+1e-9,flow.high[flow.active]-1e-9)
            result=least_squares(lambda v:flow.evaluate(v)[0],first,jac=lambda v:flow.evaluate(v)[1],
                bounds=(flow.low[flow.active],flow.high[flow.active]),max_nfev=nfev,
                x_scale='jac',ftol=2e-6,xtol=2e-6,gtol=2e-5)
            final=np.zeros(9);final[flow.active]=result.x
            attempts.append(dict(start_sha256=identity,names=start['names'],nfev=int(result.nfev),
                status=int(result.status),success=bool(result.success),cost=float(result.cost),
                actual_solver='scipy TRF/SVD on the declared signed local coordinates'))
            for ratio in np.linspace(1,0,17):consider(ratio*final)
    record_path=destination.with_suffix('.record552');record_path.write_bytes(selected);selected=record_path.read_bytes()
    assert flow.objective(selected)==best
    scores,scenes=flow.scores(selected)
    predicted=flow.model.predict(selected,flow.train['x'],round_output=False)
    continuous,_=flow.forward(flow.model.delta(selected))
    assert np.max(abs(predicted-np.clip(continuous,0,255)))<1e-7
    gates={}
    original_fc=fc.predict
    fc.predict=lambda entry,x,ui:flow.model.predict(entry,x)
    try:
        gates['selected_L1_anchor']=fc.gate(dict(record_path=meta['anchor_file']),selected,flow.groups,2)
        if phase=='exact':gates['iteration']=fc.gate(dict(record_path=str((root/'iterate.record552').relative_to(rt.HERE))),selected,flow.groups,2)
    finally:fc.predict=original_fc
    uncertainty={}
    for branch in ('0.35','0.65','nearest_A'):
        values,groups=flow.scores(selected,branch)
        uncertainty[branch]=dict(scores=values,quality=flow.guard(selected,branch),
            original_counterexamples_preserved=True)
    quality=flow.guard(selected)
    regressed=[group+'/'+name for group,items in scenes.items() for name,value in items.items()
        if any(value['candidate']['de00'][k]>value['current']['de00'][k]+1e-10 for k in ('median','p95'))]
    doc=dict(**meta,phase=phase,status='refitted_local' if selected!=flow.anchor else 'retained_anchor',
        record_file=str(record_path.relative_to(rt.HERE)),record_sha256=rt.sha(record_path),record_checks=record_checks(selected),
        objective=best,anchor_objective=flow.objective(flow.anchor),increment=flow.model.delta(selected),
        quality=quality,scores=scores,per_scene=scenes,scene_regression_review=regressed,
        exact_gates=gates,exact_gate_status='PASS' if all(g['status']=='PASS' for g in gates.values()) else 'REVIEW',
        full_start_confirmation=phase=='exact',start_manifest=str((root/(phase+'_starts.json')).relative_to(rt.HERE)),
        start_manifest_sha256=rt.sha(root/(phase+'_starts.json')),solver_attempts=attempts,
        integer_selection_after_save_and_decode=True,record_model_max_difference=float(np.max(abs(predicted-np.clip(continuous,0,255)))),
        uncertainty=uncertainty,guard_rejections=rejections,elapsed_seconds=time.monotonic()-started,
        model_error_not_removed=True,full_colour_quantitative_acceptance=False,
        all_unmodified_nodes_and_matrices_and_sectors_frozen=True,
        scores_label='电脑预测，条件局部导数模型；非Standard基底转移、未采色相、量化相位仍有模型误差',
        code_snapshot=snapshot,no_DAT_built=True)
    rt.dump(destination.with_suffix('.json'),doc);rt.assert_task_code(snapshot)
    print('PROBE2 REFIT',index,phase,doc['status'],doc['exact_gate_status'],best,flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=('prepare','iterate','exact'))
    ap.add_argument('--index',type=int);ap.add_argument('--nfev',type=int,default=100);args=ap.parse_args()
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Probe2 fit exceeded25 minutes')))
    signal.alarm(1500)
    prepare() if args.stage=='prepare' else run(args.index,args.stage,args.nfev)
