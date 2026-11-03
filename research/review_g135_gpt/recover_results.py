from pathlib import Path
import ast
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'
STATE = OUT / 'evidence/scheduler.json'
state = json.loads(STATE.read_text())
deadline = datetime.datetime.fromisoformat('2026-10-30T02:54:12+00:00')
now = datetime.datetime.now(datetime.timezone.utc)
assert now > deadline
events = [json.loads(line) for line in (OUT / 'evidence/runs.jsonl').read_text().splitlines()]
starts = {row['name']: row for row in events if row['event'] == 'start'}
names = ['group124-28mm-values', 'group124-mount-values', 'group126-28mm-values']
groups = {str(starts[name]['pid']) for name in names}
groups.add(str(state['pid']))
process_state = json.loads((OUT / 'evidence/process-state.json').read_text())
assert set(process_state['groups']) == groups
live = process_state['present']
assert not live, live

old_path = ROOT / 'research/review_g135/legacy/ui_acceptance_g135.py'
tree = ast.parse(old_path.read_bytes(), filename=str(old_path))
checks = [node for node in ast.walk(tree) if isinstance(node, ast.Assert) and node.lineno == 164]
assert len(checks) == 1
condition = checks[0].test
assert isinstance(condition, ast.BoolOp) and isinstance(condition.op, ast.And)
comparisons = condition.values
assert len(comparisons) == 2 and all(isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.Eq) for node in comparisons)
assert [ast.literal_eval(node.comparators[0]) for node in comparisons] == [1, 1]
assert [ast.literal_eval(node.left.slice) for node in comparisons] == ['screen', 'cur']

recovered = {}
expected_cases = ['all-values-0', 'all-values-1', 'all-values-2', 'all-values-3', 'L1-virtual-scroll', 'default-double-DISP', 'back-from-second-pair']
for name in names:
    folder = OUT / 'local/jobs' / name
    unit = 'mount' if '-mount-' in name else '28mm'
    assert not (folder / 'execution.json').exists()
    files = []
    for case in expected_cases:
        matches = list(folder.rglob(unit + '-' + case + '.json'))
        assert len(matches) == 1
        path = matches[0]
        data = json.loads(path.read_text())
        assert data['dat_sha256'] == '57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a'
        assert data['full_committed_settings_checked']
        assert not any(data['file_mutations'].values())
        assert data['native_UI']['host_ui_writes'] == 0 and not data['native_UI']['bad']
        if case != 'back-from-second-pair':
            assert data['status'] == 'PASS'
        else:
            assert data['status'] == 'FAIL' and ':164:back_pair' in data['error']
            event = data['events'][-1]
            after = event['after']
            assert event['key'] == 'DISP' and event['result']['ok'] and event['result']['steps'] > 0
            assert [after['screen'], after['cur']] == [1, 2] and after['failed'] == 0
        files.append(path)
    errors = list(folder.rglob('error-ui_acceptance_g135-values---unit-' + unit + '.json'))
    assert len(errors) == 1
    cases = ast.literal_eval(json.loads(errors[0].read_text())['message'])
    assert cases == [{'case': case, 'wait_status': 256 if case == 'back-from-second-pair' else 0} for case in expected_cases]
    console = folder / 'console.log'
    reported = json.loads(console.read_text().splitlines()[-1])
    assert reported['returncode'] == 1
    files.extend([errors[0], console])
    last = max(path.stat().st_mtime for path in files)
    stamp = datetime.datetime.fromtimestamp(last, datetime.timezone.utc)
    assert stamp < deadline
    started = datetime.datetime.fromisoformat(starts[name]['utc'])
    recovered[name] = {
        'name': name,
        'execution': 'RECOVERED_REPORT',
        'returncode': None,
        'reported_returncode': 1,
        'seconds': round((stamp - started).total_seconds(), 3),
        'duration_basis': 'last result file timestamp minus recorded start',
        'utc': stamp.isoformat(),
        'cases': cases,
        'actual_cursor': [1, 2],
        'legacy_expected_cursor': [1, 1],
        'legacy_assertion_line': 164,
        'sources': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
        'receipt_missing': True,
    }

(OUT / 'evidence/recovered-groups.json').write_text(json.dumps(recovered, ensure_ascii=False, indent=2) + '\n')
saved = OUT / 'local/scheduler-last-live.json'
if not saved.exists():
    saved.write_bytes(STATE.read_bytes())
state.update({'active': [], 'last_live_utc': state['utc'], 'utc': now.isoformat(), 'status': 'INTERRUPTED_TIMEBOX', 'recovered_reports': names, 'processes_present_at_finalization': live})
STATE.write_text(json.dumps(state, indent=2) + '\n')
(OUT / 'evidence/interruption.json').write_text(json.dumps({'observed_utc': now.isoformat(), 'deadline_utc': deadline.isoformat(), 'scheduler_process_present': False, 'worker_processes_present': live, 'new_groups_started_after_interruption': False, 'recovered_reports': names, 'os_exit_receipts_available': False}, indent=2) + '\n')
print(json.dumps({'recovered_reports': len(recovered), 'processes_present': len(live), 'os_exit_receipts_available': False}))
