"""Run named commands serially behind the review's write fence; retain every result."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUDIO = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/g156-codec')
ENV = {**os.environ, 'PATH': str(STUDIO/'.venv/bin')+':'+os.environ['PATH'],
       'PYTHONDONTWRITEBYTECODE':'1', 'GIT_OPTIONAL_LOCKS':'0',
       'GXR_STUDIO_TEST_PARENT':str(ROOT), 'TMPDIR':str(HERE/'tmp'),
       'RUFF_CACHE_DIR':str(HERE/'cache/ruff'), 'MYPY_CACHE_DIR':str(HERE/'cache/mypy'),
       'PYLINTHOME':str(HERE/'cache/pylint'), 'XDG_CACHE_HOME':str(HERE/'cache/xdg'),
       'UV_CACHE_DIR':str(HERE/'cache/uv'), 'UV_NO_SYNC':'1', 'UV_OFFLINE':'1',
       'COVERAGE_FILE':str(HERE/'evidence/.coverage'),
       'CLANG_MODULE_CACHE_PATH':str(HERE/'cache/clang'),
       'OPENBLAS_NUM_THREADS':'1', 'OMP_NUM_THREADS':'1', 'VECLIB_MAXIMUM_THREADS':'1',
       'GXR_REQUIRE_FRONTEND':'1', 'GXR_REQUIRE_GPU_TEST':'1',
       'COREPACK_HOME':'/Users/wu/.cache/node/corepack',
       'COREPACK_ENABLE_NETWORK':'0', 'COREPACK_ENABLE_DOWNLOAD_PROMPT':'0'}

def run(name, command, timeout=1200, extra=None):
    env={**ENV, **(extra or {})}
    env.setdefault('PYTEST_ADDOPTS', f'--force-reruns 0 --maxfail=20 --basetemp={HERE}/tmp/pytest-{name} --ignore=tests/test_gpu_parity.py')
    output=HERE/'evidence'/f'{name}.log'
    suffix=2
    while output.exists():
        output=HERE/'evidence'/f'{name}-{suffix}.log'
        suffix+=1
    started=time.monotonic()
    with output.open('wb') as stream:
        try:
            code=subprocess.run(['nice','-n','15','sandbox-exec','-f',str(HERE/'readonly.sb'),*command],
                                env=env,cwd=STUDIO,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            code='TIMEOUT'
    row=dict(name=name,command=command,returncode=code,seconds=round(time.monotonic()-started,2),log=str(output.relative_to(HERE)))
    with (HERE/'evidence/checks.jsonl').open('a') as stream:
        stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps(row),flush=True)
    return row

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=('r1','make','focused','delta','remaining','fixtures'))
    stage=parser.parse_args().stage
    py=str(STUDIO/'.venv/bin/python')
    if stage=='r1':
        run('r1-audit-dat', ['/usr/bin/python3','-I','-B',str(HERE/'r1_audit_dat.py')])
        run('r1-audit-intake', [py,'-I','-B',str(HERE/'r1_audit_intake.py')])
    elif stage=='make':
        run('locked-install-dry-run',['uv','sync','--frozen','--dry-run','--offline'])
        run('make-check',['make','-j1','check'])
    elif stage=='focused':
        run('g156-all',[py,'-I','-B','-m','pytest','-q','tests/test_g156.py',
                        '--junitxml='+str(HERE/'evidence/g156-all.xml')])
    elif stage=='delta':
        run('delta-audit',[py,'-I','-B',str(HERE/'audit_delta.py')])
    elif stage=='fixtures':
        parent=HERE/'tmp/no-parent-parser'
        for package in ('g156','g156_test','g155c','g155c_test'):
            path=parent/f'firmware/package_v310_{package}/GXRCE.DAT'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes((ROOT/f'firmware/package_v310_{package}/GXRCE.DAT').read_bytes())
        run('parent-parser-absent',[py,'-I','-B','-m','pytest','-q','tests/test_g156.py','-k','round_trip or entries_match_parent'],
            extra={'GXR_STUDIO_TEST_PARENT':str(parent)})
    else:
        for name,command in (
            ('imports',['lint-imports','--no-cache']), ('deptry',['deptry','src']),
            ('vulture',['vulture','src/gxr_studio']),
            ('duplicates',['pylint','--disable=all','--enable=duplicate-code','--ignore-patterns=.*\\.pyi','src/gxr_studio']),
            ('dast',['make','-j1','dast']),
        ):
            run(name,command)
        run('full-suite',[py,'-I','-B','-m','pytest','-q','--durations=20','--cov=gxr_studio','--cov-report=term-missing','--cov-fail-under=85'],timeout=1200)

if __name__=='__main__':
    main()
