"""Verify saved 3D-table interpolation and the conditional two-stage artifacts."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np,LOCAL,ROOT
from run import load_arrays
from verify import close,integer_fields
from infinite import tetra
from two_pass import Joint
from quality import fixtures,diagnostics
from ceiling_model import Problem
from published_axis import published_seed

def main():
    learned=fixed=dynamic=metadata=two=two_C=free=axis=0;quality_results={};axis_seeds=[]
    model,_,_=rt.upstream.camera_model()
    for i in range(51):
        meta=rt.read(LOCAL/f'target_{i:02d}.json');data=load_arrays(LOCAL/f'target_{i:02d}.npz')
        gg={k:load_arrays(LOCAL/meta.get('group_files',{}).get(k,'samples_'+k+'.npz'))
            for k in ('train','synthetic','a12-50','a12-28','mount-a12')}
        camera=rt.camera_for_unit(meta.get('camera_ui',0));gradients,rings=fixtures(camera)
        if i<27:
            target=rt.fit_adapter.target_of(dict(path=ROOT/meta['source'],input=meta['input'],output=meta['output'],interpretation=meta.get('interpretation','declared')))
            for key,g in gg.items():
                if not len(g['x']):continue
                actual=target.render(data[key+'_base'],g['xyz'])
                assert np.max(abs(actual-data[key+'_target']))<1e-9,(i,key,'target changed after relocation')
        for tag in ('raw12','raw16_headroom'):
            path=LOCAL/'infinite'/f'{i:02d}'/(tag+'.json');doc=rt.read(path);a=load_arrays(path.with_suffix('.npz'))
            assert a['table_q8_8'].dtype==np.uint16
            for key,g in gg.items():
                if not len(g['x']):continue
                pred=np.rint(tetra(a['table_q8_8'],g['x'],doc['input_maximum']))
                assert np.array_equal(pred,a[key]),(i,tag,key)
                close(rt.score(data[key+'_base'],pred,data[key+'_target']),doc['scores'][key]);learned+=1
            quality_results[f'{i:02d}/{tag}']=diagnostics(camera,
                lambda x,r:np.rint(tetra(a['table_q8_8'],x,doc['input_maximum'])) if r else tetra(a['table_q8_8'],x,doc['input_maximum']),gradients,rings)
        doc=rt.read(LOCAL/'infinite'/f'{i:02d}'/'oracle_dynamic.json')
        for key,g in gg.items():
            if not len(g['x']):continue
            want=data[key+'_target'];pred=np.rint(np.rint(np.clip(want,0,255)/255*65535)*255/65535)
            close(rt.score(data[key+'_base'],pred,want),doc['scores'][key]);dynamic+=1
        path=LOCAL/'infinite'/f'{i:02d}'/'oracle_fixed65.json'
        if path.exists():
            doc=rt.read(path);a=load_arrays(path.with_suffix('.npz'))
            for key,g in gg.items():
                if not len(g['x']):continue
                pred=np.rint(tetra(a['table_q8_8'],g['x'],doc['input_maximum']))
                close(rt.score(data[key+'_base'],pred,data[key+'_target']),doc['scores'][key]);fixed+=1
        for level in (1,4):
            path=LOCAL/'two_pass_full'/f'{i:02d}'/('body_L'+str(level)+'.json')
            doc=rt.read(path);saved=load_arrays(path.with_suffix('.npz'))
            c=rt.camera_for_unit(meta.get('camera_ui',0))
            P=Joint(c,gg['train']['x'],data['train_target'],gg['train']['sw'],level,True)
            integer_fields(doc['first_parameters']);integer_fields(doc['second_parameters'])
            s1=P.first.unpack(doc['first_parameters']);s2=P.second.unpack(doc['second_parameters'])
            for key,g in gg.items():
                if not len(g['x']):continue
                intermediate=P.first.predict_state(s1,g['x'],True)
                pred=P.second.predict_state(s2,intermediate*doc['body_input_scale'],True)
                assert np.array_equal(pred,saved[key]),(i,level,key)
                close(rt.score(data[key+'_base'],pred,data[key+'_target']),doc['scores'][key]);two+=1
        if i<27 or i>=43:
            for level in (1,4):
                path=LOCAL/'two_pass_full_C'/f'{i:02d}'/('body_L'+str(level)+'.json')
                doc=rt.read(path);saved=load_arrays(path.with_suffix('.npz'))
                P=Joint(camera,gg['train']['x'],data['train_target'],gg['train']['sw'],level,True,'C')
                integer_fields(doc['first_parameters']);integer_fields(doc['second_parameters'])
                s1=P.first.unpack(doc['first_parameters']);s2=P.second.unpack(doc['second_parameters'])
                for key,g in gg.items():
                    if not len(g['x']):continue
                    middle=P.first.predict_state(s1,g['x'],True)
                    pred=P.second.predict_state(s2,middle*doc['body_input_scale'],True)
                    assert np.array_equal(pred,saved[key]),(i,level,key,'two C')
                    close(rt.score(data[key+'_base'],pred,data[key+'_target']),doc['scores'][key]);two_C+=1
        for reference in ('L1','L4_Y_post_add_after_Rbefore_fullfields'):
            path=LOCAL/'free_curves'/f'{i:02d}'/(reference+'.json')
            doc=rt.read(path);saved=load_arrays(path.with_suffix('.npz'))
            integer_fields(doc['parameters'],True)
            P=Problem(camera,gg['train']['x'],data['train_target'],gg['train']['sw'],doc['config'])
            state=P.unpack(doc['parameters'])
            for key,g in gg.items():
                if not len(g['x']):continue
                pred=P.predict_state(state,g['x']);assert np.array_equal(pred,saved[key]),(i,reference,key)
                close(rt.score(data[key+'_base'],pred,data[key+'_target']),doc['scores'][key]);free+=1
        for reference in ('L1','L4_Y_post_add_after_Rbefore_fullfields'):
            path=LOCAL/'published_axis'/f'{i:02d}'/(reference+'.json')
            doc=rt.read(path);saved=load_arrays(path.with_suffix('.npz'));integer_fields(doc['parameters'])
            c2=rt.camera_for_unit(meta.get('camera_ui',0))
            c2.curve=rt.mm.Curve(np.asarray(doc['parameters']['curve_x_u12']),c2.curve.ys)
            P=Problem(c2,gg['train']['x'],data['train_target'],gg['train']['sw'],doc['config'])
            state=P.unpack(doc['parameters'])
            if reference.startswith('L4'):
                entry=bytes.fromhex(meta['entry_hex']);seed=published_seed(P,entry)
                computed=P.predict_state(P.state(seed,True),gg['train']['x'],False)
                original=model.predict(entry,gg['train']['x'],bw_chroma='zero')
                maximum=float(abs(computed-original).max())
                rounded=abs(np.rint(computed)-np.rint(original))
                assert maximum<1e-7,(i,'published row float reconstruction',maximum)
                axis_seeds.append(dict(index=i,name=meta['name'],continuous_max_code_difference=maximum,
                    rounded_max_code_difference=float(rounded.max()),rounded_differing_pixels=int((rounded>0).any(axis=1).sum()),
                    explanation='Analytically equal model paths may choose different sides of an exact half-code after floating-point arithmetic.'))
            for key,g in gg.items():
                if not len(g['x']):continue
                pred=P.predict_state(state,g['x']);assert np.array_equal(pred,saved[key]),(i,reference,key,'published axis')
                close(rt.score(data[key+'_base'],pred,data[key+'_target']),doc['scores'][key]);axis+=1
        print('Verified auxiliary',i,flush=True)
    for doc in rt.read(rt.HERE/'metadata_controls.json'):
        i=doc['index'];meta=rt.read(LOCAL/f'target_{i:02d}.json');data=load_arrays(LOCAL/f'target_{i:02d}.npz')
        g=load_arrays(LOCAL/meta.get('group_files',{}).get('mount-a12','samples_mount-a12.npz'))
        a=load_arrays(LOCAL/'metadata_controls'/f'{i:02d}.npz')
        pred=np.rint(tetra(a['table_q8_8'],g['x'],16380))
        assert np.array_equal(pred,a['prediction'])
        close(rt.score(data['mount-a12_base'],pred,data['mount-a12_target']),doc['known_target65_scores'])
        close(rt.score(data['mount-a12_base'],a['q10_transport_prediction'],data['mount-a12_target']),doc['q10_input_transport_scores'])
        metadata+=1
    from display_oracle import tetra as display_tetra
    from PIL import Image,ImageOps
    display=0
    for doc in rt.read(rt.HERE/'display_oracle.json'):
        meta=rt.read(LOCAL/f'target_{doc["index"]:02d}.json')
        with Image.open(ROOT/doc['jpeg']) as im:
            a=np.asarray(ImageOps.exif_transpose(im).convert('RGB')).reshape(-1,3)
            pixels=a[np.linspace(0,len(a)-1,doc['n']).astype(int)].astype(float)
        target=rt.fit_adapter.target_of(dict(path=ROOT/meta['source'],input=meta['input'],output=meta['output'],interpretation=meta.get('interpretation','declared')))
        want=target.render(pixels,None);tables=load_arrays(LOCAL/'display_oracle'/f'{doc["index"]:02d}.npz')
        for n in (17,33,65):
            pred=np.rint(display_tetra(tables[f'cube_{n}_q8_8'],pixels))
            close(rt.score(pixels,pred,want),doc['scores'][str(n)]);display+=1
    rt.dump(LOCAL/'verification_auxiliary.json',dict(label='电脑预测，离线结果复核',
        learned_table_group_scores=learned,fixed_table_group_scores=fixed,dynamic_precision_scores=dynamic,
        full_two_stage_group_scores=two,metadata_tables=metadata,display_table_scores=display,
        full_two_stage_C_group_scores=two_C,
        free_curve_group_scores=free,
        published_axis_group_scores=axis,
        original27_targets_rerendered_after_relocation=True,
        saved_predictions_byte_equal=True,score_tolerance=2e-8,hardware_acceptance=False))
    rt.dump('auxiliary_quality.json',quality_results)
    rt.dump('published_axis_seed_checks.json',axis_seeds)
    rt.finish('verify_auxiliary')

if __name__=='__main__':main()
