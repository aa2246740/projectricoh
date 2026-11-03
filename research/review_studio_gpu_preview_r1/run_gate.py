"""Run a bounded review command with all transient state on the approved SSD."""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import time

REPORT = pathlib.Path(__file__).resolve().parent
WORKTREE = pathlib.Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
SCRATCH = pathlib.Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r1')

def environment(name):
    env = dict(os.environ)
    for key, suffix in {
        'TMPDIR': '', 'UV_CACHE_DIR': 'uv-cache', 'RUFF_CACHE_DIR': 'ruff-cache',
        'MYPY_CACHE_DIR': 'mypy-cache', 'PYLINTHOME': 'pylint-cache', 'XDG_CACHE_HOME': 'xdg-cache',
    }.items():
        p = SCRATCH / suffix
        p.mkdir(parents=True, exist_ok=True)
        env[key] = str(p) + '/'
    env.update(PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
               VECLIB_MAXIMUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1',
               GXR_REQUIRE_FRONTEND='1', GXR_REQUIRE_GPU_TEST='1', MAKEFLAGS='-j1',
               GXR_CHROME=str(REPORT / 'pinned-chrome.sh'),
               COREPACK_HOME=str(SCRATCH / 'corepack'),
               COVERAGE_FILE=str(SCRATCH / (name + '.coverage')),
               PYTEST_ADDOPTS=f'--force-reruns 0 --basetemp={SCRATCH / (name + "-pytest")} -o cache_dir={SCRATCH / "pytest-cache"} --junitxml={REPORT / (name + ".xml")}')
    return env

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('--timeout', type=int, default=2700)
    ap.add_argument('command', nargs=argparse.REMAINDER)
    args = ap.parse_args()
    cmd = args.command[1:] if args.command[:1] == ['--'] else args.command
    start = time.monotonic()
    receipt = {'command': cmd, 'cwd': str(WORKTREE), 'started': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'load_before': os.getloadavg(), 'logical_cpus': os.cpu_count(), 'zero_reruns': True}
    with (REPORT / (args.name + '.log')).open('wb') as log:
        try:
            result = subprocess.run(cmd, cwd=WORKTREE, env=environment(args.name), stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout)
            receipt['exit_code'] = result.returncode
        except subprocess.TimeoutExpired:
            receipt['exit_code'] = 'TIMEOUT'
    receipt.update(elapsed_seconds=time.monotonic()-start, load_after=os.getloadavg(), finished=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (REPORT / (args.name + '-receipt.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
    raise SystemExit(0 if receipt['exit_code'] == 0 else 1)

if __name__ == '__main__':
    main()
