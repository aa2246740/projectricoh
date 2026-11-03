"""Replay saved record bytes and independently check the Standard colour path."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import hashlib
import json
import subprocess
import tarfile
import csv
import signal
import fit_one
from capabilities import main_level
from entry_codec import encode, predict, record_checks, look_identity_valid
from report import select


def main():
    receipts = []
    code_snapshots = {}
    fit_paths = list((rt.LOCAL/'fits').rglob('*.json'))
    control = rt.LOCAL/'controls/affine_a12_50'
    fit_paths += list((control/'fits').rglob('*.json'))
    main_candidates = {}
    for path in fit_paths:
        if path.is_relative_to(control):
            continue
        doc = rt.read(path)
        if doc['level'] != main_level(doc['unit']) or not doc['quality']['passes']:
            continue
        key = doc['unit'], doc['index']
        main_candidates.setdefault(key, []).append(path)
    # Match the registry's training selection, including an exactly equivalent
    # shared-curve encoding, so photo evidence binds to the final record SHA.
    selected_paths = {str(select(paths)[0]) for paths in main_candidates.values()}
    photo_rows = []
    photo_info = {}
    main_profiles = set()
    for path in sorted(fit_paths):
        doc = rt.read(path)
        for snapshot in (doc.get('code_snapshot'),doc.get('postprocess_code_snapshot')):
            if snapshot and snapshot['folder'] not in code_snapshots:
                directory = rt.HERE/snapshot['folder']
                identity = hashlib.sha256(json.dumps(snapshot['files'], sort_keys=True).encode()).hexdigest()
                assert identity == snapshot['identity']
                assert all(rt.sha(directory/name)==digest for name,digest in snapshot['files'].items())
                code_snapshots[snapshot['folder']] = identity
        assert not (doc.get('mount_probe_pending') and doc.get('recommend_next_dat_build'))
        unit, index, ui = doc['unit'], doc['index'], ('a12-50', 'a12-28', 'mount-a12').index(doc['unit'])
        archived = path.is_relative_to(control)
        target = control/'targets' if archived else rt.LOCAL/'targets'/unit
        meta = rt.read(target/f'{index:02d}.json')
        assert rt.sha(target/f'{index:02d}.json') == doc['target_sha256']
        record_path = path.with_suffix('.record552')
        entry = record_path.read_bytes()
        checks = record_checks(entry)
        assert checks['sha256'] == doc['record']['sha256']
        assert checks['row_crcs_valid'] and checks['existing_row_domain_checks_pass']
        if doc.get('look_unit_mask'):
            assert look_identity_valid(entry, doc['look_unit_mask'])
        if doc.get('mirror_iso100_curve'):
            assert entry[456:518] == entry[20:82] and entry[518:551] == entry[82:115]
        template = bytes.fromhex(meta['template_hex'])
        assert len(entry) == len(template) == 552
        if doc.get('parameters'):
            rebuilt = encode(template, doc['parameters'], level=doc.get('record_encoding_level',doc['level']), gray=doc.get('gray', False),
                             mirror_iso100=doc.get('mirror_iso100_curve', False), look_unit_mask=doc.get('look_unit_mask'))
            assert rebuilt == entry, 'Full 552-byte serialization mismatch'
        else:
            assert entry == template
        s = rt.release_dat().modules[ui].records[entry[0]-1]
        standard = rt.release_dat().modules[ui].records[3]
        assert s[3] == standard[3] == 1 and s[36:51] == standard[36:51]
        max_model_difference, saved_point_count, gray_difference = 0., 0, 0.
        for group, oldscore in doc['scores'].items():
            if oldscore is None:
                continue
            values = rt.arrays(target/f'{index:02d}_{group}.npz')
            output = predict(entry, values['x'], ui)
            assert np.array_equal(predict(template, values['x'], ui), values['current'])
            stock = rt.release_dat().entry_of(ui, 4)
            assert np.array_equal(predict(stock, values['x'], ui, round_output=False), values['base'])
            saved = rt.arrays(path.parent/(path.stem+'_'+group+'.npz'))['prediction']
            assert np.array_equal(output, saved), 'Saved integer prediction differs from record replay'
            # Setting byte 0 to an ordinary colour slot removes the archived
            # Model's special slot-03 branch. No DAT or modified record is saved.
            ordinary_slot = bytearray(entry)
            ordinary_slot[0] = 1
            independent = rt.camera_model(ui).predict(bytes(ordinary_slot), values['x'])
            ours = predict(entry, values['x'], ui, round_output=False)
            difference = float(abs(independent-ours).max())
            assert difference < 1e-7
            max_model_difference = max(max_model_difference, difference)
            rescore = rt.score(values['base'], output, values['want'])
            for field in ('median', 'p95', 'max', 'mean'):
                assert abs(rescore['de00'][field]-oldscore['candidate']['de00'][field]) < 1e-11
            if rescore['similarity_percent'] is not None:
                assert abs(rescore['similarity_percent']-oldscore['candidate']['similarity_percent']) < 1e-10
            if doc.get('gray'):
                row = rt.mm.MatrixRow.from_bytes(entry[216:244])
                assert not row.coef[1:].any()
                y = row.apply(rt.camera_model(ui).pre(entry, values['x']))[0]
                native_reference = np.clip(np.repeat(y[:, None], 3, axis=1), 0, 255)
                gray_difference = max(gray_difference, float(abs(native_reference-ours).max()))
                assert gray_difference < 1e-7 and np.ptp(ours, axis=1).max() < 1e-7
            if str(path) in selected_paths and group.startswith('photo_'):
                from photo_evidence import rows
                if unit not in photo_info:
                    photo_info[unit] = rt.read(rt.LOCAL/'inputs'/unit/'photos.json')
                photo_rows.extend(rows(doc, group, values, output, photo_info[unit]))
            saved_point_count += len(output)
        camera = rt.Camera(ui)
        gradients, rings = fit_one.quality.fixtures(camera)
        q = fit_one.guard(camera, entry, template, gradients, rings, ui, doc.get('gray', False))
        assert q['new_reverse_hue_intervals'] == doc['quality']['new_reverse_hue_intervals'] == 0
        assert abs(q['max_integer_gradient_step_de00']-doc['quality']['max_integer_gradient_step_de00']) < 1e-10
        receipts.append(dict(file=str(path.relative_to(rt.HERE)), name=doc['name'], unit=unit,
            affine_control=archived,
            points_replayed=saved_point_count, all_552_bytes_rebuilt=True, row_crcs=checks['row_crc_count'],
            record_sha256=checks['sha256'], archived_ordinary_colour_path_max_code_difference=max_model_difference,
            abstract_native_bw_reference_max_code_difference=gray_difference if doc.get('gray') else None,
            S_mode_and_parameter_bytes_match_04=True, no_native_bw_selector=True,
            scores_recomputed=True, fixed_quality_fixtures_recomputed=True))
        if not archived and doc['level'] == main_level(unit):
            main_profiles.add((unit, index))
    frozen = rt.read(rt.LOCAL/'input_freeze.json')
    changed = [name for name, expected in frozen['inputs'].items() if rt.sha(rt.ROOT/name) != expected]
    assert not changed, changed
    files = sorted(p for p in rt.LOCAL.rglob('*') if p.is_file())
    relative = [str(p.relative_to(rt.ROOT)) for p in files]
    proc = subprocess.run(['git', '-C', str(rt.ROOT), 'check-ignore', '-v', '--stdin'],
        input='\n'.join(relative)+'\n', text=True, capture_output=True, check=True)
    ignored = {line.split('\t', 1)[1] for line in proc.stdout.splitlines()}
    assert set(relative) <= ignored, 'Derived file escaped Git ignore'
    rt.dump(rt.LOCAL/'ignore_receipt.json', dict(command='git check-ignore -v --stdin',
        checked=len(relative), ignored=len(ignored), output=proc.stdout, stderr=proc.stderr))
    inputs = []
    fast_authorization = rt.read(rt.LOCAL/'fast_switch_authorization.json') if (rt.LOCAL/'fast_switch_authorization.json').exists() else None
    fast_live_drift = []
    for p in rt.SOURCE.rglob('*'):
        if not p.is_file() or 'studio_snapshot' in p.relative_to(rt.SOURCE).parts or p.name == 'studio_source_snapshot.tar.gz':
            continue
        original = rt.ROOT/p.relative_to(rt.SOURCE)
        relative = p.relative_to(rt.SOURCE)
        if relative.parts[:2] == ('tools', 'fit_fast'):
            # The parallel engine task may start a new round. Verify this
            # study's delivered frozen bytes, never silently refresh them.
            name = str(Path(*relative.parts[2:]))
            assert fast_authorization and rt.sha(p)==fast_authorization['source_files'][name]
            if not original.is_file() or rt.sha(original)!=rt.sha(p):
                fast_live_drift.append(str(relative))
        else:
            assert original.is_file() and rt.sha(p) == rt.sha(original)
        inputs.append(dict(path=str(original.relative_to(rt.ROOT)), sha256=rt.sha(p)))
    snapshot = rt.SOURCE/'studio_snapshot'
    snapshot_files = []
    with tarfile.open(rt.SOURCE/'studio_source_snapshot.tar.gz', 'r:gz') as archive:
        for member in archive.getmembers():
            assert member.isfile()
            destination = (snapshot/member.name).resolve()
            assert destination.is_relative_to(snapshot)
            with archive.extractfile(member) as stream:
                expected = hashlib.sha256(stream.read()).hexdigest()
            assert rt.sha(destination) == expected, 'Extracted historical source differs from archive'
            snapshot_files.append(member.name)
    assert len(snapshot_files) == len(set(snapshot_files))
    assert set(snapshot_files) == {str(p.relative_to(snapshot)) for p in snapshot.rglob('*') if p.is_file()}
    if photo_rows:
        with (rt.HERE/'photo_scores.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(photo_rows[0]))
            writer.writeheader()
            writer.writerows(photo_rows)
    rt.dump(rt.LOCAL/'source_verification.json', inputs)
    summary = dict(status='PASS', completed_record_fits=len(receipts), records=receipts,
        frozen_upstream_files_unchanged=len(frozen['inputs']), copied_source_inputs_verified=len(inputs),
        archived_snapshot_files_verified=len(snapshot_files),
        task_code_snapshots_verified=len(code_snapshots),
        selected_main_photo_scores=len(photo_rows),
        photo_scores_sha256=rt.sha(rt.HERE/'photo_scores.csv') if photo_rows else None,
        frozen_fast_engine_verified=fast_authorization is not None,
        live_fast_engine_drift_does_not_change_frozen_inputs=fast_live_drift,
        ignored_derived_files=len(files), numerical_process_budget=rt.COMPUTE_BUDGET,
        compute_slot=rt.COMPUTE_SLOT, nice=__import__('os').getpriority(__import__('os').PRIO_PROCESS, 0),
        no_camera_no_card_no_dat_build=True, artifact_scope='saved 552-byte records and computer predictions only',
        completed_main_profiles=len(main_profiles),
        full_recipe_matrix_complete=all((unit, index) in main_profiles
            for unit in ('a12-50', 'a12-28', 'mount-a12') for index in range(35)), created_utc=rt.utc())
    rt.dump('verification.json', summary)
    print('PASS', len(receipts), 'records,', sum(r['points_replayed'] for r in receipts), 'prediction points,', len(files), 'ignored local files')


if __name__ == '__main__':
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Record replay exceeded 25 minutes; split verification')))
    signal.alarm(1500)
    main()
