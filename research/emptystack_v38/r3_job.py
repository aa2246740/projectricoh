"""Round-3 single-job runner: run one named job of queue-final.json in this process and record the result."""
from pathlib import Path
import contextlib
import json
import os
import runpy
import signal
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import ROOT, WORK, LOCAL, setup, save
from queue_run import Log
from resume_queue import identity, historical_time, DAT_SHA, BODY_SHA

STATE = LOCAL / 'r3-state'


def expired(signum, frame):
    raise TimeoutError('Job time limit reached')


def main():
    setup()
    identity()
    name = sys.argv[1]
    jobs = {row['name']: row for file in ('queue-final.json', 'queue-r3-extra.json')
            for row in json.loads((WORK / file).read_text())}
    job = jobs[name]
    timeout_seconds = max(3600, int(historical_time(job) * 3) + 60)
    os.environ['GXR_JOB_TIMEOUT'] = str(timeout_seconds)
    os.environ.update(job.get('env', {}))
    script = ROOT / job['script']
    sys.argv = [str(script)] + job.get('args', [])
    STATE.mkdir(parents=True, exist_ok=True)
    code, status, started = 0, 'PASS', time.monotonic()
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    with (LOCAL / ('r3-' + name + '.log')).open('w') as file:
        output = Log(file)
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                runpy.run_path(str(script), run_name='__main__')
            except SystemExit as error:
                code = error.code if isinstance(error.code, int) else 1 if error.code else 0
            except TimeoutError:
                code, status = 124, 'INCOMPLETE_TIME_LIMIT'
                output.write('Job time limit reached\n')
            except BaseException as error:
                code = 1
                output.write(type(error).__name__ + ': ' + str(error) + '\n')
                for entry in traceback.extract_tb(error.__traceback__):
                    output.write(str(entry.filename) + ':' + str(entry.lineno) + ' ' + entry.name + '\n')
    signal.setitimer(signal.ITIMER_REAL, 0)
    identity()
    if code != 0 and status == 'PASS':
        status = 'FAIL'
    record = {'name': name, 'returncode': code, 'status': status,
              'seconds': round(time.monotonic() - started, 3), 'timeout_seconds': timeout_seconds,
              'dat_sha256': DAT_SHA, 'body_sha256': BODY_SHA}
    save(STATE / (name + '.json'), record)
    print(json.dumps(record), flush=True)
    sys.exit(code)


if __name__ == '__main__':
    main()
