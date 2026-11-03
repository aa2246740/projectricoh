"""Run one unit's final-DAT acceptance commands in the foreground."""
from pathlib import Path
import datetime
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, DAT, file_sha, save
from run_queue import commands

def main(unit):
    assert unit in ('50mm', '28mm', 'mount')
    fixed_sha = file_sha(DAT)
    selected = [('first_open.py', unit)]
    selected += [parts for parts in commands() if unit in parts and
                 parts[0] != 'fn2_all.py' and parts[:2] != ('run_native.py', 'matrix')]
    selected += [('open_counts.py', unit)]
    selected += [('recovery_cases.py', unit),
        ('field_cases.py', unit, '--only', 'fn2_right_left', 'disp', 'panel_keys',
         'prewrite_busy', 'partial_busy', 'row_reset', 'ready_busy',
         'capture_exit', 'capture_open', 'capture_after_fn2'),
        ('boundary_cases.py', unit), ('allocation_cases.py', unit),
        ('notice_cases.py', unit), ('bounded_moves.py', unit), ('list_counts.py', unit)]
    selected += [('run_native.py', 'matrix', unit), ('fn2_all.py', unit)]
    records = []
    folder = OUT / 'commands'
    folder.mkdir(exist_ok=True)
    deadline = datetime.datetime.fromisoformat('2026-10-28T06:41:22+00:00')
    for index, parts in enumerate(selected):
        remaining = (deadline - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        if remaining <= 0:
            break
        assert file_sha(DAT) == fixed_sha
        label = unit + '-' + str(index + 1).zfill(2) + '-' + parts[0].removesuffix('.py')
        log = folder / (label + '.log')
        print('RUN', label, list(parts[1:]), flush=True)
        started = time.monotonic()
        code = None
        try:
            with log.open('w') as output:
                result = subprocess.run(['/usr/bin/python3', '-I', '-B', str(OUT / parts[0]), *parts[1:]],
                    cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=remaining)
                code = result.returncode
        except subprocess.TimeoutExpired:
            code = 'TIMEBOX'
        assert file_sha(DAT) == fixed_sha
        records.append(dict(command=parts, returncode=code, seconds=time.monotonic() - started,
            script_sha256=file_sha(OUT / parts[0]), dat_sha256=fixed_sha,
            log=str(log.relative_to(OUT))))
        save('unit-' + unit + '.json', dict(status='RUNNING', unit=unit, dat_sha256=fixed_sha,
             commands=records, total=len(selected)))
        print('DONE', label, code, flush=True)
    save('unit-' + unit + '.json', dict(status='PASS' if len(records) == len(selected) and
         all(x['returncode'] == 0 for x in records) else 'INCOMPLETE_OR_FAILED', unit=unit,
         dat_sha256=fixed_sha, commands=records, total=len(selected), remaining=selected[len(records):]))

if __name__ == '__main__':
    main(sys.argv[1])
