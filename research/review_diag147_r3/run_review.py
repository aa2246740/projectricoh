"""Run one review script in process with a bounded foreground lifetime."""
from pathlib import Path
import json
import os
import runpy
import signal
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope

os.environ['TMPDIR'] = str(scope.SCRATCH)
scope.enable_fence()
name = sys.argv[1]
assert Path(name).name == name
args = sys.argv[2:]
sys.argv = [str(HERE / name)] + args
started = time.monotonic()
signal.alarm(1800)
code = 0
try:
    runpy.run_path(str(HERE / name), run_name='__main__')
except SystemExit as result:
    code = result.code or 0
except BaseException:
    traceback.print_exc()
    code = 1
finally:
    signal.alarm(0)
    elapsed = time.monotonic() - started
    label = name + (('-' + '-'.join(args).replace('/', '_')) if args else '')
    scope.save(HERE / ('timing-' + label + '.json'), dict(script=name, args=args, seconds=elapsed,
               timeout_seconds=1800, exit_code=code, nice=os.getpriority(os.PRIO_PROCESS, 0)))
    print('REVIEW_RUN', name, 'exit', code, 'seconds', round(elapsed, 3), flush=True)
sys.exit(code)
