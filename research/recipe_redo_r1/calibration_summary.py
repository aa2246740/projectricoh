"""Publish score-only calibration receipts without publishing response parameters."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime_std as rt
import csv

SELECTED = {'mount-a12': 'mount_screen_20261101_degree1',
            'a12-50': '50mm_native_physical_20261026_degree2'}


def main():
    scores, selected = [], {}
    for unit in SELECTED:
        for path in sorted((rt.LOCAL/'calibration'/unit).glob('*degree*.json')):
            doc = rt.read(path)
            for group, values in doc['group_scores'].items():
                row = dict(label='电脑预测', unit=unit, fit=path.stem, degree=doc['degree'],
                    scene_group=group, role=values['role'], frames=len(values['frames']),
                    points=values['recalibrated']['n'], n_train=doc['n_train'],
                    selected_primary=path.stem == SELECTED[unit])
                for model in ('transferred_50mm', 'unit_uncorrected', 'legacy_50mm_input_map', 'recalibrated'):
                    for field in ('median', 'p95', 'max', 'mean'):
                        row[model+'_'+field+'_de00'] = values[model][field]
                scores.append(row)
            if path.stem == SELECTED[unit]:
                values = doc['group_scores'][doc['holdout_group']]
                a, b = values['transferred_50mm'], values['recalibrated']
                selected[unit] = dict(label='电脑预测', fit=path.stem, degree=doc['degree'],
                    train_points=doc['n_train'], holdout_points=doc['n_holdout'],
                    train_groups=doc['training_groups'], holdout_group=doc['holdout_group'],
                    group_scores=values,
                    median_error_reduction_percent=100*(1-b['median']/a['median']),
                    p95_error_reduction_percent=100*(1-b['p95']/a['p95']),
                    selection_receipt='calibration_model_controls.json',
                    legacy_primary_eligible_flag_superseded_by_nested_selection=unit=='a12-50',
                    coefficient_file=str(path.relative_to(rt.HERE)), coefficient_file_sha256=rt.sha(path),
                    no_outer_holdout_parameter_fit=True,
                    response_kernel='native unit static parameters with transferred 50mm measured angular kernel')
    with (rt.HERE/'calibration_scores.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(scores[0]))
        writer.writeheader()
        writer.writerows(scores)
    owner_path = rt.LOCAL/'new7/owner_identity_decision.json'
    owner = rt.read(owner_path) if owner_path.exists() else {}
    received = bool(owner.get('owner_confirmed_all_seven') and owner.get('eligible_for_04_calibration'))
    rt.dump('calibration_summary.json', dict(label='电脑预测', selected=selected,
        comparison='DNG flat regions versus paired 04 JPEGs with recorded provenance and qualified historical labels',
        stock04_labels_include_historical_model_confirmation=True,
        independent_natural_light_mount04_missing=not received,
        owner_confirmed_natural_scene_mount04_received=received,
        new7_role='whole-session outer holdout, excluded from these frozen coefficient fits' if received else None,
        new7_light_scope='mixed fluorescent/window light and exterior views; daylight WB is not a controlled illuminant' if received else None,
        new7_calibration_holdout_summary='new7_04_calibration_holdout.json' if received else None,
        independent_28mm04_missing=True, physical_camera_acceptance=False))
    for unit, values in selected.items():
        print(unit, values['median_error_reduction_percent'], values['p95_error_reduction_percent'])


if __name__ == '__main__':
    main()
