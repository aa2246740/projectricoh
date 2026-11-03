"""Measure the explicit monotone-curve constraint without silently calling it hardware."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np,LOCAL
from ceiling_model import Problem
from run import load_arrays,training_objective
from quality import fixtures,diagnostics

def main():
    for i in range(51):
        meta=rt.read(LOCAL/f'target_{i:02d}.json');data=load_arrays(LOCAL/f'target_{i:02d}.npz')
        gg={k:load_arrays(LOCAL/meta.get('group_files',{}).get(k,'samples_'+k+'.npz'))
            for k in ('train','synthetic','a12-50','a12-28','mount-a12')}
        c=rt.camera_for_unit(meta.get('camera_ui',0));gradients,rings=fixtures(c)
        for key in ('L1','L4_Y_post_add_after_Rbefore_fullfields'):
            path=LOCAL/'free_curves'/f'{i:02d}'/(key+'.json')
            if path.exists():continue
            ref=rt.read(LOCAL/'fits'/f'{i:02d}'/(key+'.json'))
            cfg={**ref['config'],'full_fields':True,'free_curves':True}
            P=Problem(c,gg['train']['x'],data['train_target'],gg['train']['sw'],cfg)
            start=np.asarray(ref['theta']);theta,status=P.solve(start,100)
            candidates=[]
            for candidate in (start,theta):
                s=P.state(candidate,True);pred=P.predict_state(s,gg['train']['x'])
                candidates.append((training_objective(data['train_base'],pred,data['train_target'],gg['train']['sw']),candidate))
            objective,theta=min(candidates,key=lambda a:a[0]);p=P.packed(theta);s=P.unpack(rt.plain(p))
            scores={};predictions={}
            for group,g in gg.items():
                if not len(g['x']):scores[group]=None;continue
                prediction=P.predict_state(s,g['x']);predictions[group]=prediction.astype(np.uint8)
                scores[group]=rt.score(data[group+'_base'],prediction,data[group+'_target'])
            quality=diagnostics(c,lambda xx,r:P.predict_state(s,xx,r),gradients,rings)
            rt.dump(path,dict(label='电脑预测，解除曲线单调约束对照',index=i,name=meta['name'],
                reference_key=key,config=cfg,theta=theta,parameters=p,scores=scores,reference_scores=ref['scores'],
                training_objective=objective,solver=status,quality=quality,training_only_selection=True,
                negative_type26_steps=int((np.diff(np.asarray(p['curve_y_u8']),axis=1)<0).sum()),
                negative_RLUT_steps=int((np.diff(np.asarray(p['rlut_output_u12']),axis=1)<0).sum()),
                primary=False,hardware_response_extrapolation=True))
            np.savez_compressed(path.with_suffix('.npz'),**predictions)
            print('Free curve diagnostic',i,key,flush=True)
        rt.finish('free_curves_'+str(i))

if __name__=='__main__':main()
