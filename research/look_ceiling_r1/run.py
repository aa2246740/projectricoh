"""Refit every target without looking at held-out data when selecting parameters."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import time
import runtime as rt
from runtime import np,LOCAL
from ceiling_model import Problem,variants
from quality import fixtures,diagnostics

def load_arrays(path):
    with np.load(path,allow_pickle=False) as z:return dict(z)

def training_objective(base,pred,want,sw):
    e=rt.delta_e00(rt.lab_from_codes(pred),rt.lab_from_codes(want))
    return float(np.mean(sw*e*e)/np.mean(sw))

def seed_from_entry(P,entry):
    p=P.theta0.copy()
    row=P.c.mm.MatrixRow.from_bytes(entry[216:244])
    p[:2]=(row.coef[0,[0,2]]-P.c.row.coef[0,[0,2]])/1024
    curves=np.array([list(entry[379:412]),list(entry[82:115]),list(entry[412:445])])
    if not entry[1]&4:curves[:]=list(entry[82:115])
    if P.nc==1:curves=curves[1:2]
    p[P.qstart:P.qend]=(curves-P.c.curve.ys).ravel()
    if not P.bw:
        from gxr_studio.engine.knobs import dec
        coeff=np.array([[dec(z,128) for z in entry[i:i+4]] for i in range(115,211,4)])
        z=P.c.fs.Z_of_words(coeff[:,0],coeff[:,1],P.c.E.ctx)
        p[2:26]=np.log(np.maximum(abs(z),1e-6));p[26:50]=np.angle(z)
    return p

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--indices',default='0:27')
    parser.add_argument('--nfev',type=int,default=100)
    parser.add_argument('--keys',default='')
    parser.add_argument('--physical-asym',action='store_true',help='Add the H1 physical c/d node-response branch')
    parser.add_argument('--full-fields',action='store_true',help='Cover full integer field ranges from L2 onward')
    args=parser.parse_args()
    if ':' in args.indices:
        a,b=map(int,args.indices.split(':'));indices=range(a,b)
    else:indices=[int(x) for x in args.indices.split(',')]
    selected=set(args.keys.split(',')) if args.keys else None
    for index in indices:
        meta=rt.read(LOCAL/f'target_{index:02d}.json')
        c=rt.camera_for_unit(meta.get('camera_ui',0))
        groups={key:load_arrays(LOCAL/meta.get('group_files',{}).get(key,'samples_'+key+'.npz'))
                for key in ('train','synthetic','a12-50','a12-28','mount-a12')}
        x,sw=groups['train']['x'],groups['train']['sw']
        gradients,rings=fixtures(c)
        arrays=load_arrays(LOCAL/f'target_{index:02d}.npz')
        desired=arrays['train_target']
        solutions={}
        for config in variants():
            if args.full_fields and config['level']>=2:
                config={**config,'key':config['key']+'_fullfields','full_fields':True}
                if config['level']>=3:config['parent']=config['parent']+'_fullfields'
                if config['level']==4:config['asym_kernel']='physical_linear_H1'
            elif args.physical_asym and config['level']==4:
                config={**config,'key':config['key']+'_physical','asym_kernel':'physical_linear_H1'}
            key=config['key']
            path=LOCAL/'fits'/f'{index:02d}'/(key+'.json')
            P=Problem(c,x,desired,sw,config)
            if path.exists():
                doc=rt.read(path)
                solutions[key]=(P,np.asarray(doc['theta']))
                continue
            if (args.physical_asym and config['level']<4) or (args.full_fields and config['level']<2):
                raise FileNotFoundError('Complete original parent fits first: '+str(path))
            if selected and key not in selected:continue
            starts=[]
            if config['level']==0:
                starts.append(seed_from_entry(P,bytes.fromhex(meta['entry_hex'])))
                gray=np.ptp(x,axis=1)<1e-8
                xp=x[gray,0];yp=desired[gray]@np.array([.299,.587,.114])
                seed=P.theta0.copy()
                seed[P.qstart:P.qend]=np.maximum.accumulate(np.interp(c.curve.xs,xp,yp))-c.curve.ys
                starts.append(seed)
            else:
                parent=config.get('parent','L0')
                previous,theta=solutions[parent]
                starts.append(P.promote_integer(previous,theta) if args.full_fields else P.promote(previous,theta))
                if args.full_fields:
                    original=LOCAL/'fits'/f'{index:02d}'/(key.removesuffix('_fullfields')+'.json')
                    if original.exists():starts.append(np.asarray(rt.read(original)['theta']))
                if args.physical_asym:
                    original=LOCAL/'fits'/f'{index:02d}'/(key.removesuffix('_physical')+'.json')
                    if original.exists():starts.append(np.asarray(rt.read(original)['theta']))
                if config['level']==1:
                    if meta.get('builtin_slot'):
                        starts.append(seed_from_entry(P,bytes.fromhex(meta['entry_hex'])))
                    gray=np.ptp(x,axis=1)<1e-8
                    seed=starts[0].copy()
                    q=np.array([np.maximum.accumulate(np.interp(c.curve.xs,x[gray,0],desired[gray,ch])) for ch in range(3)])
                    seed[P.qstart:P.qend]=(q-c.curve.ys).ravel()
                    starts.append(seed)
            candidates=[];attempts=[]
            fallback=[]
            if (args.physical_asym or args.full_fields) and len(starts)>1:
                fallback=[starts[0]]
                starts=starts[1:]
            for seed in starts:
                theta,status=P.solve(seed,args.nfev)
                attempts.append(status)
                state=P.state(theta,True)
                pred=P.predict_state(state,x)
                obj=training_objective(arrays['train_base'],pred,desired,sw)
                candidates.append((obj,theta,status,'refit'))
                initial_state=P.state(seed,True)
                initial_pred=P.predict_state(initial_state,x)
                initial_obj=training_objective(arrays['train_base'],initial_pred,desired,sw)
                candidates.append((initial_obj,seed,None,'initial_integer'))
            for seed in fallback:
                pred=P.predict_state(P.state(seed,True),x)
                candidates.append((training_objective(arrays['train_base'],pred,desired,sw),seed,None,'parent_integer'))
            _,theta,status,selection=min(candidates,key=lambda r:r[0])
            packed=P.packed(theta)
            state=P.unpack(rt.plain(packed))
            scores={};raw_predictions={}
            for group,values in groups.items():
                if not len(values['x']):scores[group]=None;continue
                pred=P.predict_state(state,values['x'])
                scores[group]=rt.score(arrays[group+'_base'],pred,arrays[group+'_target'])
                raw_predictions[group]=pred.astype(np.uint8)
                if 'photo_id' in values:
                    scores[group]['per_photo']={str(i):rt.score(arrays[group+'_base'][values['photo_id']==i],
                        pred[values['photo_id']==i],arrays[group+'_target'][values['photo_id']==i])
                        for i in np.unique(values['photo_id'])}
            quality=diagnostics(c,lambda xx,round_output:P.predict_state(state,xx,round_output),gradients,rings)
            before=P.predict_state(P.state(theta,False),x)
            quantization=rt.stats(rt.delta_e00(rt.lab_from_codes(before),rt.lab_from_codes(raw_predictions['train'])))
            parent=config.get('parent','L0' if config['level'] else None)
            gains={};overfit={}
            if parent:
                parent_doc=rt.read(LOCAL/'fits'/f'{index:02d}'/(parent+'.json'))
                for group in groups:
                    if scores[group] and parent_doc['scores'][group]:
                        aa=scores[group]['similarity_percent'];bb=parent_doc['scores'][group]['similarity_percent']
                        gains[group]=None if aa is None or bb is None else aa-bb
                improved=scores['train']['de00']['mean']<parent_doc['scores']['train']['de00']['mean']-1e-9
                overfit={group:bool(improved and scores[group]['de00']['median']>=parent_doc['scores'][group]['de00']['median'])
                    for group in ('synthetic','a12-50','mount-a12') if scores[group] is not None}
            doc=dict(label='电脑预测',index=index,name=meta['name'],config=config,
                theta=theta,parameters=packed,solver_selected=status,solver_attempts=attempts,
                selection=selection,training_only_selection=True,train_objective=min(candidates,key=lambda r:r[0])[0],
                scores=scores,quality=quality,parameter_quantization_de00=quantization,
                parent=parent,gain_over_parent_pp=gains,overfit_flags=overfit,
                photo_synthetic_gap_pp={unit:None if scores[unit] is None or scores[unit]['similarity_percent'] is None
                    or scores['synthetic']['similarity_percent'] is None else
                    scores[unit]['similarity_percent']-scores['synthetic']['similarity_percent'] for unit in ('a12-50','mount-a12')},
                holdout_used_for_fit=False,hardware_acceptance=False,
                source_sha256=meta['source_sha256'])
            rt.dump(path,doc)
            np.savez_compressed(path.with_suffix('.npz'),**raw_predictions)
            solutions[key]=(P,theta)
            print(index,meta['name'],key,'MOUNT',None if scores['mount-a12'] is None or scores['mount-a12']['similarity_percent'] is None else
                  round(scores['mount-a12']['similarity_percent'],3),'nfev',[a['nfev'] for a in attempts],
                  'seconds',round(sum(a['seconds'] for a in attempts),2),flush=True)
        rt.finish('fit_'+str(index))

if __name__=='__main__':main()
