"""Run one foreground check with an isolated temporary directory and a receipt."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import runpy
import signal
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class Log:
    def __init__(self, stream, visible):
        self.stream, self.visible, self.pending = stream, visible, ''

    def write(self, value):
        self.stream.write(value)
        self.stream.flush()
        self.pending += value
        while '\n' in self.pending:
            line, self.pending = self.pending.split('\n', 1)
            if line.strip():
                self.visible.write(line[:300] + (' ...' if len(line) > 300 else '') + '\n')
                self.visible.flush()
        return len(value)

    def flush(self):
        self.stream.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--timeout', type=int, default=10800)
    parser.add_argument('script')
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) == 10
    script = HERE / args.script
    scratch = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g153/jobs') / f'p{os.getpid()}'
    scratch.mkdir(parents=True, exist_ok=False)
    os.environ.update(TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1',
                      GXR_EMULATOR_BATCH='1', REVIEW_JOB=args.name)
    # The recovery check verifies its shared task TMPDIR explicitly; its
    # output and synthetic medium are separated by each case label.
    if script.name == 'recovery_path.py':
        os.environ['TMPDIR'] = '/Volumes/Workspace/Scratch/tmp/projectricoh/g153'
    started, clock = time.time_ns(), time.monotonic()
    log_path = HERE / 'local' / (args.name + '.log')
    receipt = dict(name=args.name, script=str(script.relative_to(ROOT)), arguments=args.arguments,
                   script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(), pid=os.getpid(),
                   nice=os.getpriority(os.PRIO_PROCESS, 0), started_ns=started,
                   timeout=args.timeout, TMPDIR=os.environ['TMPDIR'], backend='Python')
    print('START ' + args.name, flush=True)
    status = 0
    visible, errors = sys.stdout, sys.stderr
    def expired(signum, frame):
        raise TimeoutError(args.name)
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(args.timeout)
    with log_path.open('w') as log:
        sys.stdout = Log(log, visible)
        sys.stderr = Log(log, errors)
        try:
            sys.argv = [str(script), *args.arguments]
            runpy.run_path(str(script), run_name='__main__')
        except SystemExit as exc:
            status = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        except BaseException:
            status = 1
            traceback.print_exc()
        finally:
            signal.alarm(0)
            sys.stdout, sys.stderr = visible, errors
    receipt.update(returncode=status, ended_ns=time.time_ns(), seconds=time.monotonic()-clock,
                   log_sha256=hashlib.sha256(log_path.read_bytes()).hexdigest())
    (HERE / 'evidence' / (args.name + '-receipt.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    with (HERE / 'PROGRESS.md').open('a') as progress:
        progress.write(datetime.datetime.now(datetime.timezone.utc).isoformat() +
                       f'：{args.name} 返回 {status}，耗时 {receipt["seconds"]:.1f} 秒。\n')
    print('END ' + args.name + ' rc=' + str(status), flush=True)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
