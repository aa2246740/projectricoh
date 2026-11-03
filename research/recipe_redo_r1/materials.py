"""Join recorded frame identities to the raw-file audit; keep unknowns unknown."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime_std as rt
from inventory import metadata, SELECTORS
import collections
import csv
import hashlib


def main():
    rows = rt.read(rt.LOCAL / 'inventory.json')
    # These are existing local backups, never mounted camera/card paths.
    native = [
        ('artifacts/card-b-mount/card-b-after-v34c-first-run-20261026T032356Z/root/DCIM/100RICOH', 'R8051477'),
        ('artifacts/card-b-mount/card-b-after-gen115-test-20261026T084138Z/root/DCIM/100RICOH', 'R8051479'),
    ]
    known = {}
    for folder, stem in native:
        path, jp = rt.ROOT / folder / (stem + '.DNG'), rt.ROOT / folder / (stem + '.JPG')
        if not path.is_file() or not jp.is_file():
            raise FileNotFoundError(path)
        jm = dict(path=str(jp), sha256=rt.sha(jp), **metadata(jp))
        row = dict(path=str(path), sha256=rt.sha(path), bytes=path.stat().st_size, **metadata(path),
            source_collection='named_offline_backup', jpeg_pairs=[dict(path=str(jp), sha256=jm['sha256'],
                color_space=jm['color_space'], same_directory=True, metadata=jm)],
            camera_jpeg_pair_confirmed=True, duplicate_paths=[str(path)],
            stock04_status='confirmed_native04', stock04_reason='native menu and frozen same-RAW validation',
            identity_evidence='research/gen115_field_r1/REPORT.md',
            date_group=jm['when'][:10], light_group='physical_chart_indoor_light_not_measured',
            scene_group='50mm_native_physical_20261026', calibration_role='primary_iso200')
        rows.append(row)
    labels = {}
    with (rt.ROOT / 'research/recipe_tag_r1/labels.csv').open() as stream:
        for r in csv.DictReader(stream):
            labels[(r['group'], r['file'])] = r
    # Published old labels have historical model involvement; retain that qualification.
    group_roots = {
        'street-g137': 'captures/street-g137-20261031',
        'chart-g150': 'captures/mount-g150-20261101',
        'daily-g150': 'captures/mount-g150-20261101',
        'chart-50mm': 'captures/a12-50/2026-10-24/chart-v2-R8051229-1311',
    }
    tag_rows = list(labels.values())
    for row in rows:
        p = Path(row['path'])
        row['selector_name'] = SELECTORS.get(row.get('selector'), 'unknown')
        if row['source_collection'] == 'named_offline_backup':
            continue
        row.update(stock04_status='unconfirmed', stock04_reason='No independent per-frame ROM-row identity',
            date_group=str(row.get('when') or 'unknown')[:10], light_group='unknown',
            scene_group=row['unit'] + '_' + str(row.get('when') or 'unknown')[:10] + '_' + p.parent.name,
            calibration_role='excluded_unconfirmed_identity', recipe_label=None)
        rel = str(p.relative_to(rt.ROOT)) if p.is_relative_to(rt.ROOT) else str(p)
        matched = next((r for r in tag_rows if r['file'] == p.stem and rel.startswith(r['folder'] + '/')), None)
        if matched:
            row.update(recipe_label=matched['truth'], identity_evidence=matched['source'],
                identity_strength=matched['label_evidence'])
            if matched['truth'] == '04':
                row.update(stock04_status='recorded04_with_historical_model_confirmation',
                    stock04_reason='Recorded capture order plus prior model check; not a blind label')
                if row['unit'] == 'a12-50':
                    row.update(light_group='screen_fixed_manual_wb', scene_group='50mm_screen_20261024')
                elif p.stem == 'R8051693':
                    row.update(light_group='screen_fixed_manual_wb', scene_group='mount_screen_20261101')
                elif p.stem == 'R8051533':
                    row.update(light_group='street_actual_illuminant_unknown', scene_group='mount_street_20261031')
        # Baselines explicitly named by the controlled T1/T3 studies.
        if rel.startswith('captures/a12-50/2026-10-20/stage2j-v1-calibration/') and p.stem in ('R8051179', 'R8051182'):
            row.update(stock04_status='recorded04_with_historical_model_confirmation', recipe_label='04',
                stock04_reason='Controlled A-B-A baseline; original T1/T3 capture identity',
                identity_evidence='research/t1_probe/probe2/REPORT.md', light_group='screen_fixed_manual_wb',
                scene_group='50mm_screen_20261020')
        folder = 'captures/a12-50/2026-10-21/'
        selected = {'t-probe': ('R8051193', 'R8051195', 'R8051197'),
                    'screen-closedloop': ('R8051198', 'R8051204'),
                    'chart-closedloop': ('R8051207', 'R8051213')}
        for sub, frames in selected.items():
            if rel.startswith(folder + sub + '/') and p.stem in frames:
                row.update(stock04_status='recorded04_with_historical_model_confirmation', recipe_label='04',
                    stock04_reason='Recorded A-B-A / closed-loop 04 baseline sequence',
                    identity_evidence='captures/a12-50/2026-10-21/README.md',
                    light_group='physical_chart_fixed_manual_wb' if sub == 'chart-closedloop' else 'screen_fixed_manual_wb',
                    scene_group='50mm_physical_20261021' if sub == 'chart-closedloop' else '50mm_screen_20261021')
        if row['unit'] == 'mount-a12' and rel.startswith('captures/a12-50/2026-10-24/chart-v2-R8051229-1311/') and p.stem in tuple('R805' + str(n) for n in range(1262, 1268)):
            row.update(stock04_status='recorded04_with_historical_model_confirmation', recipe_label='04',
                stock04_reason='Original six-page module 04 exchange; lens f/2 owner statement',
                identity_evidence='research/mount_calib_r1/REPORT.md', light_group='screen_fixed_manual_wb',
                scene_group='mount_screen_20261024', lens_scope='35mm M lens, f/2 owner recorded; correction menu unknown')
        if row['stock04_status'] != 'unconfirmed':
            row['calibration_role'] = 'primary_iso200' if row.get('iso') == 200 else 'high_iso_diagnostic'
            if row.get('selector') != 1 or not row['jpeg_pairs']:
                row['calibration_role'] = 'excluded_metadata_conflict'
        if 'chart-v2-R8051229-1311' in rel and p.stem in tuple('R805'+str(n) for n in range(1229, 1261)):
            row.update(calibration_role='excluded_owner_rejected_capture', stock04_status='unconfirmed',
                stock04_reason='Owner explicitly rejected the initial A group')
        if '/extra-iso200-chart/' in rel and p.stem in ('R8051205', 'R8051206'):
            row.update(calibration_role='excluded_owner_rejected_capture', stock04_status='unconfirmed',
                stock04_reason='Owner identified these two underexposed first attempts as mistakes',
                identity_evidence='captures/a12-50/2026-10-21/README.md')
    summary = dict(created_utc=rt.utc(), files=len(rows), unique_raws=len({r['sha256'] for r in rows}),
        by_unit={}, labels_are_not_blind=True, unknown_wb_offsets_retained=True,
        additional_backups=len(native), no_unconfirmed_daily_photo_promoted=True)
    for unit in ('a12-50', 'a12-28', 'mount-a12', 'other'):
        ur = [r for r in rows if r['unit'] == unit]
        primary = [r for r in ur if r['calibration_role'] == 'primary_iso200']
        summary['by_unit'][unit] = dict(files=len(ur), unique_raws=len({r['sha256'] for r in ur}),
            paired_files=sum(bool(r['jpeg_pairs']) for r in ur),
            statuses=dict(collections.Counter(r['stock04_status'] for r in ur)),
            primary_iso200_frames=len(primary),
            primary_scene_groups=dict(collections.Counter(r['scene_group'] for r in primary)),
            primary_lights=sorted({r['light_group'] for r in primary}),
            high_iso_diagnostic_frames=sum(r['calibration_role'] == 'high_iso_diagnostic' for r in ur))
    rt.dump(rt.LOCAL / 'materials.json', rows)
    rt.dump('materials_summary.json', summary)
    rt.dump(rt.LOCAL / 'identity_sources.json', {name: rt.sha(rt.ROOT / name) for name in (
        'research/gen115_field_r1/REPORT.md', 'research/recipe_tag_r1/labels.csv',
        'research/t1_probe/probe2/REPORT.md', 'captures/a12-50/2026-10-21/README.md',
        'research/mount_calib_r1/REPORT.md', 'research/mount_g150_field/REPORT.md')})
    print(summary)


if __name__ == '__main__':
    main()
