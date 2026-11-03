"""Separate single-unit input definitions from hardware-expression residuals."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np,ROOT,LOCAL
from infinite import arrays,bake,tetra

def colour_matrix(neutral,matrix,camera):
    u,f=camera.anchor['u_m'],camera.anchor['f']
    white=np.asarray(neutral)@np.asarray(matrix).T
    return np.diag(neutral)@np.asarray(matrix).T*(.18/((u-f)*white[1]))

def main():
    inventory=rt.read(ROOT/'research/vlog_alchemy_eval/dng_inventory.json')
    selected=set(rt.upstream.selected_paths())
    choices=[r for r in inventory if r['unit']=='mount-a12' and r.get('iso')==200
             and r['path'] not in selected and r['path'].startswith('captures/mount-')]
    if not choices:
        choices=[r for r in inventory if r['unit']=='mount-a12' and r.get('iso')==200 and r['path'] not in selected]
    source=sorted(choices,key=lambda r:r['path'])[0]
    mref,_=rt.upstream.scene(source['path'])
    protocol=rt.read(LOCAL/'protocol_private.json');ref=protocol['scene_inventory'][0]
    camera=rt.Camera()
    K50=colour_matrix(ref['neutral'],ref['matrix'],camera)
    KM=colour_matrix(mref['neutral'],mref['matrix'],camera)
    rowM=KM@np.linalg.inv(K50)
    columnM=rowM.T
    q=np.rint(columnM*1024).astype(int)
    for i in range(3):q[i,i]=1024-sum(q[i,j] for j in range(3) if j!=i)
    f=camera.anchor['f']*4095
    model,dat,_=rt.upstream.camera_model()
    entry=dat.entry_of(2,4)
    basefn=lambda x:model.predict(entry,x,bw_chroma='zero')
    source_info=dict(path=source['path'],sha256=rt.sha(ROOT/source['path']),
        selected_without_style_pixels_or_heldout_labels=True,reference_is_outside_declared_20_DNGs=True,
        provenance='DNG metadata only; not a measured sensor calibration or cross-camera spectral reference')
    rt.dump(LOCAL/'unit_input_adapter.json',dict(label='电脑预测',source=source_info,
        mount_to_50mm_white_balanced_RGB=columnM,q10_neutral_preserving=q,
        maximum_off_diagonal=float(abs(columnM-np.diag(np.diag(columnM))).max()),
        hypothetical_MCR_form='H2 row-sum-one 3x3, six off-diagonal coefficients; real MCR equation unknown',
        physical_MCR_verified=False))
    rows=[]
    measure=rt.module('ceiling_metadata_fuji',ROOT/'research/vlog_alchemy_eval/measure.py')
    official=measure.official_cubes()
    for index in list(range(27))+[47,48]:
        meta=rt.read(LOCAL/f'target_{index:02d}.json');data=arrays(LOCAL/f'target_{index:02d}.npz')
        if index<27:
            job=dict(path=ROOT/meta['source'],input=meta['input'],output=meta['output'],interpretation=meta.get('interpretation','declared'))
            target=rt.fit_adapter.target_of(job)
            render=lambda x,xyz:target.render(basefn(x),xyz)
            log_target=meta['input']=='vlog' or meta.get('interpretation')=='scene'
        else:
            style='CLASSIC-CHROME' if meta['builtin_slot']==5 else 'CLASSIC-Neg.'
            cube=official['flog2c',style][0]
            render=lambda x,xyz:cube.apply(measure.fg_input(xyz,'flog2c'))*255
            log_target=True
        unitfixed=lambda x:render(x,camera.xyz(x,mref['neutral'],mref['matrix']))
        table=bake(unitfixed,65,16380)
        group=arrays(LOCAL/meta.get('group_files',{}).get('mount-a12','samples_mount-a12.npz'))
        x=group['x'];base=data['mount-a12_base'];want=data['mount-a12_target']
        exact=unitfixed(x)
        predicted=np.rint(tetra(table,x,16380))
        shift=rt.stats(rt.delta_e00(rt.lab_from_codes(exact),rt.lab_from_codes(want)))
        direct=rt.score(base,np.rint(exact),want)
        scores=rt.score(base,predicted,want)
        # Q10 transport uses no target pixels. It only equates two declared DNG-to-XYZ maps.
        adapted=(x-f)@(q/1024).T+f
        transported=render(x,camera.xyz(adapted,np.asarray(ref['neutral']),np.asarray(ref['matrix'])))
        tq=rt.score(base,np.rint(transported),want)
        row=dict(label='电脑预测，已知输入元数据条件对照',index=index,name=meta['name'],
            source=source_info,unit='mount-a12',log_or_scene_target=log_target,
            fixed_unit_metadata_shift_de00=shift,known_target65_scores=scores,
            continuous_known_target_scores=direct,q10_input_transport_scores=tq,
            hardware_fit_result=False,extra_training_targets_used=False,
            conclusion_scope='Separates unit input conventions. Does not identify physical sensor error.')
        rows.append(row)
        out=LOCAL/'metadata_controls';out.mkdir(exist_ok=True)
        np.savez_compressed(out/f'{index:02d}.npz',table_q8_8=table,prediction=predicted.astype(np.uint8),
                            q10_transport_prediction=np.rint(np.clip(transported,0,255)).astype(np.uint8))
        print(index,meta['name'],'MOUNT unit-specific oracle65',scores['similarity_percent'],
              'metadata median',shift['median'],flush=True)
    rt.dump('metadata_controls.json',rows)
    rt.finish('metadata_controls')

if __name__=='__main__':main()
