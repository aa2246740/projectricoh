"""Refresh the material ledger and audit the frozen prior result matrix."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime_std as rt
import collections
import csv
import statistics


def materials():
    rows = rt.read(rt.LOCAL/'materials.json')
    sensor_groups = collections.defaultdict(list)
    for row in rows:
        if row.get('sensor_payload_sha256'):
            sensor_groups[row['sensor_payload_sha256']].append(row)
    duplicates, conflicts = [], []
    for digest, members in sensor_groups.items():
        paths = [r['path'] for r in members]
        units = {r['unit'] for r in members}
        for row in members:
            row['same_sensor_exposure_paths'] = paths
            row['sensor_identity_unit_conflict'] = len(units) != 1
        if len(paths) > 1:
            duplicates.append(dict(sha256=digest, paths=paths,
                full_file_hashes=len({r['sha256'] for r in members})))
        if len(units) != 1:
            conflicts.append(dict(sha256=digest, units=sorted(units), paths=paths))
    rt.dump(rt.LOCAL/'materials.json', rows)
    rt.dump(rt.LOCAL/'sensor_duplicate_groups.json', duplicates)
    rt.dump('sensor_identity_summary.json', dict(files=len(rows), unique_sensor_payloads=len(sensor_groups),
        duplicate_exposure_groups=len(duplicates), duplicate_files=sum(len(d['paths'])-1 for d in duplicates),
        metadata_changed_duplicate_groups=sum(d['full_file_hashes']>1 for d in duplicates),
        unit_conflicts=conflicts, errors=sum('sensor_payload_error' in r for r in rows),
        owner_rejected_payloads=len({r.get('sensor_payload_sha256') for r in rows if r['calibration_role']=='excluded_owner_rejected_capture'}),
        identity_definition='TIFF CFA geometry, bit depth, compression and concatenated raw strip payload; previews and EXIF omitted',
        source='verified original payload audit plus separately verified new39 payload audit',
        no_identity_promotion_from_shared_payload=True))
    summary = dict(created_utc=rt.utc(), files=len(rows),
        unique_raws=len({r['sha256'] for r in rows}),
        unique_sensor_payloads=len({r['sensor_payload_sha256'] for r in rows if r.get('sensor_payload_sha256')}),
        by_unit={}, labels_are_not_blind=True, unknown_wb_offsets_retained=True,
        additional_backups=2, new_39_pairs_included=True,
        no_unconfirmed_daily_photo_promoted=True)
    for unit in ('mount-a12', 'a12-50', 'a12-28', 'other'):
        ur = [r for r in rows if r['unit'] == unit]
        primary = [r for r in ur if r['calibration_role'] == 'primary_iso200']
        summary['by_unit'][unit] = dict(files=len(ur), unique_raws=len({r['sha256'] for r in ur}),
            paired_files=sum(bool(r['jpeg_pairs']) for r in ur),
            statuses=dict(collections.Counter(r['stock04_status'] for r in ur)),
            selectors=dict(collections.Counter(r.get('selector_name', 'unknown') for r in ur)),
            primary_iso200_frames=len(primary),
            primary_scene_groups=dict(collections.Counter(r['scene_group'] for r in primary)),
            primary_lights=sorted({r['light_group'] for r in primary}),
            high_iso_diagnostic_frames=sum(r['calibration_role'] == 'high_iso_diagnostic' for r in ur))
    rt.dump('materials_summary.json', summary)
    # All detailed capture identities stay local, including retained EXIF fields.
    fields = ('path', 'sha256', 'unit', 'when', 'iso', 'selector_name', 'recorded_sliders',
              'wb_mode', 'wb_user_offsets', 'orientation', 'paired_jpegs', 'jpeg_srgb',
              'stock04_status', 'calibration_role', 'date_group', 'light_group', 'scene_group',
              'identity_evidence', 'sensor_payload_sha256', 'lens', 'aperture',
              'lens_owner_description', 'lens_owner_focal_mm', 'lens_owner_max_aperture_f',
              'lens_owner_mount', 'lens_manual', 'capture_aperture_f_owner', 'capture_aperture_status',
              'lens_identity_source', 'lens_confirmation_date', 'exif_zero_aperture_interpretation')
    with (rt.LOCAL/'material_identity.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            row = {k: r.get(k) for k in fields}
            row.update(paired_jpegs=len(r['jpeg_pairs']),
                jpeg_srgb=bool(r['jpeg_pairs']) and all(j.get('color_space') == 1 for j in r['jpeg_pairs']))
            writer.writerow(row)
    return summary


def pairs():
    rows = rt.read(rt.LOCAL/'materials.json')
    keys = ('when', 'iso', 'exposure', 'orientation', 'selector', 'color_raw13', 'wb_mode', 'wb_exif')
    conflicts = []
    for row in rows:
        if row['unit'] == 'other':
            continue
        for pair in row['jpeg_pairs']:
            jpeg = pair.get('metadata', {})
            wrong = {key: (row.get(key), jpeg.get(key)) for key in keys if row.get(key) != jpeg.get(key)}
            if wrong:
                conflicts.append(dict(raw=row['path'], jpeg=pair['path'], calibration_role=row['calibration_role'], fields=wrong))
    rt.dump(rt.LOCAL/'pair_metadata_conflicts.json', conflicts)
    rt.dump('pair_metadata_summary.json', dict(
        checked_paths=sum(r['unit']!='other' and bool(r['jpeg_pairs']) for r in rows),
        fields=list(keys), conflict_pairs=len(conflicts),
        conflicts_by_field=dict(collections.Counter(k for row in conflicts for k in row['fields'])),
        conflicts_in_primary04=sum(row['calibration_role']=='primary_iso200' for row in conflicts),
        new39_conflicts=sum('gxr-20261102-cardB' in row['raw'] for row in conflicts)))
    assert not any(r['calibration_role']=='primary_iso200' or 'gxr-20261102-cardB' in r['raw'] for r in conflicts)


def prior():
    base = rt.ROOT/'research/look_ceiling_r1'
    source_names = ('REPORT.md', 'METHODS.md', 'results.json', 'error_modes.json', 'quality.csv')
    prior = rt.read(base/'results.json')
    rows = [r for r in prior['fits'] if r['primary']]
    assert len(rows) == prior['primary_fit_count'] == 1530
    by_layer = {}
    for level in range(5):
        selected = [r for r in rows if r['config']['level'] == level]
        gain = collections.defaultdict(list)
        for row in selected:
            for group, value in row['gain_over_parent_pp'].items():
                if isinstance(value, (int, float)):
                    gain[group].append(value)
        by_layer[f'L{level}'] = dict(fits=len(selected),
            gain_over_parent_median_pp={k: statistics.median(v) for k, v in gain.items()},
            any_overfit_flag=sum(any(r['overfit_flags'].values()) for r in selected),
            mount_overfit_vs_parent=sum(r['overfit_flags'].get('mount-a12', False) for r in selected),
            mount_overfit_vs_current=sum(r['overfit_vs_current_flags'].get('mount-a12', False) for r in selected),
            fits_with_added_reverse_hue_intervals=sum(r['added_reverse_hue_intervals'] > 0 for r in selected))
    bw = []
    for row in rows:
        if row.get('builtin_slot') == 3 and row['config']['key'] in ('L0', 'L1'):
            unit = row['unit']
            group = 'synthetic' if unit == 'a12-28' else unit
            bw.append(dict(unit=unit, level=row['config']['key'],
                similarity_percent=row['scores'][group]['similarity_percent'],
                score_group=group, path='native pure grayscale shortcut',
                deployable_under_S04_from_prior_alone=False))
    errors = rt.read(base/'error_modes.json')
    with (base/'quality.csv').open() as stream:
        quality = list(csv.DictReader(stream))
    summary = dict(created_utc=rt.utc(), sources={name: rt.sha(base/name) for name in source_names},
        total_fits=len(prior['fits']), primary_fits=len(rows), profiles=prior['target_profiles'],
        layers=by_layer, prior03=bw,
        native_bw_source_evidence=['METHODS.md:55', 'ceiling_model.py:230'],
        prior03_requires_separate_ordinary_Standard_record_replay=True,
        error_modes=dict(rows=len(errors), groups=dict(collections.Counter(r['group'] for r in errors)),
            layers=dict(collections.Counter(r['layer'] for r in errors)),
            subsets=dict(collections.Counter(r['subset'] for r in errors))),
        quality_csv=dict(rows=len(quality), columns=list(quality[0])),
        prior_and_new_scores_have_different_photo_population=True,
        no_software_3d_lut_path_evaluated=True)
    report_rows = {}
    for line in (base/'REPORT.md').read_text().splitlines():
        cells = [v.strip() for v in line.split('|')[1:-1]]
        if len(cells) == 8 and cells[0] in by_layer and cells[1].isdigit():
            report_rows[cells[0]] = dict(fits=int(cells[1]), added_reverse_fits=int(cells[3]),
                mount_overfit_vs_parent=int(cells[4]), mount_overfit_vs_current=int(cells[5]))
    summary['prior_report_quality_table'] = report_rows
    summary['prior_report_quality_table_matches_json'] = all(
        r['added_reverse_fits'] == by_layer[k]['fits_with_added_reverse_hue_intervals'] and
        r['mount_overfit_vs_parent'] == by_layer[k]['mount_overfit_vs_parent'] and
        r['mount_overfit_vs_current'] == by_layer[k]['mount_overfit_vs_current']
        for k, r in report_rows.items())
    summary['prior_discrepancy_policy'] = 'Retain both frozen sources; current task recomputes its own quality gates from saved record bytes.'
    rt.dump('prior_audit.json', summary)
    return summary


def targets():
    rows = []
    for index in range(35):
        meta = rt.read(rt.LOCAL/'targets/mount-a12'/f'{index:02d}.json')
        keys = ('index', 'name', 'kind', 'builtin_slot', 'source', 'source_sha256',
                'input', 'output', 'interpretation', 'shipped_in_g154_looks18', 'shipped_name',
                'current_row_scope', 'target_scope')
        rows.append({k: meta[k] for k in keys if k in meta})
    shipped = [r for r in rows if r['kind'] == 'look' and r['shipped_in_g154_looks18']]
    assert len(shipped) == 18 and len({r['shipped_name'] for r in shipped}) == 18
    rt.dump('target_catalog.json', dict(unique_target_definitions=35, builtins=8,
        looks=27, g154_looks18_matched=18, additional_targets=9,
        profiles_per_unit=35, main_profiles_total=105, definitions=rows,
        labels='电脑预测', identity='source function and exact published-row name mapping'))
    return shipped


if __name__ == '__main__':
    m, p, t = materials(), prior(), targets()
    pairs()
    print('Audited', m['files'], 'material paths,', p['primary_fits'], 'prior fits, and', len(t), 'shipped Looks')
