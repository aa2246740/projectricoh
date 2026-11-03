"""Run at most one test child under OS and Python write fences, with no sleep/poll loop."""
from pathlib import Path
import os
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
profile = ('(version 1) (allow default) (deny file-write*) '
           '(allow file-write* (subpath "%s") (subpath "%s") (literal "/dev/null")) '
           '(deny network*) (deny file-read* (subpath "/Volumes/RICOHDCX"))') % (scope.HERE, scope.SCRATCH)
cases = [(unit, 'publish') for unit in ('28mm', '50mm', 'mount')]
cases += [('28mm', 'refuse'), ('50mm', 'refuse'), ('28mm', 'init'), ('28mm', 'notready')]
if len(sys.argv) > 1 and sys.argv[1] == 'experiments':
    cases = [('experiments', '')]
elif len(sys.argv) > 1:
    cases = [tuple(sys.argv[1:3])]
for unit, mode in cases:
    name = unit + ('-' + mode if mode else '')
    script_args = ([str(scope.HERE / 'experiments.py')] if unit == 'experiments' else
                   [str(scope.HERE / 'run_accept.py'), unit, mode])
    start = time.monotonic()
    with (scope.HERE / (name + '.log')).open('w') as log:
        try:
            child = subprocess.run(['sandbox-exec', '-p', profile, '/usr/bin/python3', '-I', '-B',
                                    *script_args],
                                   stdout=log, stderr=subprocess.STDOUT, cwd=scope.ROOT,
                                   env=dict(os.environ, TMPDIR=str(scope.SCRATCH)), timeout=4200)
            result = dict(exit_code=child.returncode, seconds=time.monotonic() - start, timeout_seconds=4200)
        except subprocess.TimeoutExpired:
            result = dict(exit_code='TIMEOUT', seconds=time.monotonic() - start, timeout_seconds=4200)
    scope.save(scope.HERE / (name + '-receipt.json'), result)
    print(name, result, flush=True)
    if result['exit_code'] != 0:
        print('\n'.join((scope.HERE / (name + '.log')).read_text().splitlines()[-16:]), flush=True)
        raise SystemExit(1)
