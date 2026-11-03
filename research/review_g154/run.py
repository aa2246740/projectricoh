"""前台复审入口，独立回执，超时后退出，不改实现方证据。"""
from pathlib import Path
import argparse
import contextlib
import datetime
import hashlib
import json
import os
import signal
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('group')
    p.add_argument('--unit', default='50mm')
    p.add_argument('--control', action='store_true')
    p.add_argument('--name', required=True)
    p.add_argument('--timeout', type=int, default=5400)
    a = p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) == 10
    assert a.timeout >= 1800
    if a.control:
        os.environ['G154_CONTROL'] = 'g153'
    else:
        os.environ.pop('G154_CONTROL', None)
    tmp = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g154-r1')
    tmp.mkdir(parents=True, exist_ok=True)
    os.environ.update(TMPDIR=str(tmp), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
    receipt = HERE / 'evidence' / (a.name + '.json')
    receipt.parent.mkdir(exist_ok=True)
    assert not receipt.exists(), receipt
    row = dict(name=a.name, group=a.group, unit=a.unit, control=a.control,
               backend=os.environ.get('GXR_HARNESS_BACKEND', 'c'), pid=os.getpid(), nice=10,
               timeout=a.timeout, started=datetime.datetime.now().astimezone().isoformat())
    row['review_source_sha256']={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                                for name in ('checks.py','review_support.py','run.py')}
    started = time.monotonic()
    old = signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(TimeoutError('复审作业达到时限')))
    signal.alarm(a.timeout)
    code = 0
    try:
        with (receipt.with_suffix('.log')).open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            try:
                import checks
                row['details'] = getattr(checks, a.group)(a.unit)
                row['adaptations'] = checks.R.ADAPTATIONS
                row['status'] = 'PASS'
            except BaseException:
                traceback.print_exc()
                row['status'] = 'FAIL'
                code = 1
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
        row.update(seconds=time.monotonic()-started, returncode=code,
                   ended=datetime.datetime.now().astimezone().isoformat())
        receipt.write_text(json.dumps(row, ensure_ascii=False, indent=2, default=str) + '\n')
    print(json.dumps({k: v for k, v in row.items() if k not in ('details', 'adaptations')}, ensure_ascii=False), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
