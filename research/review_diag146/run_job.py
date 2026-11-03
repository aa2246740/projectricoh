"""带硬超时的单个复审进程，不轮询。"""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
label, script, *args = sys.argv[1:]
started = time.monotonic()
command = ['/usr/bin/nice', '-n', '10', '/usr/bin/python3', '-I', '-B', str(scope.HERE / script), *args]
try:
    p = subprocess.run(command, cwd=scope.ROOT, capture_output=True, text=True,
                       timeout=7200, env=dict(os.environ, TMPDIR=str(scope.SCRATCH)))
    (scope.HERE / (label + '.log')).write_text(p.stdout + p.stderr)
    result = dict(command=command, returncode=p.returncode, timeout_seconds=7200,
                  seconds=time.monotonic() - started)
except subprocess.TimeoutExpired as e:
    (scope.HERE / (label + '.log')).write_bytes((e.stdout or b'') + (e.stderr or b''))
    result = dict(command=command, returncode='TIMEOUT', timeout_seconds=7200,
                  seconds=time.monotonic() - started)
scope.save(scope.HERE / (label + '-receipt.json'), result)
print(json.dumps(result, ensure_ascii=False))
if result['returncode'] != 0:
    raise SystemExit(1)
