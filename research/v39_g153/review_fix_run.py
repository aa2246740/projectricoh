"""Run bounded foreground batches and wait for both jobs at every boundary."""
from pathlib import Path
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PHASES = {
    'matrix': [
        ('matrix-' + unit, 'lock_checks.py', ['--unit', unit, '--timings', 'held',
         'race-at-s', 'transient', '--exits', 'ok', 'half', '--label', 'fix',
         '--summary', 'lock-fix-' + unit + '.json'], 7200)
        for unit in ('50mm', 'mount')],
    'lifetime': [
        ('lifetime-' + unit + '-' + str(slot), 'review_fix_checks.py',
         ['after-refusal', '--unit', unit, '--slot', str(slot)], 3600)
        for slot in (8, 4) for unit in ('50mm', 'mount')],
    'snapshot': [
        ('original-' + unit, 'review_fix_unverified.py', ['--unit', unit, '--original', 'late'], 1800)
        for unit in ('50mm', 'mount')
    ] + [
        ('T0-' + unit, 't0_late_checks.py', ['--unit', unit], 1800)
        for unit in ('50mm', 'mount')
    ] + [
        ('race-rows', 'review_fix_checks.py', ['snapshot-race', '--unit', 'mount', '--race', 'rows'], 1800),
        ('race-T', 'review_fix_checks.py', ['snapshot-race', '--unit', '50mm', '--race', 'T'], 1800),
        ('invalid', 'review_fix_unverified.py', ['--unit', '50mm', '--transition', 'builtin-effect',
         '--timing', 'capture-invalid', '--exit', 'ok'], 1800),
        ('restore-fail', 'review_fix_unverified.py', ['--unit', 'mount', '--transition', 'builtin-effect',
         '--timing', 'restore-fail', '--exit', 'ok'], 1800),
    ],
    'apply': [
        ('apply-' + unit, 'apply_checks.py', ['--unit', unit], 2400)
        for unit in ('50mm', 'mount', '28mm')
    ] + [('error-page', 'ui_checks.py', ['error', '--unit', 'mount'], 1800)],
    'regression': [
        ('regression-50mm', 'regressions.py', ['--unit', '50mm', 'cold-none',
         'offer-ok', 't-boot', 'first-apply-readback'], 6000),
        ('regression-mount', 'regressions.py', ['--unit', 'mount', 'offer-ok',
         't-boot', 'dat-release-test', 'dat-test-release'], 6000),
        ('regression-28mm', 'regressions.py', ['--unit', '28mm', 'cold-none'], 2400),
        ('ownership', 'ui_checks.py', ['ownership', '--unit', '50mm'], 2400),
    ],
    'variants': [
        ('effect-prior', 'review_fix_checks.py', ['effect', '--unit', 'mount'], 3600),
        ('multiple-refusals', 'review_fix_checks.py', ['multiple', '--unit', '50mm'], 3600),
        ('half-reopen', 'review_fix_photo_v3.py', ['--unit', 'mount'], 3600),
    ],
}


def one(job):
    name, script, arguments, timeout = job
    argv = [sys.executable, '-I', '-B', str(HERE / 'job.py'), '--name', 'fix-' + name,
            '--timeout', str(timeout), script, *arguments]
    started = time.time_ns()
    process = subprocess.Popen(argv, cwd=ROOT)
    code = process.wait()
    assert process.poll() == code
    row = dict(name=name, argv=argv, pid=process.pid, returncode=code,
               started_ns=started, ended_ns=time.time_ns(), wait_completed=True)
    print('WAITED ' + name + ' rc=' + str(code), flush=True)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=tuple(PHASES))
    args = parser.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) == 10
    receipt_path = HERE / 'review_fix/evidence' / ('phase-' + args.phase + '.json')
    assert not receipt_path.exists()
    jobs = PHASES[args.phase]
    result = dict(phase=args.phase, started_ns=time.time_ns(), batches=[], status='RUNNING')
    try:
        for offset in range(0, len(jobs), 2):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                rows = list(pool.map(one, jobs[offset:offset+2]))
            result['batches'].append(rows)
            assert all(row['returncode'] == 0 and row['wait_completed'] for row in rows), rows
            print('BATCH EXITED ' + args.phase + ' ' + str(offset//2+1), flush=True)
        result['status'] = 'PASS'
    finally:
        result['ended_ns'] = time.time_ns()
        receipt_path.write_text(json.dumps(result, indent=2) + '\n')
    print('PHASE DONE ' + args.phase, flush=True)


if __name__ == '__main__':
    main()
