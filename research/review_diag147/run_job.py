"""Run one review script in the current process with a foreground timeout."""
from pathlib import Path
import contextlib
import datetime
import json
import os
import runpy
import signal
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-diag147')
os.environ['TMPDIR'] = str(TMP)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.path.insert(0, str(HERE))
import scope
scope.enable_fence()
assert TMP.resolve() == TMP
TMP.mkdir(parents=True, exist_ok=True)

def expired(signum, frame):
    raise TimeoutError('REVIEW_JOB_TIMEOUT')

name, script, *args = sys.argv[1:]
assert name.replace('-', '').replace('_', '').isalnum()
target = (HERE / script).resolve()
assert target.is_relative_to(HERE)
timeout = int(os.environ.get('REVIEW_TIMEOUT', '1800'))
start = time.monotonic()
status = 0
signal.signal(signal.SIGALRM, expired)
signal.alarm(timeout)
with (HERE / (name + '.log')).open('w') as stream:
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            sys.argv = [str(target), *args]
            runpy.run_path(str(target), run_name='__main__')
        except SystemExit as exc:
            status = int(exc.code or 0)
        except BaseException:
            traceback.print_exc()
            status = 1
signal.alarm(0)
receipt = dict(script=str(target.relative_to(ROOT)), args=args,
               exit_code=status, elapsed_seconds=round(time.monotonic()-start, 3),
               timeout_seconds=timeout, max_review_processes=2,
               utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(HERE / (name + '-receipt.json')).write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt), flush=True)
sys.exit(status)
