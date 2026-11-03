"""Serial, bounded local verification with task-owned state and receipts."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

OUT = Path(__file__).resolve().parent
WORKTREE = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/studio-gpu-fix-r3')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name')
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert 0 < args.timeout <= 1500
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    assert command
    SCRATCH.mkdir(parents=True, exist_ok=True)
    isolated_home = SCRATCH / 'home'
    isolated_home.mkdir(exist_ok=True)
    env = dict(os.environ)
    for key in tuple(env):
        if key.startswith(('GXR_', 'SENTRY_')):
            env.pop(key)
    uv_cache = subprocess.check_output(['uv', 'cache', 'dir'], cwd=WORKTREE, env=env, text=True).strip()
    corepack_home = env.get('COREPACK_HOME') or str(Path(env.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'node/corepack')
    env.update(
        TMPDIR=str(SCRATCH) + '/', TEMP=str(SCRATCH), TMP=str(SCRATCH), HOME=str(isolated_home),
        UV_CACHE_DIR=uv_cache,
        COREPACK_HOME=corepack_home, COREPACK_ENABLE_NETWORK='0',
        PYTHONDONTWRITEBYTECODE='1', MAKEFLAGS='-j1',
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1',
        UV_NO_SYNC='1', UV_FROZEN='1',
        COVERAGE_FILE=str(SCRATCH / '.coverage'),
        RUFF_CACHE_DIR=str(SCRATCH / 'cache/ruff'), MYPY_CACHE_DIR=str(SCRATCH / 'cache/mypy'),
        PYLINTHOME=str(SCRATCH / 'cache/pylint'),
        GXR_CHROME=str(OUT / 'pinned_chrome.sh'),
        GXR_REQUIRE_FRONTEND='1', GXR_REQUIRE_GPU_TEST='1',
        PYTEST_ADDOPTS='--force-reruns 0 --basetemp=' + str(SCRATCH / ('pytest-' + args.name)) + ' --junitxml=' + str(OUT / (args.name + '.xml')),
        REVIEW_SOURCE=str(WORKTREE), REVIEW_TMP=str(SCRATCH / ('review-' + args.name)), REVIEW_OUT=str(OUT),
    )
    Path(env['REVIEW_TMP']).mkdir(exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=WORKTREE, text=True).strip()
    started = time.monotonic()
    receipt = dict(command=command, head=head, cwd=str(WORKTREE), timeout_seconds=args.timeout,
                   started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   nice=os.getpriority(os.PRIO_PROCESS, 0), automatic_reruns=0)
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=WORKTREE).decode().split('\0')
    before = {name: hashlib.sha256((WORKTREE / name).read_bytes()).hexdigest()
              for name in tracked if name and (WORKTREE / name).is_file()}
    with (OUT / (args.name + '.log')).open('wb') as log:
        process = subprocess.Popen(command, cwd=WORKTREE, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            receipt['exit_code'] = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            receipt['timed_out'] = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
            receipt['exit_code'] = process.returncode
    after = {name: hashlib.sha256((WORKTREE / name).read_bytes()).hexdigest()
             for name in before if (WORKTREE / name).is_file()}
    receipt.update(elapsed_seconds=time.monotonic() - started, source_hashes_unchanged=before == after,
                   changed_sources=[name for name in before if before[name] != after.get(name)])
    (OUT / (args.name + '-receipt.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
    raise SystemExit(receipt['exit_code'] if before == after else 2)


if __name__ == '__main__':
    main()
