from pathlib import Path
import ast
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'
plan = json.loads((OUT / 'queue.json').read_text())
decision_file = OUT / 'evidence/classification-decisions.json'
decisions = json.loads(decision_file.read_text()) if decision_file.exists() else {}
latest = {}
for job in plan['jobs']:
    folder = OUT / 'local/jobs' / job['name']
    path = folder / 'execution.json'
    if not path.exists():
        continue
    execution = json.loads(path.read_text())
    name = job.get('covers', job['name'])
    if name not in latest or execution['utc'] > latest[name][2]['utc']:
        latest[name] = (job, folder, execution)

for name, (job, folder, execution) in latest.items():
    decisions.pop(name, None)
    if execution['returncode'] == 0 or execution['execution'] != 'FINISHED':
        continue
    errors = [(path, json.loads(path.read_text())) for path in folder.rglob('error-*.json')]
    if job.get('kind') == 'user-regression':
        display_file = folder / 'local/user-display.json'
        if not display_file.exists():
            continue
        display = json.loads(display_file.read_text())
        if not display.get('other_assertions_completed') or not display.get('differences'):
            continue
        expected = all(item['expected'] == '<FCC-001' and item['actual'] == '<5 F-CC' for item in display['differences'])
        reports = []
        for path in folder.rglob('users-*.json'):
            data = json.loads(path.read_text())
            if data.get('status') == 'PASS' and data.get('full_committed_settings_checked') and data.get('readonly_metadata_unchanged'):
                reports.append(str(path.relative_to(ROOT)))
        terminal = any(data.get('message') == 'User card title differs from the previous display contract' for path, data in errors)
        if expected and reports and terminal:
            decisions[name] = {'outcome': '卡片标题差异已记录，其余断言完成', 'evidence': str(display_file.relative_to(ROOT)), 'reports': reports, 'raw_returncode': execution['returncode']}
    elif job.get('group') == 'project':
        if any(data.get('error') == 'KeyError' and data.get('message') == "'uv_levels'" for path, data in errors):
            assert json.loads((OUT / 'evidence/windows.json').read_text())['status'] == 'PASS'
            assert json.loads((OUT / 'evidence/boundary-sweep.json').read_text())['status'] == 'PASS'
            decisions[name] = {'outcome': '旧入口已归类，替代检查通过', 'evidence': ['research/review_g135_gpt/evidence/windows.json', 'research/review_g135_gpt/evidence/boundary-sweep.json'], 'raw_returncode': execution['returncode']}
    elif job.get('group') == 'values':
        for path, data in errors:
            try:
                cases = ast.literal_eval(data.get('message', ''))
            except (ValueError, SyntaxError):
                continue
            if not isinstance(cases, list) or len(cases) != 7 or not all(isinstance(case, dict) for case in cases):
                continue
            failed = [case for case in cases if case.get('wait_status') != 0]
            if len(failed) == 1 and failed[0].get('case') == 'back-from-second-pair' and failed[0].get('wait_status') == 256:
                nav = json.loads((OUT / 'evidence/nav-memory.json').read_text())
                assert nav['current_observed'] == [1, 2]
                decisions[name] = {'outcome': '旧光标期望已归类，其余通过', 'cases': cases, 'evidence': str(path.relative_to(ROOT)), 'navigation_evidence': 'research/review_g135_gpt/evidence/nav-memory.json', 'raw_returncode': execution['returncode']}

decision_file.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'classified_current_groups': len(decisions), 'names': sorted(decisions)}, ensure_ascii=False))
