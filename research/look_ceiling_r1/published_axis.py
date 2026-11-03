"""Known type26 input-node control, using each published row's original axis."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import struct
import runtime as rt
from runtime import np,LOCAL
from ceiling_model import Problem
from run import load_arrays,seed_from_entry,training_objective
from quality import fixtures,diagnostics

KEYS=('L1','L4_Y_post_add_after_Rbefore_fullfields')

def published_seed(P,entry):
    p=seed_from_entry(P,entry)
    row=rt.mm.MatrixRow.from_bytes(entry[216:244])
    if 'matrix' in P.blocks:
        C,_=P.legacy.parameters(p[:P.base_n])
        v=[(row.coef[0,1]-C[0,1])/1024]
        if not P.bw:v.extend(((row.coef[1:]-C[1:])/1024).ravel())
        p[P.blocks['matrix']]=v
        delta=row.offsets-P.c.row.offsets
        p[P.blocks['offsets']]=delta[:1] if P.bw else np.r_[delta,0,0]
    return p

def main():
    model,_,_=rt.upstream.camera_model()
    for i in range(51):
        meta=rt.read(LOCAL/f'target_{i:02d}.json');data=load_arrays(LOCAL/f'target_{i:02d}.npz')
        gg={k:load_arrays(LOCAL/meta.get('group_files',{}).get(k,'samples_'+k+'.npz'))
            for k in ('train','synthetic','a12-50','a12-28','mount-a12')}
        entry=bytes.fromhex(meta['entry_hex']);c=rt.camera_for_unit(meta.get('camera_ui',0))
        gradients,rings=fixtures(c)
        xs=np.r_[0,np.asarray(struct.unpack_from('>31H',entry,20)),4095]
        same=bool(np.array_equal(xs,c.curve.xs));c.curve=rt.mm.Curve(xs,c.curve.ys)
        for key in KEYS:
            path=LOCAL/'published_axis'/f'{i:02d}'/(key+'.json')
            if path.exists():continue
            reference_path=LOCAL/'fits'/f'{i:02d}'/(key+'.json');ref=rt.read(reference_path)
            cfg={**ref['config'],'published_curve_axis':True}
            P=Problem(c,gg['train']['x'],data['train_target'],gg['train']['sw'],cfg)
            starts=[np.asarray(ref['theta']),published_seed(P,entry)]
            candidates=[];attempts=[]
            if same:
                theta=starts[0]
                candidates=[(ref['train_objective'],theta)]
            else:
                for seed in starts:
                    theta,status=P.solve(seed,100);attempts.append(status)
                    for candidate in (seed,theta):
                        pred=P.predict_state(P.state(candidate,True),gg['train']['x'])
                        objective=training_objective(data['train_base'],pred,data['train_target'],gg['train']['sw'])
                        candidates.append((objective,candidate))
            objective,theta=min(candidates,key=lambda a:a[0]);p=P.packed(theta);state=P.unpack(rt.plain(p))
            scores={};predictions={}
            for group,g in gg.items():
                if not len(g['x']):scores[group]=None;continue
                pred=P.predict_state(state,g['x']);predictions[group]=pred.astype(np.uint8)
                scores[group]=rt.score(data[group+'_base'],pred,data[group+'_target'])
            quality=diagnostics(c,lambda xx,r:P.predict_state(state,xx,r),gradients,rings)
            seed=published_seed(P,entry)
            entry_prediction=np.rint(model.predict(entry,gg['train']['x'],bw_chroma='zero'))
            seed_error=float(abs(P.predict_state(P.state(seed,True),gg['train']['x'])-entry_prediction).max())
            rt.dump(path,dict(label='电脑预测，已发布曲线输入节点对照',index=i,name=meta['name'],
                reference_key=key,config=cfg,theta=theta,parameters=p,scores=scores,reference_scores=ref['scores'],
                quality=quality,solver_attempts=attempts,training_objective=objective,training_only_selection=True,
                input_nodes_equal_stock=same,input_nodes_optimized=False,
                published_entry_reconstruction_max_code_difference=seed_error,
                reconstruction_expected_exact=key.startswith('L4'),primary=False,
                meaning='Original published input axis, not searched or selected by held-out data. L1 still holds stock chroma rows.'))
            np.savez_compressed(path.with_suffix('.npz'),**predictions)
            print('Published axis',i,key,'same',same,'entry reconstruction',seed_error,flush=True)
        rt.finish('published_axis_'+str(i))

if __name__=='__main__':main()
