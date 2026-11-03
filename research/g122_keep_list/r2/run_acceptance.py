"""Run the missing commands and functional groups; retain each real exit."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(OUT))
from common import DAT, TREE, file_sha, save

PIN = '9724268c3d8a2c8c60650b903db1d536ca6ab594f95144d5991cb3b964ebb262'
DEADLINE = datetime.datetime.fromisoformat('2026-10-28T09:39:00+00:00')
UNITS = ('50mm', '28mm', 'mount')
baseline = json.loads((HERE / 'before/acceptance.json').read_text())

def now():
    return datetime.datetime.now(datetime.timezone.utc)

def one_unit(unit):
    missing = [r['command'] for r in baseline['remaining_commands'][unit] if r['record'] is None]
    assert len(missing) == 22
    extras = [['allocation_cases.py', unit], ['notice_cases.py', unit],
              ['bounded_moves.py', unit], ['keep_cases.py', unit, '--rerun']]
    commands = missing + extras
    records = []
    for index, parts in enumerate(commands):
        if now() >= DEADLINE:
            break
        assert file_sha(DAT) == PIN
        label = unit + '-' + str(index + 1).zfill(2) + '-' + '-'.join(parts).replace('.py', '')
        log = HERE / 'logs' / (label + '.log')
        log.parent.mkdir(exist_ok=True)
        dependency_paths = sorted(p for p in OUT.glob('*.py')) + [HERE / 'run_one.py']
        sources = {str(p.relative_to(ROOT)):file_sha(p) for p in dependency_paths}
        argv = ['/usr/bin/python3', '-I', '-B', str(HERE / 'run_one.py'), *parts]
        start = now(); tick = time.monotonic()
        print('RUN', unit, index + 1, '/', len(commands), parts, flush=True)
        with log.open('w') as stream:
            result = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=max(1, (DEADLINE - now()).total_seconds()))
        text = log.read_text()
        assert 'REUSE completed' not in text and 'PASS existing' not in text, parts
        stable = all(file_sha(ROOT / name) == digest for name,digest in sources.items())
        record = dict(command=parts, argv=argv, cwd=str(ROOT), returncode=result.returncode,
                      seconds=time.monotonic()-tick, started_utc=start.isoformat(), ended_utc=now().isoformat(),
                      dat_sha256=file_sha(DAT), source_sha256=sources, sources_unchanged=stable,
                      log=str(log.relative_to(OUT)), log_sha256=file_sha(log), reused=False)
        records.append(record)
        save('r2/commands-' + unit + '.json', dict(unit=unit, dat_sha256=PIN, total=26,
             status='RUNNING', commands=records))
        print('DONE', unit, index + 1, 'rc', result.returncode, 'seconds', round(record['seconds'], 1), flush=True)
    status = 'PASS' if len(records)==26 and all(r['returncode']==0 and r['sources_unchanged'] for r in records) else 'FAIL' if any(r['returncode'] for r in records) else 'INCOMPLETE_TIMEBOX'
    save('r2/commands-' + unit + '.json', dict(unit=unit, dat_sha256=PIN, total=26, status=status, commands=records))
    return unit,status

def main():
    if (HERE/'scope-stop.json').exists():
        raise SystemExit('STOPPED_USER_SCOPE: gen 122 regression dispatch was cancelled by the user.')
    assert file_sha(DAT) == PIN
    # Each unit has its own output names and decode directory. The main process
    # waits for all foreground subprocesses; this is not agent delegation.
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(one_unit, UNITS))
    save('r2/queue.json', dict(status='PASS' if all(s=='PASS' for _,s in results) else 'FAIL', units=dict(results), dat_sha256=PIN))
    print('FINISHED',results,flush=True)

if __name__ == '__main__':
    main()
