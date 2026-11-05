"""Run CI commands serially, retaining failures and a write fence. No sync/install mutations."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUDIO = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/g156-codec')
ENV = {**os.environ,
       'PATH':str(STUDIO/'.venv/bin')+':'+os.environ['PATH'],
       'PYTHONDONTWRITEBYTECODE':'1', 'GIT_OPTIONAL_LOCKS':'0',
       'GXR_STUDIO_TEST_PARENT':str(ROOT), 'TMPDIR':str(HERE/'tmp'),
       'RUFF_CACHE_DIR':str(HERE/'cache/ruff'), 'MYPY_CACHE_DIR':str(HERE/'cache/mypy'),
       'PYLINTHOME':str(HERE/'cache/pylint'), 'XDG_CACHE_HOME':str(HERE/'cache/xdg'),
       'UV_CACHE_DIR':str(HERE/'cache/uv'), 'UV_NO_SYNC':'1', 'UV_OFFLINE':'1',
       'COVERAGE_FILE':str(HERE/'evidence/.coverage'),
       'CLANG_MODULE_CACHE_PATH':str(HERE/'cache/clang'),
       'OPENBLAS_NUM_THREADS':'1', 'OMP_NUM_THREADS':'1', 'VECLIB_MAXIMUM_THREADS':'1',
       'GXR_REQUIRE_FRONTEND':'1','GXR_REQUIRE_GPU_TEST':'1',
       'PYTEST_ADDOPTS':f'--force-reruns 0 --maxfail=10 --basetemp={HERE}/tmp/pytest-ci --ignore=tests/test_gpu_parity.py'}


def run(name, command, timeout=2400, extra=None):
    env = {**ENV, **(extra or {})}
    start = time.monotonic()
    log_path = HERE/'evidence'/f'{name}.log'
    if log_path.exists():
        index = 2
        while (HERE/'evidence'/f'{name}-{index}.log').exists():
            index += 1
        log_path = HERE/'evidence'/f'{name}-{index}.log'
    # Each command owns a different pytest root, including concurrently invoked stages.
    if not extra or 'PYTEST_ADDOPTS' not in extra:
        env['PYTEST_ADDOPTS'] = (f'--force-reruns 0 --maxfail=10 '
                                f'--basetemp={HERE}/tmp/pytest-{log_path.stem} '
                                '--ignore=tests/test_gpu_parity.py')
    with log_path.open('wb') as log:
        try:
            done = subprocess.run(['sandbox-exec','-f',str(HERE/'readonly.sb'),*command],
                                  cwd=STUDIO,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
            code = done.returncode
        except subprocess.TimeoutExpired:
            code = 'TIMEOUT'
    row = dict(name=name,command=command,returncode=code,seconds=round(time.monotonic()-start,2),
               log=str(log_path.relative_to(HERE)))
    with (HERE/'evidence/checks.jsonl').open('a') as log:
        log.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps(row),flush=True)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('initial','remaining','g156-pure','g156-all','dast','seed-build-cache','retry-make','dist','fixture-probes','gpu','frontend-copy','frontend-linked'))
    stage = parser.parse_args().stage
    if stage == 'seed-build-cache':
        cache = Path('/Users/wu/.cache/uv')
        for package in ('hatchling','packaging','pathspec','pluggy','tomlkit','trove-classifiers'):
            source = cache/'wheels-v5/pypi'/package
            destination = HERE/'cache/uv/wheels-v5/pypi'/package
            shutil.copytree(source,destination,symlinks=False,dirs_exist_ok=True)
            for entry in source.iterdir():
                if entry.is_symlink():
                    archive = entry.resolve()
                    shutil.copytree(archive,HERE/'cache/uv/archive-v0'/archive.name,dirs_exist_ok=True)
            metadata = cache/'simple-v17/pypi'/f'{package}.rkyv'
            target = HERE/'cache/uv/simple-v17/pypi'/metadata.name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(metadata,target)
        print('Copied only six cached build requirements; original cache is unchanged.')
    elif stage == 'retry-make':
        run('make-check-warm-cache',['make','-j1','check'])
    elif stage == 'initial':
        run('locked-install-dry-run',['uv','sync','--frozen','--dry-run','--offline'])
        run('make-check',['make','-j1','check'])
    elif stage == 'remaining':
        for name, command in (
            ('private-bytes-tracked',['python','-B','scripts/private_bytes.py','--tracked']),
            ('dead-flags',['python','-B','scripts/dead_flags.py']),
            ('agents-contract',['python','-B','scripts/check_agents_md.py']),
            ('large-files',['python','-B','scripts/large_files.py']),
            ('openapi',['python','-B','scripts/export_openapi.py','--check']),
            ('frontend',['python','-B','scripts/check_frontend.py']),
            ('imports',['lint-imports','--no-cache']),
            ('deptry',['deptry','src']),
            ('vulture',['vulture','src/gxr_studio']),
            ('duplicates',['pylint','--disable=all','--enable=duplicate-code','--ignore-patterns=.*\\.pyi','src/gxr_studio']),
        ):
            run(name,command)
        run('full-suite',['python','-B','-m','pytest','-q','--durations=20','--cov=gxr_studio',
                          '--cov-report=term-missing','--cov-fail-under=85'])
    elif stage == 'g156-pure':
        run('g156-pure',['python','-B','-m','pytest','-q','tests/test_g156.py',
                        '-k','not original_template and not file_and_upload',
                        '--junitxml='+str(HERE/'evidence/g156-pure.xml')])
    elif stage == 'g156-all':
        run('g156-all',['python','-B','-m','pytest','-q','tests/test_g156.py',
                       '--junitxml='+str(HERE/'evidence/g156-all.xml')])
    elif stage == 'dist':
        run('private-bytes-dist',['python','-B','scripts/private_bytes.py','--tracked','--dist'])
    elif stage == 'fixture-probes':
        parent = HERE/'tmp/no-helper-parent'
        for package in ('g156','g156_test','g155c','g155c_test'):
            dest = parent/f'firmware/package_v310_{package}/GXRCE.DAT'
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/f'firmware/package_v310_{package}/GXRCE.DAT',dest)
        run('dat-present-helper-absent',['python','-B','-m','pytest','-q','tests/test_g156.py',
                '-k','real_dat_round_trip'],extra={'GXR_STUDIO_TEST_PARENT':str(parent)})
        dest = parent/'firmware/package_v310_g156/GXRCE.DAT'
        data = bytearray(dest.read_bytes()); data[-1] ^= 1; dest.write_bytes(data)
        run('dat-present-bad-digest',['python','-B','-m','pytest','-q',
                'tests/test_g156.py::test_user_edit_keeps_banks_and_native_records[g156]'],
                extra={'GXR_STUDIO_TEST_PARENT':str(parent)})
    elif stage == 'gpu':
        run('pinned-gpu-parity',['python','-B','-m','pytest','-q','tests/test_gpu_parity.py','-p','pinned_gpu_plugin'],
            timeout=600,extra={'PYTHONPATH':str(HERE),
                'PYTEST_ADDOPTS':f'--force-reruns 0 --maxfail=1 --basetemp={HERE}/tmp/pytest-gpu'})
    elif stage in ('frontend-copy','frontend-linked'):
        linked = stage == 'frontend-linked'
        dest = HERE/('frontend-copy-linked' if linked else 'frontend-copy')
        if not dest.exists():
            shutil.copytree(STUDIO/'frontend',dest,symlinks=linked)
        code = f"import importlib.util; spec=importlib.util.spec_from_file_location('checker',{str(STUDIO/'scripts/check_frontend.py')!r}); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); m.FRONTEND=m.Path({str(dest)!r}); raise SystemExit(m.main())"
        run(stage,['python','-B','-c',code],extra={
            'COREPACK_HOME':'/Users/wu/.cache/node/corepack',
            'COREPACK_ENABLE_NETWORK':'0','COREPACK_ENABLE_DOWNLOAD_PROMPT':'0'})
    else:
        run('dast',['make','-j1','dast'])


if __name__ == '__main__':
    main()
