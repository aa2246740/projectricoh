"""Run a single foreground review command with a timeout and write fence."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-batch-r3')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=int, default=3600)
    parser.add_argument('name')
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    assert os.getpriority(os.PRIO_PROCESS, 0) == 15, 'launch the runner with nice -n 15'
    command = ['/usr/bin/sandbox-exec', '-f', str(HERE / 'fence.sb'),
               '/usr/bin/python3', '-I', '-B', *arguments]
    env = dict(os.environ, TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1', GXR_EMULATOR_BATCH='0')
    started = time.monotonic()
    record = {'command': command, 'timeout_seconds': args.timeout, 'cwd': str(ROOT),
              'nice': os.getpriority(os.PRIO_PROCESS, 0),
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (HERE / 'local/serial.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (HERE / 'local' / (args.name + '.log')).open('w') as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            record['pid'] = process.pid
            try:
                record['returncode'] = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                record.update(returncode=124, timed_out=True)
        record['seconds'] = time.monotonic() - started
        (HERE / 'local' / (args.name + '-process.json')).write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)
    raise SystemExit(record['returncode'])


if __name__ == '__main__':
    main()
