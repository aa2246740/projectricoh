"""Evaluate MOUNT reference-row guards and fixed photo error regions without fitting."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from fit_one import quality, guard
from entry_codec import record_checks
import csv


def main():
    unit, ui = 'mount-a12', 2
    camera = rt.Camera(ui)
    gradients, rings = quality.fixtures(camera)
    guards, modes, coverages = [], [], []
    for index in range(35):
        base = rt.LOCAL/'targets'/unit
        meta = rt.read(base/f'{index:02d}.json')
        current = bytes.fromhex(meta['template_hex'])
        q = guard(camera, current, current, gradients, rings, ui, False)
        checks = record_checks(current)
        s = rt.release_dat().modules[ui].records[current[0]-1]
        guards.append(dict(label='电脑预测', unit=unit, index=index, name=meta['name'],
            current_row_scope=meta['current_row_scope'], quality=q,
            S_image_setting=s[3], independent_curves=checks['independent_curves'],
            current_record_sha256=checks['sha256'], row_crcs_valid=checks['row_crcs_valid'],
            row_domain_checks=checks['existing_row_domain_checks_pass']))
        for group in ('train', 'synthetic', 'photo_iso200', 'photo_other_iso'):
            if not meta['coverage'][group]['total']:
                continue
            coverage = meta['coverage'][group]
            coverages.append(dict(label='电脑预测', unit=unit, index=index, name=meta['name'], group=group,
                total=coverage['total'], supported=coverage['supported'],
                unsupported_fraction=1-coverage['supported']/coverage['total']))
            if not group.startswith('photo_'):
                continue
            values = rt.arrays(base/f'{index:02d}_{group}.npz')
            standard, target, pred = [rt.lab_from_codes(values[k]) for k in ('base', 'want', 'current')]
            cb = np.linalg.norm(standard[:, 1:], axis=1)
            hb = np.degrees(np.arctan2(standard[:, 2], standard[:, 1])) % 360
            masks = dict(all=np.ones(len(standard), bool), near_neutral=cb<5,
                shadow=standard[:, 0]<25, highlight=standard[:, 0]>75, saturated=cb>40,
                skin_region=(hb>=20)&(hb<=70)&(cb>=5)&(cb<=45)&(standard[:, 0]>=20)&(standard[:, 0]<=85))
            current_error = rt.delta_e00(pred, target)
            standard_error = rt.delta_e00(standard, target)
            for subset, mask in masks.items():
                if not mask.any():
                    continue
                c, b = rt.stats(current_error[mask]), rt.stats(standard_error[mask])
                modes.append(dict(label='电脑预测', unit=unit, index=index, name=meta['name'], group=group,
                    subset=subset, points=c['n'], current_median_de00=c['median'], current_p95_de00=c['p95'],
                    baseline_median_de00=b['median'], baseline_p95_de00=b['p95'],
                    overlapping_subsets=True, no_fit_performed=True))
        print('MOUNT reference row', index, q['reverse_hue_intervals'], q['max_integer_gradient_step_de00'], flush=True)
    rt.dump('current_mount_quality.json', guards)
    rt.dump('target_coverage.json', coverages)
    with (rt.HERE/'current_mount_error_modes.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(modes[0]))
        writer.writeheader()
        writer.writerows(modes)
    assert all(r['row_crcs_valid'] and r['row_domain_checks'] for r in guards)
    assert all(r['S_image_setting']==1 for r in guards), 'Reference row points at non-Standard S'
    print('Audited MOUNT 35 reference rows,', len(modes), 'photo-region rows')


if __name__ == '__main__':
    main()
