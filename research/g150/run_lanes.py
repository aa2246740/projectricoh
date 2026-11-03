"""Run a queue of run_case.py jobs in two foreground lanes; wait for all.

  /usr/bin/python3 -I -B research/g150/run_lanes.py <queue.json>

queue.json: [{"job", "generation", "script", "cases", "unit", "timeout", "package"?}, ...]
script: "g150" (g150_checks.py), "review" (independent_checks.py) or "host" (tests/g139_check.py).
Each job is one run_case.py call (sandboxed, nice 10, its own timeout and
fresh-output receipt). At most two jobs run at once; the summary goes to
evidence/<queue name>-complete.json.
"""
from pathlib import Path
import json
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = {'g150': 'research/g150/g150_checks.py', 'review': 'research/g150/independent_checks.py',
           'host': 'research/g150/tests/g139_check.py'}


def outputs(job):
    base = 'tests/local' if job['script'] != 'host' else 'tests/local'
    folder = HERE / base / job['job'] / 'checks' if job['script'] != 'host' else HERE / 'tests/local' / job['job'] / 'checks'
    return [str((folder / ('%s-%s.json' % (job['unit'], case))).relative_to(ROOT)) for case in job['cases']]


def run(job, results):
    command = ['/usr/bin/python3', '-I', '-B', str(HERE / 'run_case.py'), '--job', job['job'],
               '--generation', str(job['generation']), '--package', job.get('package', 'test'),
               '--timeout', str(job['timeout']), '--outputs', *outputs(job), '--',
               '/usr/bin/python3', '-I', '-B', SCRIPTS[job['script']], *job['cases'], '--unit', job['unit']]
    started = time.monotonic()
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    line = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else '{}'
    try:
        receipt = json.loads(line)
    except ValueError:
        receipt = dict(status='RUNNER_ERROR', stderr=done.stderr[-2000:])
    row = dict(job=job['job'], generation=job['generation'], unit=job['unit'], cases=job['cases'],
               status=receipt.get('status'), seconds=round(time.monotonic() - started, 3),
               outputs=[dict(path=o.get('path'), status=o.get('status'), case_seconds=o.get('case_seconds'),
                             fresh=o.get('fresh'), dat_sha256=o.get('dat_sha256')) for o in receipt.get('outputs', [])])
    results.append(row)
    print(row['status'], row['job'], row['seconds'], [o['status'] for o in row['outputs']], flush=True)


def main():
    queue_path = Path(sys.argv[1])
    queue = json.loads(queue_path.read_text())
    pending = list(queue); results = []; lock = threading.Lock()

    def lane():
        while True:
            with lock:
                if not pending:
                    return
                job = pending.pop(0)
            run(job, results)
    lanes = [threading.Thread(target=lane) for _ in range(2)]
    for t in lanes:
        t.start()
    for t in lanes:
        t.join()
    summary = HERE / 'evidence' / (queue_path.stem + '-complete.json')
    summary.write_text(json.dumps(sorted(results, key=lambda r: r['job']), indent=2) + '\n')
    print(json.dumps({r['job']: r['status'] for r in results}, indent=1))


if __name__ == '__main__':
    main()
