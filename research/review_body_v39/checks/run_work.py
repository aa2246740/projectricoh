#!/usr/bin/python3 -I
"""Run one foreground workload and retain its command, log and receipt."""
from pathlib import Path
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_body_v39/evidence'
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-body-v39')
PINS = {
    'firmware/image_v39/local/ilaunch3': 'c0f8065d58e78fda09ad13580c941647a4a20d1e3225e302dbed0b05251d6f3f',
    'firmware/package_v39_g149/local/SD_ROOT/GXRCE.DAT': 'ef349e709ab14f93238a4db154c24efdeb4a0f9f209e9a6cefacbe44e6b44fe5',
    'firmware/resident_v39/local/resident/build/resident.elf': 'bb1fd856181937d32f6eed0bcacfc38b462af14ef2273bd0a9988fe52c9b743b',
    'firmware/engine_v58_g149/candidate/local/full-r13/engine.elf': 'a5d9c312ef5110402dd5ec2097c3f9dc99d874d1df6138d0701e0d84e1cf03ad',
}


def execute():
    name, limit, *command = sys.argv[1:]
    assert name.replace('-', '').replace('_', '').isalnum()
    timeout = int(limit)
    for relative, expected in PINS.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative
    receipt_path = OUT / (name + '-receipt.json')
    if receipt_path.exists():
        prior = json.loads(receipt_path.read_text())
        assert prior['command'] == command and prior['returncode'] == 0
        assert hashlib.sha256((ROOT / prior['log']).read_bytes()).hexdigest() == prior['log_sha256']
        for helper in ('batch_model.py', 'regression_check.py'):
            path = ROOT / 'research/review_body_v39/checks' / helper
            assert hashlib.sha256(path.read_bytes()).hexdigest() == prior['review_scripts'][str(path.relative_to(ROOT))]
        print(json.dumps({'event': 'completed_result', 'name': name, 'returncode': 0}), flush=True)
        return
    target = TEMP / name
    target.mkdir(parents=True, exist_ok=False)
    environment = dict(os.environ, TMPDIR=str(target), PYTHONDONTWRITEBYTECODE='1',
                       GXR_EMULATOR_BATCH='1', GIT_OPTIONAL_LOCKS='0',
                       CLANG_MODULE_CACHE_PATH=str(target / 'clang-cache'),
                       REVIEW_CASE=name, REVIEW_TEMP=str(target),
                       ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                       UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    log = OUT / (name + '.log')
    checks = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (ROOT / 'research/review_body_v39/checks').glob('*.py')}
    start = time.monotonic()
    with log.open('wb') as stream:
        process = subprocess.Popen(command, cwd=ROOT, env=environment,
                                   stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        status = 'finished'
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            status = 'timeout'
            os.killpg(process.pid, signal.SIGTERM)
            try:
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
    result = {'name': name, 'command': command, 'returncode': code,
              'status': status, 'timeout_seconds': timeout,
              'seconds': round(time.monotonic() - start, 3),
              'log': str(log.relative_to(ROOT)),
              'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
              'nice': os.getpriority(os.PRIO_PROCESS, 0), 'pid': process.pid,
              'review_scripts': checks, 'artifact_pins': PINS}
    receipt_path.write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'review_scripts'}), flush=True)
    raise SystemExit(code if code >= 0 else 1)


def main():
    name = sys.argv[1]
    assert name.replace('-', '').replace('_', '').isalnum()
    directory = TEMP / 'locks'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / (name + '.lock')).open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        execute()


if __name__ == '__main__':
    main()
