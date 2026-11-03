"""Run the requested native review cases sequentially in the foreground."""
from pathlib import Path
import datetime
import json
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, DAT, DAT_SHA, DEADLINE_UTC, save, file_sha

def commands():
    units = ('50mm', '28mm', 'mount')
    for unit in units:
        yield ('fn2_all.py', unit)
    for unit in units:
        yield ('run_native.py', 'matrix', unit)
    for unit in units:
        yield ('run_native.py', 'ah', unit)
        yield ('native_cases.py', 'h07', unit)
        for group in ('retain', 'failures', 'measure'):
            yield ('fn2_quality.py', group, unit)
        yield ('run_native.py', 'exits', unit)
        yield ('confirm_paths.py', unit)
        yield ('latch_paths.py', unit)
        yield ('native_names.py', unit)
        yield ('entry_switch.py', unit, 'fn2')
        for group in ('recovery', 'fallback', 'nested'):
            yield ('concurrent_menu.py', group, unit)
        for at in ('1', '6', '16', '17', '140'):
            yield ('concurrent_menu.py', 'other_menu', unit, '--at', at, '--reopen-fn2')
        for point in ('redraw', 'cursor_cache'):
            yield ('ui_cutpoints.py', point, unit)
        for at in ('1', '16'):
            yield ('coalescing.py', '123', unit, '--at', at)
        for at in ('1', '6'):
            yield ('failure_boundaries.py', unit, at)

def main():
    assert file_sha(DAT) == DAT_SHA
    history = []
    log_dir = OUT/'commands'
    log_dir.mkdir(exist_ok=True)
    deadline = datetime.datetime.fromisoformat(DEADLINE_UTC.replace('Z', '+00:00'))
    all_commands = list(commands())
    for index, parts in enumerate(all_commands):
        if datetime.datetime.now(datetime.timezone.utc) >= deadline:
            save('queue.json', dict(status='INCOMPLETE_TIMEBOX', commands=history,
                                    remaining=[list(p) for p in all_commands[index:]]))
            return
        label = '-'.join((str(index+1).zfill(3), *parts)).replace('.py', '').replace('--', '')
        print('RUN', index+1, '/', len(all_commands), label, flush=True)
        command = ['/usr/bin/python3', '-I', '-B', str(OUT/parts[0]), *parts[1:]]
        started = time.monotonic()
        with (log_dir/(label+'.log')).open('w') as output:
            result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
        history.append(dict(command=parts, script_sha256=file_sha(OUT/parts[0]),
                            returncode=result.returncode, seconds=time.monotonic()-started,
                            log='commands/'+label+'.log', dat_sha256=file_sha(DAT)))
        save('queue.json', dict(status='RUNNING', commands=history,
                                total=len(all_commands)))
        print('DONE', label, 'return', result.returncode, flush=True)
    save('queue.json', dict(status='PASS' if all(x['returncode']==0 for x in history) else 'FAIL',
                            commands=history, total=len(all_commands)))

if __name__ == '__main__':
    main()
