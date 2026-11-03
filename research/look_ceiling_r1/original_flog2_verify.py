"""Integer reconstruction and public summary of the historical six Fuji profiles."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from original_flog2 import BASE,INDICES
from ceiling_model import Problem,variants
from run import load_arrays,training_objective
from quality import fixtures,diagnostics
from verify import close,integer_fields
from infinite import tetra

def main():
    profiles=[];fits=groups=pixels=learned=0
    for i in INDICES:
        meta=rt.read(BASE/f'target_{i:02d}.json');data=load_arrays(BASE/f'target_{i:02d}.npz')
        gg={k:load_arrays(BASE/meta['group_files'][k]) for k in ('train','synthetic','a12-50','a12-28','mount-a12')}
        c=rt.camera_for_unit(meta['camera_ui']);gradients,rings=fixtures(c);rows=[]
        for config in variants():
            key=config['key']+('_fullfields' if config['level']>=2 else '')
            path=BASE/'fits'/f'{i:02d}'/(key+'.json');doc=rt.read(path);saved=load_arrays(path.with_suffix('.npz'))
            P=Problem(c,gg['train']['x'],data['train_target'],gg['train']['sw'],doc['config'])
            integer_fields(doc['parameters']);s=P.unpack(doc['parameters'])
            for group,g in gg.items():
                if not len(g['x']):continue
                pred=P.predict_state(s,g['x']);assert np.array_equal(pred,saved[group]),(i,key,group)
                close(rt.score(data[group+'_base'],pred,data[group+'_target']),doc['scores'][group]);groups+=1;pixels+=len(pred)
                if 'per_photo' in doc['scores'][group]:
                    for pid in np.unique(g['photo_id']):
                        mask=g['photo_id']==pid
                        close(rt.score(data[group+'_base'][mask],pred[mask],data[group+'_target'][mask]),doc['scores'][group]['per_photo'][str(pid)])
            quality=diagnostics(c,lambda xx,r:P.predict_state(s,xx,r),gradients,rings)
            close(quality,doc['quality'])
            assert abs(training_objective(data['train_base'],saved['train'],data['train_target'],gg['train']['sw'])-doc['train_objective'])<2e-8
            row={k:doc[k] for k in ('label','config','scores','quality','parameter_quantization_de00','gain_over_parent_pp','overfit_flags','photo_synthetic_gap_pp','solver_attempts','selection')}
            if doc.get('parent'):
                parent=rt.read(path.parent/(doc['parent']+'.json'))
                improved=doc['train_objective']<parent['train_objective']-1e-10
                row['overfit_flags']={g:bool(improved and doc['scores'][g]['de00']['median']>=parent['scores'][g]['de00']['median']-1e-10) for g in ('synthetic','a12-50','mount-a12')}
            rows.append(row)
            fits+=1
        inf={}
        for tag in ('raw12','raw16_headroom'):
            path=BASE/'infinite'/f'{i:02d}'/(tag+'.json');doc=rt.read(path);a=load_arrays(path.with_suffix('.npz'))
            for group,g in gg.items():
                if not len(g['x']):continue
                pred=np.rint(tetra(a['table_q8_8'],g['x'],doc['input_maximum']))
                assert np.array_equal(pred,a[group]);close(rt.score(data[group+'_base'],pred,data[group+'_target']),doc['scores'][group]);learned+=1
            inf[tag]=doc
        profiles.append(dict(index=i,name=meta['name'],unit=meta['unit'],slot=meta['builtin_slot'],
            target_variant=meta['target_variant'],official_LUT=meta['official_LUT'],current_scores=meta['scores'],
            target_shift_from_requested_FLog2C33_de00=meta['target_shift_from_requested_FLog2C33_de00'],fits=rows,infinite=inf))
        print('Verified historical FLog2',i,flush=True)
    assert fits==180 and groups==720 and learned==48
    rt.dump('original_flog2_results.json',dict(label='电脑预测',profiles=profiles,
        verification=dict(status='PASS',integer_models=fits,scored_groups=groups,reconstructed_pixels=pixels,
            quality_cases=fits,learned_table_group_scores=learned,saved_predictions_byte_equal=True),
        why='Historical05/06 reports specify F-Log2/F-Gamut65. The requested F-Log2C33 branch is retained separately.',
        same_training_and_holdout=True,all_other_model_hypotheses_unchanged=True,
        initialization='Same retained bounded C-control parameter starts, plus newly fitted original-target parent fallbacks; training-only selection.'))
    rt.finish('original_flog2_verify')

if __name__=='__main__':main()
