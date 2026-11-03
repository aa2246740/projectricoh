#!/usr/bin/python3
"""Check the resumed queue and bind every accepted row to the final files."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g131_merge'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def journal(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def main():
    start = json.loads((WORK / 'evidence/resume-start.json').read_text())
    pin = sha(ROOT / 'firmware/package_v36_g131/local/SD_ROOT/GXRCE.DAT')
    assert pin == start['dat_sha256']
    assert all(sha(ROOT / name) == digest for name, digest in start['source_sha256'].items())
    queue = json.loads((WORK / 'queue.json').read_text())
    assert len(queue) == 38
    root_rows = journal(WORK / 'evidence/runs.jsonl')
    local_rows = []
    for path in sorted((WORK / 'local/checks').glob('*/runs.jsonl')):
        local_rows.extend(journal(path))
    latest = {row['name']: row for row in root_rows + local_rows}
    resumed = local_rows[start['prior_local_run_rows']:]
    resumed_names = {row['name'] for row in resumed}
    stages = journal(WORK / 'evidence/stage-runs.jsonl')
    offset = start['prior_stage_rows']
    selected_stages = {5: stages[:5], 19: stages[offset:offset + 1],
                       23: stages[offset + 1:offset + 4]}
    expected_stages = {5: ['target_gate', 'host_check', 'layout', 'layout_bindings', 'check_delta'],
                       19: ['target_gate'], 23: ['target_check-0', 'target_check-1', 'target_check-2']}
    reference = json.loads((WORK / 'evidence/reference-v2.json').read_text())
    assert reference['status'] == 'PASS' and reference['dat_sha256'] == pin and reference['cases'] == 3430
    assert reference['reference_source_sha256'] == sha(WORK / 'reference_v2.py')
    assert reference['library_sha256'] == sha(WORK / 'local/host/engine.dylib')
    rows = []
    revisions = json.loads((WORK / 'evidence/runner-revisions.json').read_text())['revisions']
    assert all(sha(ROOT / row['source']) == row['sha256'] for row in revisions)
    runner_pins = {}
    for row in revisions:
        for index in row['indices']:
            runner_pins.setdefault(index, set()).add(row['sha256'])
    for index, job in enumerate(queue):
        if job.get('standalone'):
            batch = selected_stages[index]
            assert [row['name'] for row in batch] == expected_stages[index], (index, 'stage-coverage')
            assert all(row['returncode'] == 0 for row in batch), (index, 'stage-result')
            row = dict(index=index, name=job['name'], returncode=0,
                       seconds=round(sum(item['seconds'] for item in batch), 3),
                       source='research/g131_merge/evidence/stage-runs.jsonl',
                       stage_names=expected_stages[index])
        else:
            assert job['name'] in latest, (index, 'missing-row')
            entry = latest[job['name']]
            assert entry['dat_sha256'] == pin
            expected = 1 if job.get('record_only') else 0
            assert entry['returncode'] == expected, (index, entry['returncode'])
            actual = json.loads((ROOT / entry['result']).read_text())
            assert actual['dat_sha256'] == pin and actual['returncode'] == expected
            if index >= 19:
                assert job['name'] in resumed_names, (index, 'missing-resumed-row')
                assert actual['runner_sha256'] in runner_pins[index]
                assert actual['seconds'] == entry['seconds']
                if job.get('postcheck'):
                    assert actual['postcheck_returncode'] == 0
                if 30 <= index <= 32:
                    metadata = json.loads((ROOT / entry['result']).with_name('binding-' + actual['name'] + '.json').read_text())
                    linked = [item for item in metadata['bindings'] if item.get('kind') == 'knobs-v2-reference']
                    assert linked and all(item['dat_sha256'] == pin and
                        item['reference_source_sha256'] == reference['reference_source_sha256'] and
                        item['reference_library_sha256'] == reference['library_sha256'] for item in linked)
            row = dict(index=index, name=job['name'], returncode=entry['returncode'],
                       seconds=entry['seconds'], source=entry['result'])
        row.update(dat_sha256=pin, origin='resumed' if index >= 19 else 'retained',
                   timeout_seconds=job['timeout_seconds'],
                   status='OPEN_P2_03' if job.get('record_only') else 'PASS')
        rows.append(row)
    assert len(resumed_names) == 17
    assert sum(row['status'] == 'OPEN_P2_03' for row in rows) == 7
    host = json.loads((WORK / 'host-results.json').read_text())
    assert host['status'] == 'PASS' and host['dat_sha256'] == pin
    assert host['plans'] == host['integrated_points'] == 3430
    assert host['points_per_unit'] == [1133, 1134, 1163]
    for index, unit in enumerate(('50mm', '28mm', 'mount')):
        target = json.loads((WORK / ('target-' + str(index) + '.json')).read_text())
        assert target['status'] == 'PASS' and target['dat_sha256'] == pin
        assert target['cases'] == host['points_per_unit'][index]
        restored = json.loads((WORK / 'local/checks/review_g126' / ('h01-restore-' + unit + '.json')).read_text())
        assert restored['status'] == 'PASS' and restored['dat_sha256'] == pin
        assert restored['before'] == restored['reopened'] == dict(mode=1, wb=[9, 9])
    codegen = json.loads((WORK / 'evidence/codegen-four-categories.json').read_text())
    assert codegen['status'] == 'PASS_STATIC' and codegen['dat_sha256'] == pin
    assert len(codegen['reviews']) == 12 and codegen['dat_engine_elf_equal']
    assert codegen['elf_sha256'] == sha(ROOT / 'firmware/engine_v51_g131/candidate/local/full-r13/engine.elf')
    rpc = json.loads((WORK / 'evidence/rpc-summary.json').read_text())
    assert rpc['status'] == 'PASS' and rpc['dat_sha256'] == pin and rpc['complete_records'] > 0
    local_files = []
    binary_suffixes = {'.bin', '.dat', '.elf', '.o', '.a', '.dylib', '.entry'}
    for base in (ROOT / 'firmware/engine_v51_g131', ROOT / 'firmware/package_v36_g131', WORK):
        for path in base.rglob('*'):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(base)
            if path.suffix.casefold() in binary_suffixes:
                assert 'local' in relative.parts, 'binary-location'
            if 'local' in relative.parts:
                local_files.append(str(path.relative_to(ROOT)))
    checked = subprocess.run(['/usr/bin/git', '--no-optional-locks', 'check-ignore', '--stdin'],
                             input='\n'.join(local_files) + '\n', capture_output=True, text=True)
    assert checked.returncode == 0 and set(checked.stdout.splitlines()) == set(local_files)
    result = dict(status='PASS', dat_sha256=pin, queue_items=len(rows),
                  retained_items=19, resumed_items=19, resumed_regular_items=len(resumed_names),
                  passing_items=31, inherited_open_items=7, source_files_unchanged=len(start['source_sha256']),
                  cold_reentry_50mm='RERUN_COMPLETE', ignored_local_files=len(local_files), rows=rows)
    (WORK / 'evidence/queue-complete.json').write_text(json.dumps(result, indent=2) + '\n')
    for row in rows:
        if row['index'] not in (5, 19, 23):
            continue
        entry = dict(name=row['name'], returncode=0, seconds=row['seconds'],
                     dat_sha256=pin, timeout_seconds=row['timeout_seconds'],
                     result='research/g131_merge/evidence/queue-complete.json',
                     stages=row['stage_names'])
        if entry not in root_rows:
            with (WORK / 'evidence/runs.jsonl').open('a') as stream:
                stream.write(json.dumps(entry) + '\n')
    print(json.dumps(dict(name='resume-review', returncode=0, counts=dict(
        queue_items=len(rows), resumed_items=19, passing_items=31, inherited_open_items=7))))
    return result

if __name__ == '__main__':
    main()
