"""Validate the frozen 04 input map on the entire owner-confirmed new session."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from calibrate import sample


def main():
    records=rt.read(rt.LOCAL/'new7/materials.json')
    decision=rt.read(rt.LOCAL/'new7/owner_identity_decision.json')
    assert decision['owner_confirmed_all_seven']
    current_path=rt.LOCAL/'calibration/mount-a12/mount_screen_20261101_degree1.json'
    calibration=rt.read(current_path)
    C=np.asarray(calibration['coefficients'])
    legacy=rt.read(rt.SOURCE/'research/refit_50mm_r7/local/folds/full/calibration.json')
    LC=np.asarray(legacy['residual_coefficients'])
    stock=rt.release_dat().entry_of(2,4)
    own,transferred=rt.camera_model(2),rt.camera_model(2,transferred=True)
    pooled={name:[] for name in ('transferred_50mm','unit_uncorrected','legacy_50mm_input_map','recalibrated')}
    frames=[]
    for record in records:
        assert record['stock04_status']=='owner_confirmed_native04'
        assert record['scene_group'] not in calibration['training_groups']
        assert rt.sha(record['path'])==record['sha256']
        assert rt.sha(record['jpeg_pairs'][0]['path'])==record['jpeg_pairs'][0]['sha256']
        values,info=sample(record)
        good=values['valid']
        raw,observed=values['raw_wb'][good],values['observed'][good]
        predictions=dict(transferred_50mm=transferred.predict(stock,raw*4095),
            unit_uncorrected=own.predict(stock,raw*4095),
            legacy_50mm_input_map=own.predict(stock,rt.calibration_apply(raw,LC)),
            recalibrated=own.predict(stock,rt.calibration_apply(raw,C)))
        errors={name:rt.delta_e00(rt.lab_from_codes(value),rt.lab_from_codes(observed)) for name,value in predictions.items()}
        for name,error in errors.items():pooled[name].append(error)
        frames.append(dict(frame=Path(record['path']).stem,raw_sha256=record['sha256'],
            jpeg_sha256=record['jpeg_pairs'][0]['sha256'],points=len(raw),scene=record['scene_group'],
            scores={name:rt.stats(error) for name,error in errors.items()}))
        rt.dump(rt.LOCAL/'new7/04_holdout'/f'{Path(record["path"]).stem}.json',frames[-1])
    scores={name:rt.stats(np.concatenate(values)) for name,values in pooled.items()}
    result=dict(label='电脑预测，与机主确认原厂04相机JPG比较',created_utc=rt.utc(),photos=7,
        confirmation_source='机主口头确认，2026-11-03',white_balance='daylight preset, from files and owner',
        assignment='entire new capture session kept as an outer holdout',
        current_calibration_sha256=rt.sha(current_path),training_groups=calibration['training_groups'],
        new_session_not_used_for_coefficient_fitting=True,no_new_parameter_fitting=True,
        no_reference_chart_expected_values=True,no_per_photo_exposure_or_white_balance_fit=True,
        scores=scores,frames=frames,
        median_error_reduction_vs_transferred_percent=100*(1-scores['recalibrated']['median']/scores['transferred_50mm']['median']),
        numerical_scope='fixed continuous 04 model against averages of flat JPEG regions, not new-recipe camera acceptance')
    rt.dump('new7_04_calibration_holdout.json',result)
    print('New confirmed 04 holdout',len(frames),'photos',scores['recalibrated']['n'],'points')
    for name,score in scores.items():print(name,'median',score['median'],'P95',score['p95'])


if __name__=='__main__':main()
