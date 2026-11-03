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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import ROOT, WORK, LOCAL, setup, save, sha, neutral
from fences import check_inputs
from queue_run import Log

DAT_SHA = '78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8'
BODY_SHA = 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'
DEADLINE = datetime.datetime(2026, 10, 30, 4, 42, 36, tzinfo=datetime.timezone.utc).timestamp()


def identity():
    package = ROOT / 'firmware/package_v38_g137/local/SD_ROOT'
    assert sha(package / 'GXRCE.DAT') == DAT_SHA
    assert sha(package / 'ilaunch3') == BODY_SHA
    check_inputs()


def expired(signum, frame):
    raise TimeoutError('Job time limit reached')


def historical_time(job):
    history = json.loads((LOCAL / 'queue-final-state.json').read_text())['jobs']
    seconds = [row['seconds'] for row in history]
    if job['script'].endswith('/run_existing.py'):
        arguments = job['args']
        name = Path(arguments[0]).stem + '-' + '-'.join(arguments[1:])
        for base in (ROOT / 'research/g135_v37/local/checks', LOCAL / 'checks'):
            for path in base.glob('**/result-' + name + '.json'):
                if path.is_file():
                    seconds.append(json.loads(path.read_text()).get('seconds', 0))
    return max(seconds, default=0)


def main():
    setup()
    identity()
    jobs = json.loads((WORK / 'queue-final.json').read_text())
    jobs = jobs[4:]
    index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    state_path = LOCAL / 'resume-state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'jobs': []}
    if index >= len(jobs):
        print(json.dumps({'complete': True, 'jobs': len(state['jobs']),
                          'failed': sum(row['returncode'] != 0 for row in state['jobs'])}), flush=True)
        return
    if time.time() >= DEADLINE:
        state['status'] = 'INCOMPLETE_TIME_LIMIT'
        save(state_path, state)
        print(json.dumps({'status': state['status'], 'next': jobs[index]['name']}), flush=True)
        return
    job = jobs[index]
    historical_seconds = historical_time(job)
    timeout_seconds = max(3600, int(historical_seconds * 3) + 60)
    os.environ['GXR_JOB_TIMEOUT'] = str(timeout_seconds)
    started = time.monotonic()
    script = ROOT / job['script']
    sys.argv = [str(script)] + job.get('args', [])
    code = 0
    status = 'PASS'
    print(json.dumps({'started': job['name'], 'timeout_seconds': timeout_seconds}), flush=True)
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    with (LOCAL / ('r2-' + job['name'] + '.log')).open('w') as file:
        output = Log(file)
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                runpy.run_path(str(script), run_name='__main__')
            except SystemExit as error:
                code = error.code if isinstance(error.code, int) else 1 if error.code else 0
            except TimeoutError:
                code = 124
                status = 'INCOMPLETE_TIME_LIMIT'
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
    record = {'index': index + 4, 'name': job['name'], 'returncode': code,
              'status': status, 'seconds': round(time.monotonic() - started, 3),
              'historical_seconds': historical_seconds, 'timeout_seconds': timeout_seconds,
              'dat_sha256': DAT_SHA, 'body_sha256': BODY_SHA}
    state['jobs'].append(record)
    save(state_path, state)
    print(json.dumps(record), flush=True)
    os.execv('/usr/bin/python3', ['/usr/bin/python3', '-I', '-B', str(WORK / 'resume_queue.py'), str(index + 1)])


if __name__ == '__main__':
    main()
