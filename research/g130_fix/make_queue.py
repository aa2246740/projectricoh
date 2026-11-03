#!/usr/bin/python3
"""Keep the requested focused checks in one sequential process."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g130_fix'
jobs = []
units = ('50mm', '28mm', 'mount')
for case in ('h07-parent', 'h07-parent-preview', 'preview-window', 'settings-check'):
    for unit in units:
        jobs.append(dict(name=case + '-' + unit, script='research/review_g127/native_checks.py', args=['--case', case, '--unit', unit, '--crc-mode', 'native'], timeout_seconds=1200, crc_implementation='native'))
for name in ('ownership_settings', 'cold_reentry', 'cold_exit', 'settings_cases'):
    for unit in units:
        jobs.append(dict(name=name + '-' + unit, script='research/review_g126/' + name + '.py', args=['--unit', unit], timeout_seconds=3600, crc_implementation='host'))
for group in ('safety', 'locked', 'nested', 'cutpoints', 'exits'):
    jobs.append(dict(name='batch-' + group + '-50mm', script='research/review_g126/batch.py', args=['--unit', '50mm', '--groups', group, '--tag', 'g130-' + group], timeout_seconds=3600, crc_implementation='host'))
(WORK / 'queue.json').write_text(json.dumps(jobs, indent=2) + '\n')
print(json.dumps(dict(name='focused-queue', returncode=0, counts=dict(jobs=len(jobs), parallel=1))))
