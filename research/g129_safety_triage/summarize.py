"""Collect per-case safety records from the triage jobs into evidence/summary.json and a text table."""
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parent
JOBS = [
    ('g129', 'orig-reader', 'wrapper', 'triage-safety-50mm-orig'),
    ('g129', 'stale-layout+diag', 'wrapper', 'triage-safety-50mm-patched'),
    ('g129', 'corrected-reader', 'wrapper', 'triage-safety-50mm-fixedreader'),
    ('g129', 'corrected-reader', 'wrapper', 'triage-safety-50mm-final'),
    ('g129', 'corrected-reader', 'wrapper', 'triage-safety-28mm-final'),
    ('g129', 'corrected-reader', 'wrapper', 'triage-safety-mount-final'),
    ('g129', 'orig-reader', 'wrapper', 'triage-safety-28mm-orig'),
    ('g129', 'orig-reader', 'wrapper', 'triage-safety-mount-orig'),
    ('g131', 'corrected-reader', 'wrapper131', 'triage-g131-safety-50mm-fixedreader'),
    ('g131', 'corrected-reader', 'wrapper131', 'triage-g131-safety-28mm-fixedreader'),
    ('g131', 'corrected-reader', 'wrapper131', 'triage-g131-safety-mount-fixedreader'),
    ('g131', 'orig-reader', 'wrapper131', 'triage-g131-safety-50mm-orig'),
]
rows = []
for gen, reader, wrapper, job in JOBS:
    folder = ROOT / wrapper / 'local' / job / 'review_g124' / 'local' / 'safety'
    result = ROOT / wrapper / 'local' / job / 'review_g124' / 'result.json'
    if not folder.is_dir():
        continue
    cases = {}
    for path in sorted(folder.glob('*.json')):
        record = json.loads(path.read_text())
        error = (record.get('error') or '').strip().splitlines()
        cases[record['case']] = dict(status=record['status'], error_tail=error[-1][:200] if error else '')
    unit = next(iter(json.loads(p.read_text())['unit'] for p in folder.glob('*.json')))
    info = json.loads(result.read_text()) if result.exists() else {}
    rows.append(dict(generation=gen, reader=reader, job=job, unit=unit, returncode=info.get('returncode'),
                     seconds=info.get('seconds'), dat_sha256=info.get('dat_sha256'), cases=cases,
                     passed=sum(c['status'] == 'PASS' for c in cases.values()), total=len(cases)))
(ROOT / 'evidence/summary.json').write_text(json.dumps(rows, indent=2) + '\n')
names = ['h01_switch_activity', 'h01_switch_state', 'list_rollback', 'panel_rollback', 'ready_warm', 'settings_recheck', 'write_latch', 'storage']
print('| gen | reader | unit | job | rc | s | pass | ' + ' | '.join(n for n in names if n in ('panel_rollback', 'ready_warm', 'write_latch')) + ' |')
for r in rows:
    print('| %s | %s | %s | %s | %s | %s | %d/%d | %s |' % (r['generation'], r['reader'], r['unit'], r['job'], r['returncode'], r['seconds'], r['passed'], r['total'],
          ' | '.join(r['cases'].get(n, {}).get('status', '-') for n in ('panel_rollback', 'ready_warm', 'write_latch'))))
