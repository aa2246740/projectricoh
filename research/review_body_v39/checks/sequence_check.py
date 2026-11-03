#!/usr/bin/python3 -I
"""Run a declared sequence in one foreground test slot."""
from pathlib import Path
import json
import subprocess
import sys
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_body_v39/evidence'
plan_path = Path(sys.argv[1]).resolve()
plan = json.loads(plan_path.read_text())
record = OUT / (plan_path.stem + '-sequence.json')
rows = []
start = time.monotonic()
for job in plan['jobs']:
    command = ['/usr/bin/python3', '-I', '-B',
               str(ROOT / 'research/review_body_v39/checks/run_work.py'),
               job['name'], str(job['timeout_seconds']), *job['command']]
    print(json.dumps({'event': 'start', 'name': job['name']}), flush=True)
    result = subprocess.run(command, cwd=ROOT)
    receipt = json.loads((OUT / (job['name'] + '-receipt.json')).read_text())
    rows.append(receipt)
    record.write_text(json.dumps({'jobs': rows, 'seconds': time.monotonic() - start}, indent=1) + '\n')
    if result.returncode:
        raise SystemExit(result.returncode)
print(json.dumps({'event': 'finished', 'jobs': len(rows), 'seconds': round(time.monotonic() - start, 3)}))
