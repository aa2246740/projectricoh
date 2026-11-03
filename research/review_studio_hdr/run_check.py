"""Run the unchanged make check once, synchronously, with isolated output."""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_studio_hdr'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-hdr')

def environment():
    env = os.environ.copy()
    for name in list(env):
        if name.startswith('GXR_STUDIO_') or name.startswith('SENTRY_'):
            env.pop(name)
    env.update({
        'TMPDIR': str(TMP / 'tmp'), 'TMP': str(TMP / 'tmp'), 'TEMP': str(TMP / 'tmp'),
        'PYTHONDONTWRITEBYTECODE': '1', 'UV_OFFLINE': '1', 'UV_NO_SYNC': '1',
        'UV_CACHE_DIR': str(TMP / 'uv-cache'), 'RUFF_CACHE_DIR': str(TMP / 'ruff-cache'),
        'MYPY_CACHE_DIR': str(TMP / 'mypy-cache'), 'XDG_CACHE_HOME': str(TMP / 'cache'),
        'COVERAGE_FILE': str(TMP / 'coverage'), 'GIT_OPTIONAL_LOCKS': '0',
        'CLANG_MODULE_CACHE_PATH': str(TMP / 'clang-modules'),
        'SWIFT_MODULECACHE_PATH': str(TMP / 'swift-modules'),
        'PYTEST_ADDOPTS': '--basetemp=' + str(TMP / 'pytest-make') + ' --force-reruns 0',
        'PATH': str(TMP / 'bin') + os.pathsep + env['PATH'],
    })
    for name in ['tmp', 'uv-cache', 'ruff-cache', 'mypy-cache', 'cache', 'clang-modules', 'swift-modules']:
        (TMP / name).mkdir(exist_ok=True)
    return env

def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'make_check'
    assert label in ('make_check', 'make_check_full')
    marker = OUT / (label + '_started.json')
    if marker.exists():
        raise SystemExit('A make check run is already recorded')
    env = environment()
    argv = ['/usr/bin/sandbox-exec', '-f', str(OUT / 'review.sb'), '/usr/bin/nice', '-n', '10', '/usr/bin/make', 'check']
    record = {'utc_start': datetime.now(timezone.utc).isoformat(), 'argv': argv, 'timeout_seconds': 7200,
              'reruns': 0, 'cwd': str(ROOT / 'studio'), 'env': {k: env[k] for k in env if k in ['TMPDIR','UV_OFFLINE','UV_NO_SYNC','UV_CACHE_DIR','RUFF_CACHE_DIR','MYPY_CACHE_DIR','XDG_CACHE_HOME','COVERAGE_FILE','PYTEST_ADDOPTS','CLANG_MODULE_CACHE_PATH','SWIFT_MODULECACHE_PATH']}}
    marker.write_text(json.dumps(record, indent=2) + '\n')
    started = time.monotonic()
    with (OUT / (label + '.log')).open('xb') as log:
        child = subprocess.Popen(argv, cwd=ROOT / 'studio', env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            result = child.wait(timeout=7200)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=30)
            result = 124
    record.update({'exit_code': result, 'seconds': round(time.monotonic() - started, 3), 'utc_end': datetime.now(timezone.utc).isoformat()})
    (OUT / (label + '_result.json')).write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))
    return result

if __name__ == '__main__':
    raise SystemExit(main())
