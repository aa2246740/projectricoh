"""Summarize current evidence without treating a successful rerun as a first success."""
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
HEAD = '652847c0ea570ba4bc1e5e635055e3a1543ec996'


def json_file(name):
    return json.loads((OUT/name).read_text())


def log_data(name):
    text = re.sub(r'\x1b\[[0-9;]*m', '', (OUT/name).read_text())
    records = []
    for line in text.splitlines():
        match = re.search(r'(tests/.*?) (PASSED|SKIPPED|FAILED|ERROR|RERUN)(?:\s|$)', line)
        if match:
            records.append({'node': match.group(1).strip(), 'status': match.group(2)})
    statuses = {r['node']: r['status'] for r in records}
    summaries = [line for line in text.splitlines() if re.search(r'\b\d+ passed\b', line)]
    result = {'file': name, 'sha256': hashlib.sha256((OUT/name).read_bytes()).hexdigest(),
              'summaries': summaries, 'individual_tests': len(statuses),
              'status_counts': {s: list(statuses.values()).count(s) for s in ['PASSED', 'SKIPPED', 'FAILED', 'ERROR', 'RERUN']},
              'new_dat_tests': {n: s for n, s in statuses.items() if n.startswith('tests/test_dat_card_identity.py::')},
              'gpu_tests': {n: s for n, s in statuses.items() if n.startswith('tests/test_gpu_parity.py::')},
              'test_status_records': records}
    assert all(s in ('PASSED', 'SKIPPED') for s in statuses.values())
    return result


first = {j['name']: j for j in json_file('debug-jobs-attempt1.json')['jobs']}
second = {j['name']: j for j in json_file('debug-jobs-attempt2.json')['jobs']}
attempts = []
for name, job in first.items():
    repeated = second[name]
    attempts.append({'name': name, 'attempt1_id': job['id'], 'attempt2_id': repeated['id'],
                     'first_conclusion': job['conclusion'], 'second_conclusion': repeated['conclusion'],
                     'first_started_at': job['started_at'], 'second_started_at': repeated['started_at'],
                     'first_completed_at': job['completed_at'], 'second_completed_at': repeated['completed_at'],
                     'execution_times_reused': (job['started_at'], job['completed_at']) == (repeated['started_at'], repeated['completed_at'])})
assert [r['name'] for r in attempts if not r['execution_times_reused']] == ['windows-probes']
assert first['windows-probes']['conclusion'] == 'failure' and second['windows-probes']['conclusion'] == 'success'
timeout = {'head': json_file('debug-run-metadata.json')['head_sha'], 'attempts': attempts,
           'first_failure_log': 'debug-windows-probes-first.log', 'final_probe_log': 'debug-windows-probes-final.log',
           'confirmed_first_result': 'No page completion at 30 seconds, followed by Windows file-use error 32 during temporary directory cleanup.',
           'first_timeout_cause': 'Not established by the available first-run log.',
           'log_file_holder_pid': 'Not recorded; the first log does not identify the process holding chrome.log.',
           'helper': 'tests/gpu_support.py:115-165', 'probe_limit_seconds': 30, 'regular_test_limit_seconds': 180,
           'confirmed_helper_gap': 'Only the initially launched process is terminated and waited for. The first Windows log shows a held log file after that path returned.',
           'merge_severity': 'P2', 'regular_windows_first_attempt': log_data('debug-windows-full-first.log')}
assert timeout['head'] == HEAD
(OUT/'windows-timeout-analysis.json').write_text(json.dumps(timeout, indent=2)+'\n')

receipts = [json.loads(p.read_text()) for p in sorted((OUT/'cases').glob('*/receipt.json')) if p.parent.name != 'targeted-tests']
assert len(receipts) == 27 and all(r['error'] is None and r['nice'] == 10 and r['head'] == HEAD for r in receipts)
historical = []
for name in ['r2-colour', 'r4-colour']:
    path = OUT/'cases'/name/'synthetic-lut-counterexample-swiftshader.json'
    colour = json.loads(path.read_text())
    assert all(row['max_code'] == 0 and row['mean'] == 0 and row['advertised_gate_pass'] for row in colour['rows'])
    historical.append({'case': name, 'result': str(path.relative_to(OUT)), 'passed': True})
browser = [json.loads(p.read_text()) for p in sorted((OUT/'cases').glob('*/browser-receipt.json'))]
assert len(browser) == 3 and all(r['browserClosed'] and r['nice'] == 10 and not r['pageErrors'] for r in browser)
dat = json_file('cases/independent-dat/dat-identity.json')
assert dat['count'] == 49 and all(r['passed'] for r in dat['cases'])
targeted = json_file('cases/targeted-tests/receipt.json')
assert targeted['exit'] == 0 and targeted['reruns'] == 0
summary = {'head': HEAD, 'historical_replays': receipts+historical, 'historical_passed': len(receipts)+len(historical),
           'legacy_interface_observation': json_file('cases/r3-original-interface/legacy-interface.json'),
           'independent_dat_cases': dat['count'], 'current_gpu_checks': json_file('cases/current-colour/colour-results.json')['passed'],
           'targeted': targeted, 'browser_sessions_closed': len(browser)}
assert summary['current_gpu_checks'] == 14
(OUT/'verification-summary.json').write_text(json.dumps(summary, indent=2)+'\n')

if (OUT/'pr-run-final.json').exists():
    run = json_file('pr-run-final.json')
    assert run['head_sha'] == HEAD and run['event'] == 'pull_request' and run['conclusion'] == 'success' and run['run_attempt'] == 1
    jobs = json_file('pr-jobs-final.json')['jobs']
    wanted = ['tests (windows-latest)', 'tests (macos-latest)', 'check']
    assert all(next(j for j in jobs if j['name'] == name)['conclusion'] == 'success' for name in wanted)
    windows, mac, linux = log_data('pr-windows.log'), log_data('pr-macos.log'), log_data('pr-linux.log')
    for item in [windows, mac]:
        assert item['individual_tests'] == 1739
        assert len(item['new_dat_tests']) == 8 and set(item['new_dat_tests'].values()) == {'PASSED'}
        assert len(item['gpu_tests']) == 14 and set(item['gpu_tests'].values()) == {'PASSED'}
    assert windows['status_counts']['PASSED'] == 1036 and windows['status_counts']['SKIPPED'] == 703
    assert mac['status_counts']['PASSED'] == 1033 and mac['status_counts']['SKIPPED'] == 706
    assert any('1029 passed, 710 skipped' in line for line in linux['summaries'])
    result = {'head': HEAD, 'run': run['html_url'], 'attempt': run['run_attempt'],
              'jobs': [{k:j[k] for k in ['id','name','conclusion','started_at','completed_at']} for j in jobs],
              'windows': windows, 'macos': mac, 'linux': linux}
    push = json_file('push-run-final.json')
    assert push['head_sha'] == HEAD and push['event'] == 'push' and push['conclusion'] == 'success' and push['run_attempt'] == 1
    pushed_windows = log_data('push-windows.log')
    assert pushed_windows['individual_tests'] == 1739
    assert pushed_windows['status_counts']['PASSED'] == 1036 and pushed_windows['status_counts']['SKIPPED'] == 703
    result['push'] = {'run': push['html_url'], 'attempt': push['run_attempt'], 'conclusion': push['conclusion'], 'windows': pushed_windows}
    (OUT/'ci-verification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({'historical_replays_passed': summary['historical_passed'], 'independent_dat_cases': dat['count'], 'current_gpu_checks': summary['current_gpu_checks'], 'browser_sessions_closed': len(browser), 'formal_pr_verified': (OUT/'ci-verification.json').exists()}))
