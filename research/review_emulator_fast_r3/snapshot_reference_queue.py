"""Candidate snapshot layer + explicit Python reference devices, fresh processes."""
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
rows = []
for kind, name in (('recipe-off', 'key-current-reference'), ('hold', 'hold-current-reference')):
    args = [sys.executable, '-I', '-B', str(HERE / 'snapshot_probes.py'), kind,
            '--backend', 'reference', '--name', name, '--short']
    with (HERE / 'runs' / (name + '-queue.log')).open('x') as log:
        child = subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                               env=dict(os.environ, GXR_STRICT_REFERENCE_ORACLE='current'), timeout=500)
    rows.append(dict(name=name, returncode=child.returncode))
    (HERE / 'runs/snapshot-current-reference-queue.json').write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps(rows[-1]), flush=True)
