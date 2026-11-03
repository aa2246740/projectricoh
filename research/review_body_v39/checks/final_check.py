#!/usr/bin/python3 -I
"""Validate the retained result objects after both foreground slots finish."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_body_v39/evidence'


def read(name):
    return json.loads((OUT / name).read_text())


summary = read('regression-summary.json')
assert summary['pass'] == 18 and not summary['fail'] and not summary['pending']
host = [json.loads(line) for line in (OUT / 'host.jsonl').read_text().splitlines()]
assert len(host) == 51 and host[0]['combinations'] == 128
replay = read('replay.json')
assert len(replay['cases']) == 36
models = []
for tag, unit in (('body50-final', '50mm'), ('body28', '28mm'), ('bodymount', 'mount')):
    value = read(f'{tag}/evidence/dat-body-{unit}.json')
    assert value['body_sha256'] == 'c0f8065d58e78fda09ad13580c941647a4a20d1e3225e302dbed0b05251d6f3f'
    assert value['dat_sha256'] == 'ef349e709ab14f93238a4db154c24efdeb4a0f9f209e9a6cefacbe44e6b44fe5'
    assert value['grain_matrix']['cases'] == value['grain_matrix']['identical'] == 379
    assert value['grain_commit']['cases'] == value['grain_commit']['identical'] == 144
    assert not value['grain_matrix']['differences'] and not value['grain_commit']['differences']
    assert len(value['h40']) == 10 and value['root_state'] == 3
    models.append({'unit': unit, 'grain_cases': 379, 'commit_cases': 144, 'image_cases': 10})
card = read('card-state.json')
assert card['status'] == 'PASS' and len(card['cases']) == 9
assert all(case['dat_calls_after_disabled'] == 0 and case['rows'] == 7 for case in card['cases'])
cold = read('emu-diff.json')
assert all(cold['observations_equal'].values())
assert cold['observation_counts'] == {'official': 60, 'v38': 60, 'v39': 60}
assert len(cold['phases']) == 27 and cold['root_page_v39'][:488] == 'ff' * 244
assert all(len(set(phase['state'].values())) == 1 for phase in cold['phases'])
tags = ['replay', 'cold', 'body50-final', 'body28', 'bodymount', 'cardstate']
tags += ['route-' + name for name in ('release', 'ctl', 'ctl-bad', 'no-card', 'old-dat')]
batch = {}
for tag in tags:
    states = read(tag + '-batch.json')
    assert states and all(value['batch'] and value['mode'] == 'fast' for value in states)
    assert any(value['batch_stats'].get('batch-steps', 0) > 0 for value in states)
    batch[tag] = len(states)
manifests = read('package-manifests.json')
assert sum(row['count'] for row in manifests) == 89 and all(row['status'] == 'PASS' for row in manifests)
assert read('build.json')['elf_bytes_equal']
assert [row['link_ok'] for row in read('margins.json')] == [True, False, False]
assert read('identity-check.json')['status'] == 'PASS'
port = read('port.json')
assert port == read('port2.json') and port['status'] == 'PASS'
assert port['g150_settings_op6_retained'] and port['op6_does_not_clear_grain']
port_records = read('port-files.json')
assert len(port_records) == 6
for row in port_records:
    assert hashlib.sha256((ROOT / row['retained']).read_bytes()).hexdigest() == row['sha256']
expected_failures = {'extra124exit50', 'extra124exit50r2', 'oldprobe148',
                     'extra-group124-50mm-view-reentry', 'port'}
receipts = [json.loads(path.read_text()) for path in OUT.glob('*-receipt.json')]
actual_failures = {row['name'] for row in receipts if row['returncode'] != 0}
assert actual_failures == expected_failures, actual_failures
for row in receipts:
    assert row['status'] == 'finished' and row['nice'] == 10
    assert hashlib.sha256((ROOT / row['log']).read_bytes()).hexdigest() == row['log_sha256']
result = {'status': 'PASS', 'regression_groups': 18, 'host_lines': 51, 'replay_cases': 36,
          'models': models, 'card_cases': 9, 'cold_phases': 27, 'cold_observations_per_image': 60,
          'batch_state_counts': batch, 'package_manifest_entries': 89,
          'port_retained_files': len(port_records),
          'workload_receipts': len(receipts), 'preserved_tool_failures': sorted(actual_failures)}
(OUT / 'final-evidence.json').write_text(json.dumps(result, indent=1) + '\n')
print(json.dumps(result))
