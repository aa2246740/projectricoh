"""Sequential runs of copied acceptance checks; no product input is writable."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope

scope.enable_fence()
CASES = ['28mm-retire', 'allwritefail', 'busyall', 'notready', 'busy', 'partial',
         'cuts', '50mm', 'mount', '28mm-refuse', 'nofile', 'badheader', 'short',
         'closefail', 'ingress-I', 'svcfail', 'name-zero', 'noreadback']
rows = []
for case in sys.argv[1:] or CASES:
    start = time.monotonic()
    args = ['/usr/bin/nice', '-n', '10', '/usr/bin/python3', '-I', '-B',
            str(scope.HERE / 'accept_diag146.py'), case]
    log = scope.HERE / ('host-' + case + '.log')
    with log.open('w') as stream:
        try:
            result = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=600, cwd=scope.ROOT, env=os.environ.copy())
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 'TIMEOUT'
    row = dict(case=case, seconds=round(time.monotonic()-start, 3), returncode=code,
               timeout_seconds=600, log=str(log.relative_to(scope.ROOT)))
    rows.append(row)
    scope.save(scope.HERE / 'host-suite.json', rows)
    print(json.dumps(row), flush=True)
print('HOST_SUITE_DONE', all(r['returncode'] == 0 for r in rows), flush=True)
