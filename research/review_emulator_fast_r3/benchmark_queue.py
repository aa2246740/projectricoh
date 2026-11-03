"""All R3 functional work must be finished before starting this queue."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
result = dict(started=time.strftime('%FT%TZ', time.gmtime()), jobs=[])
for label, command in (
        ('profile', [sys.executable, '-I', '-B', str(HERE / 'profile_native.py')]),
        ('quiet-preflight', ['/usr/bin/top', '-l', '2', '-s', '1', '-n', '12', '-o', 'cpu']),
        ('main', [sys.executable, '-I', '-B', str(HERE / 'benchmark.py'), '--kind', 'main', '--pairs', '5']),
        ('input', [sys.executable, '-I', '-B', str(HERE / 'benchmark.py'), '--kind', 'input', '--pairs', '5'])):
    print(json.dumps(dict(start=label, utc=time.strftime('%FT%TZ', time.gmtime()))), flush=True)
    with (HERE / 'runs' / ('benchmark-queue-' + label + '.log')).open('x') as log:
        child = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=2000)
    row = dict(label=label, returncode=child.returncode)
    result['jobs'].append(row)
    (HERE / 'runs/benchmark-queue.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(row), flush=True)
    if child.returncode:
        raise SystemExit(child.returncode)
result['status'] = 'COMPLETE'
(HERE / 'runs/benchmark-queue.json').write_text(json.dumps(result, indent=2) + '\n')
