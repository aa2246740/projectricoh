"""Copy of research/review_cpuprobe_r2/run_review.py (unchanged logic): two test processes, explicit deadlines."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import review_scope as rs
rs.enable()
TIMEOUT = dict(full=2400, cursor=1200, irq=600, exits=1200, pages=1200,
               cache=1800, retire=600, extra=2400, rebuild=1800,
               reference=600, boot=900, draw=900, **{'native-probe': 900, 'effect-probe': 900, 'old-cache': 1800})


def run(case, unit, name):
    started = time.monotonic()
    target = 'extra_review.py' if case in ('extra', 'draw') else 'rebuild_review.py' if case == 'rebuild' else 'batch_review.py'
    if case == 'old-cache':
        target = 'old_control.py'
    sources_before = {p.name: rs.digest(p) for p in HERE.glob('*.py')}
    command = ['nice', '-n', '10', '/usr/bin/python3', '-I', '-B', str(HERE / target), case, unit]
    log = HERE / 'logs' / (name + '-' + case + '-' + unit + '.log')
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w') as stream:
        try:
            result = subprocess.run(command, cwd=rs.ROOT, env=dict(os.environ),
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=TIMEOUT[case])
            status = 'PASS' if result.returncode == 0 else 'FAIL'
            code = result.returncode
        except subprocess.TimeoutExpired:
            status, code = 'INCOMPLETE', None
    row = dict(case=case, unit=unit, status=status, returncode=code,
               seconds=round(time.monotonic() - started, 3), timeout=TIMEOUT[case],
               argv=command, log=str(log.relative_to(rs.ROOT)),
               scripts_before=sources_before, scripts_after={p.name: rs.digest(p) for p in HERE.glob('*.py')})
    print('REVIEW_JOB', case, unit, status, row['seconds'], flush=True)
    return row


def main():
    name = sys.argv[1]
    jobs = [tuple(job.split(':')) for job in sys.argv[2:]]
    result_path = HERE / (name + '.json')
    assert not result_path.exists()
    started = time.monotonic()
    rows = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run, case, unit, name) for case, unit in jobs]
        for future in as_completed(futures):
            rows.append(future.result())
            rs.save(result_path, dict(max_test_processes=2, results=rows,
                                     seconds=round(time.monotonic() - started, 3)))
    assert len(rows) == len(jobs)
    assert all(row['status'] == 'PASS' for row in rows), rows


if __name__ == '__main__':
    main()
