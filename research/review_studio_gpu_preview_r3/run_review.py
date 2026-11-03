"""Bounded, serial review commands. All generated state stays in the review root."""
from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import time

OUT = Path(__file__).resolve().parent
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r3')
WT = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
COPY = TMP / 'source'


def environment(isolated=True):
    env = dict(os.environ)
    for key in tuple(env):
        if key.startswith(('GXR_', 'GXR_STUDIO_', 'SENTRY_')):
            env.pop(key)
    env.update(TMPDIR=str(TMP / 'tmp'), TMP=str(TMP / 'tmp'), TEMP=str(TMP / 'tmp'),
               PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0', GH_PAGER='cat',
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1',
               NUMEXPR_NUM_THREADS='1', MAKEFLAGS='-j1', UV_NO_SYNC='1', UV_FROZEN='1',
               UV_PROJECT_ENVIRONMENT=str(WT / '.venv'),
               UV_CACHE_DIR=str(TMP / 'uv-cache'), PYLINTHOME=str(TMP / 'cache/pylint'),
               COREPACK_HOME=str(TMP / 'corepack'), COREPACK_ENABLE_NETWORK='0',
               GXR_REQUIRE_FRONTEND='1', RAYON_NUM_THREADS='1', UV_CONCURRENT_BUILDS='1',
               COVERAGE_FILE=str(TMP / '.coverage'), RUFF_CACHE_DIR=str(TMP / 'cache/ruff'),
               MYPY_CACHE_DIR=str(TMP / 'cache/mypy'), PYTEST_ADDOPTS='--force-reruns 0 --basetemp=' + str(TMP / 'pytest') + ' --junitxml=' + str(OUT / 'make-check.xml'),
               GXR_CHROME=str(OUT / 'pinned_chrome.sh'), GXR_REQUIRE_GPU_TEST='1',
               PYTHONPATH=str(COPY / 'src'), REVIEW_TMP=str(TMP), REVIEW_SOURCE=str(COPY))
    if isolated:
        env.update(HOME=str(TMP / 'home'), XDG_CACHE_HOME=str(TMP / 'cache'),
                   XDG_CONFIG_HOME=str(TMP / 'config'), XDG_DATA_HOME=str(TMP / 'data'))
        gitfile = (WT / '.git').read_text().strip()
        env.update(GIT_DIR=gitfile.removeprefix('gitdir: '), GIT_WORK_TREE=str(COPY))
    return env


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--name', required=True)
    p.add_argument('--timeout', type=int, default=900)
    p.add_argument('--network', action='store_true')
    p.add_argument('--cwd', type=Path)
    p.add_argument('command', nargs=argparse.REMAINDER)
    a = p.parse_args()
    assert 0 < a.timeout < 1800
    cmd = a.command[1:] if a.command[:1] == ['--'] else a.command
    started = time.monotonic()
    receipt = dict(command=cmd, cwd=str(a.cwd or (WT if a.network else COPY)),
                   started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   timeout_seconds=a.timeout, nice=os.getpriority(os.PRIO_PROCESS, 0))
    with (OUT / (a.name + '.log')).open('wb') as log:
        proc = subprocess.Popen(cmd, cwd=receipt['cwd'], env=environment(not a.network),
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            receipt['exit_code'] = proc.wait(timeout=a.timeout)
        except subprocess.TimeoutExpired:
            receipt['timed_out'] = True
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                receipt['exit_code'] = proc.wait(timeout=25)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                receipt['exit_code'] = proc.wait(timeout=10)
    receipt['elapsed_seconds'] = time.monotonic() - started
    (OUT / (a.name + '-receipt.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)
    lines = (OUT / (a.name + '.log')).read_text(errors='replace').splitlines()
    print('\n'.join(lines[-45:]))
    return receipt['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
