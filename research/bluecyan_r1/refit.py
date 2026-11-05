#!/usr/bin/env python3
"""Bounded corrected-model recipe fits using fit_fast and reference exact.

Uses frozen targets/current entries and either native C040 or a T-only model.
No live module, shared runtime, DAT writer, or experimental solver is imported.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import np,ROOT,LOCAL,read,dump,sha,stats,de
from correction import Correction
import experiments as ex
import ast
import types
import struct
import hashlib
import shutil
import argparse
import os
import time
import zlib


def backend(ref):
    rt=types.ModuleType('blue_refit_runtime');sys.modules[rt.__name__]=rt
    rt.np=np;rt.ROOT=ROOT;rt.LOCAL=LOCAL;rt.HERE=ROOT/'tools/fit_fast'
    rt.PRIVATE=LOCAL/'fit_fast';rt.SCRATCH=LOCAL/'tmp';rt.Path=Path
    rt.REFERENCE=ROOT/'tools/fit_fast/reference';rt.hashlib=hashlib
    rt.sha=sha;rt.stats=stats;rt.mm=ref.mm
    rt.lab_from_codes=ref.fs.lab_from_codes;rt.delta_e00=ref.fs.delta_e00;rt.de00_components=ref.fs.de00_components
    def output(p,value):
        p=Path(p);p=p if p.is_absolute() else LOCAL/p
        assert p.resolve().is_relative_to(LOCAL)
        dump(p.relative_to(LOCAL),value)
    rt.dump=output
    def local_read(p):
        p=Path(p)
        if p==LOCAL/'hardware_constants.json':p=ROOT/'research/look_ceiling_r1/local/hardware_constants.json'
        return read(p)
    rt.read=local_read;rt.PRIVATE.mkdir(exist_ok=True);rt.SCRATCH.mkdir(exist_ok=True)
    aliases={'runtime':rt.__name__,'native':'blue_refit_native','exact_table':'blue_refit_exact_table',
             'guard':'blue_refit_legacy_io','common':'blue_refit_common'}
    def relocated(name,path):
        tree=ast.parse(path.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):
                for item in n.names:
                    if item.name in aliases:
                        old=item.name;item.name=aliases[old];item.asname=item.asname or old
            if isinstance(n,ast.ImportFrom) and n.module in aliases:n.module=aliases[n.module]
        ast.fix_missing_locations(tree)
        m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m
        exec(compile(tree,str(path),'exec'),m.__dict__)
        return m
    io=types.ModuleType(aliases['guard']);io.LOCAL=LOCAL;io.output_path=lambda p:LOCAL/p;io.dump=output
    sys.modules[io.__name__]=io
    safety=a.module('blue_refit_safety',ROOT/'research/closed_loop/local/vendor/safety.py');safety.fs=ref.fs
    common=types.ModuleType(aliases['common']);common.helper=lambda name:safety if name=='safety' else None
    sys.modules[common.__name__]=common
    legacy=relocated('blue_refit_legacy',rt.REFERENCE/'research/film_look_routes/fit.py')
    rt.LegacyProblem=legacy.Problem;rt.weights=legacy.weights
    def to_words(Z,ctx):
        P=Z*ctx.S_eff*32
        aa=np.rint(P.real-ctx.d0);bb=np.rint(-P.imag-ctx.d1)
        return np.clip(aa,-127,127).astype(int),np.clip(bb,-127,127).astype(int),(abs(aa)>127)|(abs(bb)>127)
    ref.fs.to_words=to_words
    rt.ref_module=lambda name,filename:relocated('blue_ref_'+name,rt.REFERENCE/'research/look_ceiling_r1'/filename)
    # Reuse the already compiled, hash-verified C kernel in our own output tree.
    key=sha(rt.HERE/'kernels.c')[:20]
    filename='kernels-c-'+key+'.dylib'
    old=ROOT/'research/recipe_redo_r1/local/normal_fast_engine/build'/filename
    receipt=read(old.with_suffix('.json'))
    assert receipt['source_sha256']==sha(rt.HERE/'kernels.c') and receipt['library_sha256']==sha(old)
    dest=rt.PRIVATE/'build'/filename;dest.parent.mkdir(exist_ok=True)
    for src,dst in ((old,dest),(old.with_suffix('.json'),dest.with_suffix('.json'))):
        if not dst.exists():shutil.copyfile(src,dst)
        assert sha(src)==sha(dst)
    relocated(aliases['native'],rt.HERE/'native.py')
    relocated(aliases['exact_table'],rt.HERE/'exact_table.py')
    fast=relocated('blue_refit_engine',rt.HERE/'engine.py')
    guard=ex.load_solver()
    quality=rt.ref_module('quality','quality.py')
    return fast,fast.reference,guard,quality


def camera(ref,unit,entry,physical_model=False):
    # A separate owner chain per fitting process and per unit.
    import history
    hm=history.Models()
    raw13=read(LOCAL/'history/inventory.json')[0]['metadata']['color_raw13']
    model=hm.model(unit,200,raw13)
    if physical_model:
        import physical
        physical.update_model(model,unit)
    ui=('a12-50','a12-28','mount-a12').index(unit)
    fmt=a.module('blue_refit_dat',ROOT/'research/v39_g153/dat_format.py')
    data=(ROOT/'firmware/package_v310_g156_test/GXRCE.DAT').read_bytes()
    base=fmt.expand(data,ui,4)
    assert base[115:211]==bytes.fromhex(hm.official[('50mm','28mm','mount')[ui]]['rows']['colour1']['hex'])
    xs=np.r_[0,struct.unpack_from('>31H',entry,20),4095]
    A,B=np.array([model.fs.decode_word(base[o:o+4]) for o in range(115,211,4)]).T
    return types.SimpleNamespace(model=model,E=model.engine,mm=model.mm,fs=model.fs,
        row=model.mm.MatrixRow.from_bytes(entry[216:244]),curve=model.mm.Curve(xs,list(base[82:115])),
        A=A,B=B,initial_z=model.fs.Z_of_words(A,B,model.engine.ctx),entry=base,ui=ui)


def seed(P,b):
    p=P.theta0.copy();row=P.c.mm.MatrixRow.from_bytes(b[216:244])
    p[:2]=(row.coef[0,[0,2]]-P.c.row.coef[0,[0,2]])/1024
    q=np.array([list(b[379:412]),list(b[82:115]),list(b[412:445])])
    if not b[1]&4:q[:]=list(b[82:115])
    if P.nc==1:q=q[1:2]
    p[P.qstart:P.qend]=(q-P.c.curve.ys).ravel()
    ab=np.array([P.c.fs.decode_word(b[o:o+4]) for o in range(115,211,4)])
    z=P.c.fs.Z_of_words(ab[:,0],ab[:,1],P.c.E.ctx)
    p[2:26]=np.log(abs(z));p[26:50]=np.angle(z)
    return p


def encode(c,template,state):
    b=bytearray(template);q=state['q']
    if len(q)==1:q=np.repeat(q,3,axis=0)
    b[82:115]=bytes(q[1].tolist())
    if b[1]&4:
        b[379:412]=bytes(q[0].tolist());b[412:445]=bytes(q[2].tolist())
    b[216:244]=c.mm.MatrixRow(state['C'],c.row.tail).to_bytes()
    b[115:211]=b''.join(c.fs.encode_word(aa,bb) for aa,bb in zip(state['A'],state['B']))
    # Same existing record encoding policy as recipe_redo: mirror ISO100 rows.
    b[456:518]=b[20:82];b[518:551]=b[82:115]
    from gxr_studio.camdata.datcodec import CRC_FIELDS,OFFSETS,ROW_BYTES,_valid_look_row
    for off,n,crc in CRC_FIELDS:struct.pack_into('>I',b,crc,zlib.crc32(b[off:off+n])&0xffffffff)
    assert all(_valid_look_row(bytes(b[o:o+n]),j,b[1]) for j,(o,n) in enumerate(zip(OFFSETS,ROW_BYTES)))
    assert all(struct.unpack_from('>I',b,co)[0]==zlib.crc32(b[o:o+n])&0xffffffff for o,n,co in CRC_FIELDS)
    return bytes(b)


def groups(unit,index,physical_model=False):
    folder=ROOT/f'research/recipe_redo_r1/local/targets/{unit}'
    out={}
    for group in ('train','synthetic','photo_iso200','photo_other_iso'):
        source=folder/f'{index:02d}_{group}.npz'
        if unit=='a12-28' and not source.exists() and group.startswith('photo_'):continue
        with np.load(source,allow_pickle=False) as z:out[group]=dict(z)
    if unit=='mount-a12':
        with np.load(ROOT/f'research/recipe_redo_r1/local/new7/recipe_holdout_L1_lens_r5/{index:02d}.npz',allow_pickle=False) as z:
            out['new7_RAW_target']=dict(z)
    if physical_model:
        from physical_calibration import coefficients,apply
        C=coefficients(unit)
        for values in out.values():
            values['x_old']=values['x'].copy()
            values['x']=apply(values['raw_codes'],C) if C.ndim==2 and C.size else values['raw_codes'].copy()
    return out


def quality_check(c,q,corr,current,candidate):
    gradients,rings=q.fixtures(c)
    before=lambda x,rounding:corr.predict(c.model,current,x,round_output=rounding)
    after=lambda x,rounding:corr.predict(c.model,candidate,x,round_output=rounding)
    detail=q.diagnostics(c,after,gradients,rings)
    masks=[]
    for fn in (before,after):
        mm=[]
        for ring in rings:
            _,co=c.mm.ycbcr(fn(ring['x'],False));angle=np.unwrap(np.angle(co))*180/np.pi
            valid=ring['valid'][:-1]&ring['valid'][1:]&(abs(co[:-1])>=2)&(abs(co[1:])>=2)
            mm.append(valid&(np.diff(angle)/.5<-.001))
        masks.append(mm)
    detail['new_reverse_hue_intervals']=sum(int((y&~x).sum()) for x,y in zip(*masks))
    detail['nominal_old_publication_gate']=detail['new_reverse_hue_intervals']==0 and detail['max_integer_gradient_step_de00']<=2
    return detail


def run(unit,slot,phase,nfev,physical_model=False,hue_guard=False):
    _,ref,_=a.load();fast,reference,guard,quality=backend(ref)
    corr=None if physical_model else Correction()
    ui=('a12-50','a12-28','mount-a12').index(unit);index=slot+26
    fmt=a.module('blue_refit_record',ROOT/'research/v39_g153/dat_format.py')
    current=fmt.expand((ROOT/'firmware/package_v310_g156_test/GXRCE.DAT').read_bytes(),ui,slot)
    c=camera(ref,unit,current,physical_model);bank=groups(unit,index,physical_model);train=bank['train']
    if physical_model:
        class FullModel:
            def predict(self,model,entry,x,round_output=False):
                pred=model.predict(entry,x,quantize=False)
                return np.rint(pred) if round_output else pred
        corr=FullModel()
    def corrected_class(base):
        if physical_model:return base
        class Corrected(base):
            def sector(self,s,ci):return corr.sector(self.c.E.table,ci,s['z'])
        return Corrected
    model_source=LOCAL/f'physical/ring-{unit}-200.json' if physical_model else LOCAL/'model.json'
    level=int(bool(current[1]&4));config=dict(key=f'{unit}_{slot}_{phase}',level=level,
        correction_sha256=sha(model_source),frozen_C100_chroma=True)
    P=corrected_class(fast.Problem)(c,train['x'],train['want'],train['sw'],config)
    R=corrected_class(reference.Problem)(c,train['x'],train['want'],train['sw'],config)
    initial=seed(P,current)
    fitroot=LOCAL/'physical/guarded_fits' if hue_guard else LOCAL/'physical/fits' if physical_model else LOCAL/'fits'
    folder=fitroot/unit/f'{slot:02d}';folder.mkdir(parents=True,exist_ok=True)
    if phase=='exact':initial=np.array(read(folder/'iterate.json')['theta'])
    # Numerical equivalence includes corrected forward, residual and Jacobian.
    rf,jf=P.evaluate(initial);rr,jr=R.evaluate(initial)
    equivalence=dict(max_residual=float(np.max(abs(rf-rr))),max_jacobian=float(np.max(abs(jf-jr))))
    assert equivalence['max_residual']<1e-8 and equivalence['max_jacobian']<1e-5,equivalence
    predicted=P.predict_state(P.state(seed(P,current)),train['x'],round_output=False)
    encoded=corr.predict(c.model,current,train['x'])
    assert np.max(abs(predicted-encoded))<1e-7
    if hue_guard:
        source=ROOT/'research/recipe_redo_r1/guarded_problem.py'
        tree=ast.parse(source.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                for item in node.names:
                    if item.name=='runtime':item.name='blue_refit_runtime';item.asname='rt'
            if isinstance(node,ast.ImportFrom) and node.module=='runtime':node.module='blue_refit_runtime'
        ast.fix_missing_locations(tree);mod=types.ModuleType('blue_hue_guard');mod.__file__=str(source)
        exec(compile(tree,str(source),'exec'),mod.__dict__)
        _,rings=quality.fixtures(c)
        def wrap(primary):
            G=mod.GuardedProblem(primary,lambda x:corr.predict(c.model,current,x),c,rings)
            for key in ('np','lower','upper','want','c','config'):setattr(G,key,getattr(primary,key))
            G.x=primary.x;G.residual=lambda p:G.evaluate(p)[0]
            return G
        solver=wrap(P) if phase=='iterate' else wrap(R)
        if phase=='iterate':theta,receipt=guard.solve(solver,initial,nfev)
        else:theta,receipt=solver.solve(initial,nfev)
    elif phase=='iterate':theta,receipt=guard.solve(P,initial,nfev)
    else:theta,receipt=R.solve(initial,nfev)
    candidates=[('current',current,None)]
    if phase=='exact':candidates.append(('iterate',(folder/'iterate.record552').read_bytes(),initial))
    candidates.append((phase,encode(c,current,R.state(theta,True)),theta))
    integer_guard_search=[]
    if hue_guard:
        # This fixed quantized line search is selected only on training loss
        # and reachable hue/gradient checks. No photo holdout enters selection.
        origin_theta=seed(R,current)
        for alpha in np.linspace(0,1,17)[1:-1]:
            point=origin_theta+alpha*(theta-origin_theta)
            candidate=encode(c,current,R.state(point,True))
            candidates.append((f'alpha_{alpha:.4f}',candidate,point))
        safe=[]
        for origin,b,point in candidates:
            q=quality_check(c,quality,corr,current,b)
            integer_guard_search.append(dict(origin=origin,quality_pass=q['nominal_old_publication_gate'],
                new_reverse_hue_intervals=q['new_reverse_hue_intervals'],max_integer_step=q['max_integer_gradient_step_de00']))
            if q['nominal_old_publication_gate']:safe.append((origin,b,point))
        candidates=safe
        assert candidates
    def objective(b):
        pred=corr.predict(c.model,b,train['x'],round_output=True)
        err=c.fs.delta_e00(c.fs.lab_from_codes(pred),c.fs.lab_from_codes(train['want']))
        return float(np.average(err*err,weights=train['sw']))
    origin,entry,selected_theta=min(candidates,key=lambda item:objective(item[1]))
    if selected_theta is None:selected_theta=seed(R,current)
    (folder/(phase+'.record552')).write_bytes(entry)
    scores={};photo_scores=[]
    for group,v in bank.items():
        if not len(v['x']):continue
        before=corr.predict(c.model,current,v['x'],round_output=True)
        after=corr.predict(c.model,entry,v['x'],round_output=True)
        if physical_model:
            import history
            oldmodel=history.Models().model(unit,200,read(LOCAL/'history/inventory.json')[0]['metadata']['color_raw13'])
            baseline=oldmodel.predict(current,v['x_old'],quantize=True)
        else:baseline=c.model.predict(current,v['x'],quantize=True)
        e0=de(before,v['want']);e1=de(after,v['want']);eold=de(baseline,v['want'])
        scores[group]=dict(current_old_model=stats(eold),current_corrected_model=stats(e0),
            candidate_corrected_model=stats(e1),photos=len(set(v['photo_id'].tolist())),
            target='frozen intended style, not an observed new-camera JPEG')
        if 'photo_id' in v:
            for pid in sorted(set(v['photo_id'].tolist())):
                if pid<0:continue
                ix=v['photo_id']==pid
                photo_scores.append(dict(group=group,photo_id=int(pid),n=int(ix.sum()),
                    current=stats(e0[ix]),candidate=stats(e1[ix]),
                    median_regressed=bool(np.median(e1[ix])>np.median(e0[ix])+1e-10),
                    p95_regressed=bool(np.percentile(e1[ix],95)>np.percentile(e0[ix],95)+1e-10)))
    exact_rgb=corr.predict(c.model,entry,train['x'])
    state_rgb=R.predict_state(R.state(selected_theta,True),train['x'],round_output=False)
    replay=float(np.max(abs(exact_rgb-state_rgb)))
    assert replay<1e-7,replay
    q=quality_check(c,quality,corr,current,entry)
    doc=dict(unit=unit,slot=slot,phase=phase,origin=origin,theta=selected_theta,solver_receipt=receipt,
        backend='fit_fast guarded_normal' if phase=='iterate' else 'frozen reference exact SciPy SVD',
        model_sha256=sha(model_source),current_sha256=hashlib.sha256(current).hexdigest(),
        record_sha256=sha(folder/(phase+'.record552')),record_file=str((folder/(phase+'.record552')).relative_to(LOCAL)),
        payload_bytes_changed=sum(x!=y for x,y in zip(current,entry)),equivalence=equivalence,
        integer_record_reference_replay_max_rgb=replay,train_objective=objective(entry),
        original_train_objective=objective(current),scores=scores,photo_scores=photo_scores,quality=q,
        scope='computer prediction with a conditional MOUNT ISO200 model; no candidate exposure exists',
        runtime_nice=os.getpriority(os.PRIO_PROCESS,0),round3_experimental_solver_used=False)
    doc['hue_guard']=hue_guard;doc['integer_guard_search']=integer_guard_search
    doc['missing_photo_holdouts']=[g for g in ('photo_iso200','photo_other_iso') if g not in bank]
    if doc['missing_photo_holdouts']:
        doc['publication_eligible']=False
        doc['missing_holdout_reason']='No pre-existing paired photograph target files for this unit; not replaced by synthetic data'
    if physical_model:
        doc['physical_C040_model']=True
        doc['model_sha256']=sha(LOCAL/f'physical/ring-{unit}-200.json')
        doc['input_map_sha256']=sha(LOCAL/'physical/input-map-mount-a12.json') if unit=='mount-a12' else None
        doc['scope']='computer prediction using official per-unit C040 nodes; no candidate exposure exists'
    dump(folder.relative_to(LOCAL)/(phase+'.json'),doc)
    print(unit,slot,phase,'selected',origin,'objective',doc['original_train_objective'],'->',doc['train_objective'],flush=True)
    print('scores',[(k,round(v['current_corrected_model']['median'],3),round(v['candidate_corrected_model']['median'],3),round(v['current_corrected_model']['p95'],3),round(v['candidate_corrected_model']['p95'],3)) for k,v in scores.items()],flush=True)
    print('quality',q['new_reverse_hue_intervals'],q['max_integer_gradient_step_de00'],flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--unit',default='mount-a12',choices=('mount-a12','a12-50','a12-28'))
    ap.add_argument('--slot',type=int,required=True,choices=(5,6));ap.add_argument('--phase',choices=('iterate','exact'),required=True)
    ap.add_argument('--nfev',type=int,default=160)
    ap.add_argument('--physical',action='store_true')
    ap.add_argument('--hue-guard',action='store_true')
    args=ap.parse_args();run(args.unit,args.slot,args.phase,args.nfev,args.physical,args.hue_guard)
