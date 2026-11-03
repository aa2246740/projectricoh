"""Run the gen 147 / g147a host acceptance (at most two processes at a time, each under nice -n 10).

Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/diag147 \
       /usr/bin/python3 -I -B research/diag147/run_accept147.py <out-name> [case:unit ...]
       /usr/bin/python3 -I -B research/diag147/run_accept147.py --g147a <out-name> [case:unit ...]

Default: the five gen 147 cases on the three units (15 runs); with --g147a: accept_diag147a.py, full and
refuse on the three units (6 runs). Each run gets 1,800 s (gen 146 history: 35-60 s per
case; the gen 147 faults case has 15 opens, so the bound is far above 3x). Logs and summary.json go to
research/diag147/local/<out-name>/ (ignored). The runner waits on its child processes; it does not poll.
"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
assert Path(os.environ['TMPDIR']) == Path('/Volumes/Workspace/Scratch/tmp/projectricoh/diag147')
G147A = '--g147a' in sys.argv
ARGS = [a for a in sys.argv[1:] if a != '--g147a']
SCRIPT = 'accept_diag147a.py' if G147A else 'accept_diag147.py'
OUT = HERE / 'local' / ARGS[0]
JOBS = ARGS[1:] or ['%s:%s' % (c, u) for c in (('full', 'refuse') if G147A else
                                             ('full', 'keep1', 'faults', 'refuse', 'otherfile'))
                    for u in ('50mm', '28mm', 'mount')]
TIMEOUT = 1800


def run(job):
    case, unit = job.split(':')
    log = OUT / ('%s-%s.log' % (case, unit))
    started = time.monotonic()
    args = ['nice', '-n', '10', '/usr/bin/python3', '-I', '-B', str(HERE / SCRIPT), case, unit]
    with log.open('w') as stream:
        try:
            rc = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT, timeout=TIMEOUT, cwd=ROOT).returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
    lines = log.read_text().strip().splitlines()
    done = [l for l in lines if l.startswith('ACCEPT_DONE')]
    row = dict(case=case, unit=unit, rc=rc, seconds=round(time.monotonic() - started, 1),
               status='PASS' if rc == 0 and done else ('INCOMPLETE' if rc == 'timeout' else 'FAIL'),
               last=(done or lines[-1:] or [''])[0][:400])
    print(json.dumps(row), flush=True)
    return row


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(run, JOBS))
    counts = {k: sum(1 for r in rows if r['status'] == k) for k in ('PASS', 'FAIL', 'INCOMPLETE')}
    (OUT / 'summary.json').write_text(json.dumps(dict(counts=counts, rows=rows), indent=1) + '\n')
    (OUT / 'DONE').write_text(('PASS' if counts['PASS'] == len(rows) else 'FAIL') + '\n')
    print('SUMMARY', json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()
