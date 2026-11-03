"""One active test child, a 4200-second timeout per case, no polling."""
from pathlib import Path
import os
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
cases = [('50mm','full'),('mount','full'),('28mm','empty'),('28mm','notready'),('28mm','heap')]
for unit,mode in cases:
    name = 'accept-' + unit + '-' + mode
    start = time.monotonic()
    with (scope.HERE / (name+'.log')).open('w') as log:
        try:
            child = subprocess.run(['/usr/bin/python3','-I','-B',str(scope.HERE/'run_accept.py'),unit,mode],
                                   stdout=log,stderr=subprocess.STDOUT,cwd=scope.ROOT,
                                   env=dict(os.environ,TMPDIR=str(scope.SCRATCH)),timeout=4200)
            result = {'exit_code':child.returncode,'seconds':time.monotonic()-start,'timeout_seconds':4200}
        except subprocess.TimeoutExpired:
            result = {'exit_code':'TIMEOUT','seconds':time.monotonic()-start,'timeout_seconds':4200}
    scope.save(scope.HERE / (name+'-receipt.json'), result)
    print(name,result,flush=True)
    if result['exit_code'] != 0:
        print('\n'.join((scope.HERE/(name+'.log')).read_text().splitlines()[-12:]),flush=True)
        raise SystemExit(1)
