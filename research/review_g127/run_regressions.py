#!/usr/bin/python3
"""Run retained groups with three workers and retain count summaries."""
from pathlib import Path
import argparse
import concurrent.futures
import datetime
import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g127'
WORK = ROOT / 'research/g127_fix'
PIN = '9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6'
DAT = ROOT / 'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT'
PY = ['/usr/bin/python3', '-I', '-B']
LIMIT = 4200
DEADLINE = datetime.datetime(2026, 10, 28, 22, 36, tzinfo=datetime.timezone.utc).timestamp()
GROUPS = {
    'safety': ['safety_cases.py'], 'locked': ['locked_cases.py'],
    'nested': ['lock_nested.py', '--cuts', 'record_failure_return', 'after_update_restore', 'before_redraw', 'row_draw'],
    'cutpoints': ['lock_cutpoints.py', '--irq-enabled'], 'exits': ['lock_exits.py'],
    'transitions': ['ui_acceptance.py', 'transitions'], 'values': ['ui_acceptance.py', 'values'],
    'view-reentry': ['view_reentry.py'], 'reentry-six': ['reentry_all_keys.py'],
    'users': ['user_acceptance.py'], 'other-users': ['other_users.py'],
    'project': ['project_boundary.py'], 'labels': ['label_acceptance.py'],
    'half': ['official_half.py', '--hook-trace'],
}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def preflight():
    assert not __import__('sys').flags.optimize
    assert digest(DAT) == PIN and DAT.stat().st_size == 58772
    rows = []
    for family in (124, 126):
        path = WORK / f'local/release127/review_g{family}/evidence/user-tool.json'
        value = json.loads(path.read_text())
        fixture = ROOT / value['fixture']
        assert value['status'] == 'PASS' and value['base_dat_sha256'] == PIN
        assert digest(fixture) == value['fixture_sha256']
        raw = fixture.read_bytes()
        original = DAT.read_bytes()
        size = int.from_bytes(original[136:140], 'big')
        assert raw[256:256+size] == original[256:256+size]
        rows.append(dict(family=family, ready=True, base_dat_sha256=PIN,
                         fixture=str(fixture.relative_to(ROOT)), fixture_sha256=digest(fixture),
                         engine_bytes_equal=True))
    (OUT / 'preflight.json').write_text(json.dumps(rows, indent=2) + '\n')

def jobs():
    control = ['--postcheck', 'research/g127_fix/ownership_reopen.py',
               'research/review_g126/ownership_settings.py', '--generation', '127', '--unit', '50mm']
    yield dict(name='crc-settings-fast', kind='crc', fast=True, args=control)
    yield dict(name='crc-settings-native', kind='crc', fast=False, args=control)
    for mode in ('flag','default','native'):
        yield dict(name='crc-route-'+mode, kind='native', fast=False, direct=True,
                   args=['research/review_g127/native_checks.py','--case','crc-settings','--crc-mode',mode])
    for unit in ('50mm','28mm','mount'):
        for case in ('preview-window','settings-check','h07-parent'):
            yield dict(name=case+'-'+unit, kind='native', fast=False, direct=True,
                       args=['research/review_g127/native_checks.py','--case',case,'--unit',unit])
    yield dict(name='history123-50mm', kind='history123', fast=True,
               args=['research/review_g123/run_cases.py', 'suite', '--generation', '127', '--unit', '50mm'])
    yield dict(name='settings_cases-50mm', kind='settings_cases', fast=True,
               args=['research/review_g126/settings_cases.py', '--unit', '50mm'])
    values = json.loads((WORK / 'evidence/acceptance.json').read_text())['groups']
    for item in values:
        if item['complete']:
            continue
        family, unit, group = item['family'], item['unit'], item['group']
        script, *rest = GROUPS[group]
        args = [f'research/review_g{family}/{script}', *rest]
        args += [unit] if group == 'locked' else ['--unit', unit]
        yield dict(name=f'group{family}-{unit}-{group}', kind='group', fast=True,
                   family=family, unit=unit, group=group, args=args)
    for unit in ('28mm', 'mount'):
        yield dict(name='history123-'+unit, kind='history123', fast=True,
                   args=['research/review_g123/run_cases.py', 'suite', '--generation', '127', '--unit', unit])
        yield dict(name='settings_cases-'+unit, kind='settings_cases', fast=True,
                   args=['research/review_g126/settings_cases.py', '--unit', unit])

