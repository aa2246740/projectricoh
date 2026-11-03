"""Evaluate central-only MOUNT04 input calibration, with edge data diagnostic only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import calibrate
import signal
import argparse
import shutil


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',default='spatial_calibration_lens_r3');args=ap.parse_args()
    assert Path(args.tag).name==args.tag
    base=rt.LOCAL
    out=base/args.tag
    assert not out.exists(), 'Preserve the first run and use a new output version'
    out.mkdir()
    snapshot=rt.freeze_task_code()
    rows=[r for r in rt.read(base/'materials.json') if r['unit']=='mount-a12' and r['calibration_role']=='primary_iso200']
    seen=set();frames=[];parts=[]
    for row in rows:
        if row['sha256'] in seen:continue
        seen.add(row['sha256'])
        values,info=calibrate.sample(row)
        center=calibrate.central_mask(values,info)
        width,height=info['dng_summary']['default_crop_size_wh']
        xy=values['centers']
        edge=(xy[:,0]<.1*width)|(xy[:,0]>.9*width)|(xy[:,1]<.1*height)|(xy[:,1]>.9*height)
        good=values['valid']&center
        assert good.sum()>=10
        parts.append(dict(raw=values['raw_wb'][good],observed=values['observed'][good],xyz=values['xyz'][good],
            jpeg_sd=values['jpeg_sd'][good],group=np.full(good.sum(),row['scene_group']),
            frame=np.full(good.sum(),Path(row['path']).stem)))
        frames.append((row,values,info,center,edge))
    assert len(frames)==14
    dataset={k:np.concatenate([p[k] for p in parts]) for k in parts[0]}
    dest=out/'calibration/mount-a12';dest.mkdir(parents=True)
    np.savez_compressed(dest/'dataset.npz',**dataset)
    hold='mount_screen_20261101';natural='mount_natural_20261103_whole_collection'
    old_path=base/'calibration/mount-a12'/ (hold+'_degree1.json')
    old=rt.read(old_path)
    starts=[('zero',None),('frozen',old['coefficients']),('half_frozen',np.asarray(old['coefficients'])*.5)]
    rt.LOCAL=out
    try:
        for name,initial in starts:
            calibrate.fit('mount-a12',hold,1,80,exclude_groups=(natural,),prefix=name+'_',initial_coefficients=initial)
    finally:rt.LOCAL=base
    new_path=dest/(hold+'_degree1.json')
    candidates=[(dest/(name+'_'+hold+'_degree1.json'),name) for name,_ in starts]
    best,selected_name=min(candidates,key=lambda pair:(rt.read(pair[0])['training_objective_weighted_rgb_plus_regularization'],pair[1]))
    shutil.copyfile(best,new_path)
    new=rt.read(new_path)
    coefficients={'frozen_full_frame_map':np.asarray(old['coefficients']),
                  'central60_refit':np.asarray(new['coefficients'])}
    camera=rt.Camera(2)
    grouped={};per_frame=[]
    for row,values,info,center,edge in frames:
        observed_lab=rt.lab_from_codes(values['observed'])
        predictions={name:camera.stock(rt.calibration_apply(values['raw_wb'],C)) for name,C in coefficients.items()}
        errors={name:rt.delta_e00(rt.lab_from_codes(p),observed_lab) for name,p in predictions.items()}
        deltas={name:rt.lab_from_codes(p)-observed_lab for name,p in predictions.items()}
        result=dict(frame=Path(row['path']).stem,scene=row['scene_group'],lens=row.get('lens_owner_description',row.get('lens_scope','unknown')),
            aperture=row.get('capture_aperture_f_owner'),raw_sha256=row['sha256'],jpeg_sha256=row['jpeg_pairs'][0]['sha256'],regions={})
        for region,mask in [('central60',center),('outer10_diagnostic',edge),('legacy_full_frame_diagnostic',np.ones(len(center),bool))]:
            mask=mask&values['valid']
            if not mask.any():continue
            result['regions'][region]={name:dict(de00=rt.stats(error[mask]),
                median_Lab_residual=np.median(deltas[name][mask],axis=0)) for name,error in errors.items()}
            for name,error in errors.items():
                grouped.setdefault((row['scene_group'],region,name),[]).append(error[mask])
        np.savez_compressed(out/(result['frame']+'_residuals.npz'),centers=values['centers'],
            valid=values['valid'],central=center,edge_diagnostic=edge,
            old_error=errors['frozen_full_frame_map'],central_refit_error=errors['central60_refit'],
            old_Lab_residual=deltas['frozen_full_frame_map'],central_refit_Lab_residual=deltas['central60_refit'])
        per_frame.append(result)
    groups=[]
    for group,region in sorted({(g,r) for g,r,n in grouped}):
        groups.append(dict(scene=group,region=region,scores={name:rt.stats(np.concatenate(grouped[group,region,name])) for name in coefficients}))
    held=[r for r in groups if r['region']=='central60' and r['scene'] in (hold,natural)]
    accepted=all(r['scores']['central60_refit'][field]<=r['scores']['frozen_full_frame_map'][field]+1e-10 for r in held for field in ('median','p95'))
    rt.dump(out/'frames.json',per_frame)
    rt.assert_task_code(snapshot)
    rt.dump('spatial_calibration_summary.json',dict(label='电脑预测，与确认04 JPG的固定区域对照',created_utc=rt.utc(),
        policy=dict(central_width_fraction=.6,central_height_fraction=.6,minimum_edge_margin_fraction=.2,
                    full_12_by_12_patch_must_be_inside=True,selected_without_image_error=True),
        native04_frames=14,center_dataset_points=len(dataset['raw']),training_groups=new['training_groups'],
        whole_scene_holdouts=[hold,natural],new7_used_for_fit=False,
        groups=groups,central_map_passes_both_heldout_median_and_p95=accepted,
        old_map_sha256=rt.sha(old_path),central_map_file=str(new_path.relative_to(rt.HERE)),central_map_sha256=rt.sha(new_path),
        frame_details=str((out/'frames.json').relative_to(rt.HERE)),
        selected_start=selected_name,start_selection='weighted training RGB loss plus fixed regularization only',
        all_start_receipts=[str(p.relative_to(rt.HERE)) for p,n in candidates],
        absolute_optical_vignetting_identified=False,absolute_lens_colour_shading_identified=False,
        limitation='No uniform flat-field or same-view aperture series; spatial response residuals also include scene spectra and in-camera corrections',
        old_training_lens_not_inferred_from_today_owner_confirmation=True,main_recipe_parameters_changed=False,
        code_snapshot=snapshot))
    print('Central60 calibration comparison',len(dataset['raw']),'points; both heldout median/P95 pass',accepted)
    for row in held:print(row['scene'],row['scores'],flush=True)


if __name__=='__main__':
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Central calibration exceeded 25 minutes')))
    signal.alarm(1500)
    main()
