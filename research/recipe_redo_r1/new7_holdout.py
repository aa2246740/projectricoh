"""Render fixed MOUNT records on the seven new RAWs, without using their JPEGs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import prepare_targets as pt
from prepare_inputs import sample
from entry_codec import predict
from photo_evidence import rows as per_photo_rows
import csv
import signal
import argparse
import shutil
from capabilities import mount_l1_enabled


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--level',type=int,choices=(0,1),default=1 if mount_l1_enabled() else 0)
    ap.add_argument('--tag',default='')
    ap.add_argument('--bank')
    args=ap.parse_args();suffix='_L1' if args.level else ''
    assert not args.tag or Path(args.tag).name==args.tag
    destination = rt.LOCAL/('new7/recipe_holdout'+suffix+('_'+args.tag if args.tag else ''))
    assert not destination.exists(), 'Keep the first independent holdout receipt'
    destination.mkdir(parents=True)
    records = rt.read(rt.LOCAL/'new7/materials.json')
    decision = rt.read(rt.LOCAL/'new7/owner_identity_decision.json')
    assert not decision.get('used_for_current_04_training',False)
    coefficients = np.asarray(rt.read(rt.LOCAL/'inputs/mount-a12/definition.json')['calibration_coefficients'])
    pieces,photos = [],[]
    for record in records:
        values,info = sample(record)
        raw = values['raw_codes']
        pieces.append(dict(x=rt.calibration_apply(raw/4095,coefficients),raw_codes=raw,xyz=values['xyz'],
            sw=np.ones(len(raw)),photo_id=np.full(len(raw),len(photos),int),iso=np.full(len(raw),record['iso'],int)))
        photos.append(info)
    data = {key:np.concatenate([piece[key] for piece in pieces]) for key in pieces[0]}
    if args.level:
        frozen=rt.arrays(rt.LOCAL/'new7/recipe_holdout/inputs.npz')
        assert all(np.array_equal(data[k],frozen[k]) for k in data), 'New L1 RAW inputs changed from frozen L0 holdout'
    np.savez_compressed(destination/'inputs.npz',**data)
    rt.dump(destination/'photos.json',photos)
    bank_path=rt.LOCAL/('mount_L1_before_new7/candidate_registry.json' if args.level else 'mount_main_after_refinement/candidate_registry.json')
    if args.bank:bank_path=rt.HERE/args.bank
    bank = rt.read(bank_path)
    profiles = [r for r in bank['profiles'] if r['unit']=='mount-a12']
    assert len(profiles)==35 and all(r['verified_record_replay'] for r in profiles)
    base = predict(rt.release_dat().entry_of(2,4),data['x'],2,round_output=False)
    dense = {slot:pt.builtin.DenseTarget(slot) for slot in (1,2)}
    cubes = pt.official()
    inverse_source = rt.ROOT/'research/huzi_luts/local/artifacts/downloads/vlog-alchemy-20261024/Luts/Panasonic-Standard/Conversion/S1RIIS2V.cube'
    if args.level:
        old_inverse=rt.LOCAL/'new7/recipe_holdout/s1rii_inverse.npz'
        arrays=rt.arrays(old_inverse);inverse_rgb,inverse_error=arrays['rgb'],arrays['residual']
        shutil.copyfile(old_inverse,destination/'s1rii_inverse.npz')
    else:
        inverse_mod = rt.module('new7_s1rii_inverse',rt.SOURCE/'research/huzi_luts/panasonic.py')
        inverse = inverse_mod.StandardInverse(pt.Cube.read(inverse_source))
        inverse_rgb,inverse_error = [],[]
        for start in range(0,len(data['x']),512):
            rgb,error = inverse.invert(pt.xyz_to_encoded(data['xyz'][start:start+512],'vlog'))
            inverse_rgb.append(rgb*255)
            inverse_error.append(error)
        inverse_rgb,inverse_error = np.vstack(inverse_rgb),np.concatenate(inverse_error)
        np.savez_compressed(destination/'s1rii_inverse.npz',rgb=inverse_rgb,residual=inverse_error)
    leica_root = rt.ROOT/'artifacts/downloads/huzi-panasonic-std-luts-20261024/original'
    leica = {7:pt.Cube.read(leica_root/'Leica Chrome.cube'),8:pt.Cube.read(leica_root/'Leica VIVID.cube')}
    summaries,photographs = [],[]
    for row in profiles:
        index = row['index']
        meta = rt.read(rt.LOCAL/'targets/mount-a12'/f'{index:02d}.json')
        template = bytes.fromhex(meta['template_hex'])
        record_path = rt.HERE/row['record_file']
        entry = record_path.read_bytes()
        assert rt.sha(record_path)==row['record_sha256']
        fit_doc = rt.read(rt.HERE/row['fit_receipt'])
        valid = np.ones(len(base),bool)
        if index<27:
            source = Path(meta['source'])
            assert rt.sha(source)==meta['source_sha256']
            target = pt.Target(pt.Cube.read(source),meta['input'],meta['output'])
            if meta['interpretation']=='scene':
                want = np.clip(target.cube.apply(pt.xyz_to_encoded(data['xyz'],'srgb')),0,1)*255
            else:
                want = target.render(base,data['xyz'])
        else:
            slot = meta['builtin_slot']
            if slot in (1,2):
                want,valid,_ = dense[slot](data['raw_codes'],data['xyz'],base)
            elif slot==3:
                want,valid,_ = pt.builtin.hc_target(data['raw_codes'],data['xyz'],base)
            elif slot==4:
                want = base.copy()
            elif slot in (5,6):
                want = cubes[slot,'historical'][0].apply(pt.fg_input(data['xyz']))*255
            else:
                want = np.clip(.3*inverse_rgb+.7*leica[slot].apply(inverse_rgb/255)*255,0,255)
        prediction = predict(entry,data['x'],2)
        ordinary = bytearray(entry)
        ordinary[0]=1
        assert np.array_equal(prediction,np.rint(rt.camera_model(2).predict(bytes(ordinary),data['x'])))
        current = predict(template,data['x'],2)
        if args.level:
            frozen=rt.arrays(rt.LOCAL/'new7/recipe_holdout'/f'{index:02d}.npz')
            assert np.array_equal(valid,frozen['valid_source_mask'])
            assert np.array_equal(want[valid],frozen['want']), 'Target changed between L0 and L1 holdout'
        values = {key:value[valid] for key,value in data.items()}
        values.update(base=base[valid],want=want[valid],current=current[valid],prediction=prediction[valid],valid_source_mask=valid)
        np.savez_compressed(destination/f'{index:02d}.npz',**values)
        current_score = rt.score(base[valid],current[valid],want[valid])
        candidate_score = rt.score(base[valid],prediction[valid],want[valid])
        med_reg = candidate_score['de00']['median']>current_score['de00']['median']+1e-10
        p95_reg = candidate_score['de00']['p95']>current_score['de00']['p95']+1e-10
        result = dict(label='电脑预测，新增RAW整组留出',unit='mount-a12',index=index,name=row['name'],
            record_sha256=row['record_sha256'],record_file=row['record_file'],fit_receipt=row['fit_receipt'],
            points=int(valid.sum()),photos=7,scene='mount_natural_20261103_whole_collection',
            current=current_score,candidate=candidate_score,median_regressed=med_reg,p95_regressed=p95_reg,
            scene_gate_pass=not (med_reg or p95_reg),parameters_changed=False,observed_jpeg_used=False,
            inverse_residual=rt.stats(inverse_error) if index in (33,34) else None)
        summaries.append(result)
        photographs += per_photo_rows(fit_doc,'photo_new7_RAW_diagnostic',values,prediction[valid],photos)
        print(index,row['name'],'new RAW holdout',candidate_score['similarity_percent'],'scene pass',result['scene_gate_pass'],flush=True)
    receipt = dict(label='电脑预测，新增RAW留出',created_utc=rt.utc(),profiles=summaries,
        artifact_root=str(destination.relative_to(rt.HERE)),
        independent_new_capture_group=True,collection_kept_whole=True,
        parameters_frozen_before_holdout_scoring=True,
        new7_not_used_in_training_objective_or_parameter_selection=True,
        chronology='Record bank frozen before holdout scoring; no claim of freezing before the capture notice',
        observed_jpegs_not_used_as_04_truth=True,new7_not_used_for_04_coefficient_fitting=True,
        level=args.level,mount_L1_response_amplitude_unclosed=bool(args.level),
        source_bank_sha256=rt.sha(bank_path),
        input_sha256=rt.sha(destination/'inputs.npz'),no_dat_built=True)
    rt.dump(destination/'scores.json',receipt)
    rt.dump('new7_raw_holdout_summary'+suffix+'.json',receipt)
    with (rt.HERE/('new7_photo_scores'+suffix+'.csv')).open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(photographs[0]))
        writer.writeheader()
        writer.writerows(photographs)


if __name__=='__main__':
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('New RAW holdout exceeded 25 minutes')))
    signal.alarm(1500)
    main()