def run(job):
    start = time.monotonic()
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cmd = ['/usr/bin/sandbox-exec', '-f', str(OUT / 'write-fence.sb'), *PY]
    if not job.get('direct'):
        cmd.append(str(WORK / 'run_existing.py'))
    if job['fast']:
        cmd.append('--fast-crc')
    cmd += job['args']
    if time.time() >= DEADLINE:
        return dict(job, returncode=None, seconds=0, status='NOT_STARTED', PASS=0, FAIL=0, command=cmd)
    env = dict(os.environ, TMPDIR=str(WORK / 'local/tmp'), PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=True)
    try:
        raw = proc.communicate(timeout=min(LIMIT, max(1, DEADLINE-time.time())))[0]
        code = proc.returncode
        state = 'FINISHED'
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            raw = proc.communicate(timeout=10)[0]
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            raw = proc.communicate()[0]
        code = 124
        state = 'TIMEBOX' if time.time() >= DEADLINE else 'TIMEOUT'
    text = raw.decode('utf-8', errors='replace')
    counts = {word:len(re.findall(r'\b'+word+r'\b', text)) for word in ('PASS', 'FAIL', 'OBSERVED')}
    if job.get('direct'):
        for line in text.splitlines():
            try:
                parsed=json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed,dict) and all(key in parsed for key in counts):
                counts={key:parsed[key] for key in counts}
    row = dict(job, returncode=code, seconds=round(time.monotonic()-start, 3),
               status=state, started_utc=stamp, command=cmd, dat_sha256=digest(DAT),
               output_counts=counts, output_bytes=len(raw), reused=('Already ' in text))
    assert row['dat_sha256'] == PIN
    (OUT / 'runs' / (job['name']+'.json')).write_text(json.dumps(row, indent=2) + '\n')
    return row

def main():
    global DEADLINE
    parser=argparse.ArgumentParser()
    parser.add_argument('--deadline-utc')
    args=parser.parse_args()
    if args.deadline_utc:
        value=datetime.datetime.fromisoformat(args.deadline_utc)
        if value.tzinfo is None:
            parser.error('deadline needs an explicit timezone')
        DEADLINE=value.timestamp()
    (OUT / 'runs').mkdir(parents=True, exist_ok=True)
    lock=(OUT/'coordinator.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    preflight()
    finished=set()
    for path in (OUT/'runs.jsonl',OUT/'priority-batch-runs.jsonl'):
        if path.exists():
            finished.update(json.loads(line)['name'] for line in path.read_text().splitlines()
                            if json.loads(line).get('returncode')==0)
    pending = [job for job in jobs() if job['name'] not in finished]
    (OUT / 'plan.json').write_text(json.dumps(dict(workers=3, timeout_seconds=LIMIT,
        deadline_utc=datetime.datetime.fromtimestamp(DEADLINE, datetime.timezone.utc).isoformat(),
        jobs=pending), indent=2) + '\n')
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        work = {pool.submit(run, job):job for job in pending}
        for future in concurrent.futures.as_completed(work):
            row = future.result()
            with (OUT / 'runs.jsonl').open('a') as stream:
                stream.write(json.dumps(row) + '\n')
            print(json.dumps({key:row.get(key) for key in ('name','returncode','seconds','output_counts','status','reused')}), flush=True)

if __name__ == '__main__':
    main()
