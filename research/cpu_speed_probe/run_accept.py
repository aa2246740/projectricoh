"""Run acceptance cases, at most 2 at a time, each under nice -n 10 with a timeout.

Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/cpuprobe \
       /usr/bin/python3 -I -B research/cpu_speed_probe/run_accept.py <run-name> case:unit [case:unit ...]

Writes research/cpu_speed_probe/local/runs/<run-name>.json and one log per case; prints PASS / FAIL / TIMEOUT
counts (a timeout is reported as INCOMPLETE, never as PASS).
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# history: full ~230 s, cursor ~260 s, irq ~70 s on this machine (2 processes in parallel)
TIMEOUT = {'full': 2400, 'cursor': 900, 'irq': 300, 'exits': 900, 'pages': 900, 'cache': 1500, 'retire': 300, 'bounds': 3600}


def main():
    name, jobs = sys.argv[1], [tuple(x.split(':')) for x in sys.argv[2:]]
    out = HERE / 'local/runs'
    out.mkdir(parents=True, exist_ok=True)
    assert not (out / (name + '.json')).exists(), 'run name used'
    pending, running, results = list(jobs), [], {}
    while pending or running:
        while pending and len(running) < 2:
            case, unit = pending.pop(0)
            log = (out / ('%s-%s-%s.log' % (name, case, unit))).open('w')
            p = subprocess.Popen(['nice', '-n', '10', '/usr/bin/python3', '-I', '-B',
                                  str(HERE / 'accept_cpuprobe.py'), case, unit], cwd=ROOT, stdout=log,
                                 stderr=subprocess.STDOUT, env=dict(os.environ))
            running.append((case, unit, p, time.monotonic(), log))
        case, unit, p, started, log = running[0]
        try:
            p.wait(timeout=max(1, TIMEOUT[case] - (time.monotonic() - started)))
            status = 'PASS' if p.returncode == 0 else 'FAIL'
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
            status = 'INCOMPLETE'
        log.close()
        running.pop(0)
        results['%s:%s' % (case, unit)] = dict(status=status, seconds=round(time.monotonic() - started, 1),
                                               returncode=p.returncode)
        print(case, unit, status, results['%s:%s' % (case, unit)]['seconds'], flush=True)
    (out / (name + '.json')).write_text(json.dumps(results, indent=1) + '\n')
    counts = {k: sum(1 for r in results.values() if r['status'] == k) for k in ('PASS', 'FAIL', 'INCOMPLETE')}
    print('RUN', name, json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()
