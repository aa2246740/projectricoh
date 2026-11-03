"""Read-only review runner. All generated data stays in review or the named scratch."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
STUDIO = PROJECT / 'studio'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-g152-r1')

def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def git(*args: str) -> str:
    return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=STUDIO, env={**os.environ, 'GIT_OPTIONAL_LOCKS':'0'}).decode()

def snapshot(label: str) -> dict:
    paths = [STUDIO / p for p in git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split('\0') if p]
    value = {'head':git('rev-parse', 'HEAD').strip(), 'status':git('status', '--short', '--untracked-files=all'),
             'source':{str(p.relative_to(STUDIO)):digest(p) for p in sorted(paths) if p.is_file()},
             'git':{str(p.relative_to(STUDIO / '.git')):digest(p) for p in sorted((STUDIO / '.git').rglob('*')) if p.is_file()}}
    (HERE / f'snapshot-{label}.json').write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')
    return value

def environment() -> dict[str,str]:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0',
               UV_OFFLINE='1', UV_NO_SYNC='1', RUFF_CACHE_DIR=str(SCRATCH/'ruff'), MYPY_CACHE_DIR=str(SCRATCH/'mypy'),
               COVERAGE_FILE=str(SCRATCH/'coverage-data'), CLANG_MODULE_CACHE_PATH=str(SCRATCH/'clang'),
               XDG_CACHE_HOME=str(SCRATCH/'xdg-cache'), UV_CACHE_DIR=str(SCRATCH/'uv-cache'), PYLINTHOME=str(SCRATCH/'pylint'), MAKEFLAGS='-j1')
    for name in ('HOME','LIBRARY','EXPORT','VOLUMES'):
        env['GXR_STUDIO_'+name] = str(SCRATCH / ('isolated-'+name.lower()))
    env.pop('GXR_STUDIO_SENTRY_DSN', None)
    return env

def prepare_build_cache() -> None:
    source=Path('/Users/wu/.cache/uv')
    target=SCRATCH/'uv-cache'
    for package in ('hatchling','packaging','pathspec','pluggy','tomlkit','trove-classifiers'):
        simple=target/'simple-v17/pypi'/f'{package}.rkyv'
        simple.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source/'simple-v17/pypi'/simple.name,simple)
        wheels=source/'wheels-v5/pypi'/package
        dest=target/'wheels-v5/pypi'/package
        dest.mkdir(parents=True,exist_ok=True)
        for path in wheels.iterdir():
            if path.is_symlink():
                original=path.resolve()
                archive=target/'archive-v0'/original.name
                shutil.copytree(original,archive,dirs_exist_ok=True)
                link=dest/path.name
                if link.is_symlink(): link.unlink()
                link.symlink_to(archive)
            elif path.is_file(): shutil.copy2(path,dest/path.name)

def run(name: str, args: list[str], timeout: int=1200, env: dict[str,str]|None=None, cwd: Path=STUDIO) -> dict:
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    begin=time.monotonic()
    log=HERE/(name+'.log')
    timed_out=False
    with log.open('wb') as f:
        actual_args=args if os.getpriority(os.PRIO_PROCESS,0)>=10 else ['nice','-n','10',*args]
        proc=subprocess.Popen(actual_args,cwd=cwd,env=env or environment(),stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            code=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True
            os.killpg(proc.pid,signal.SIGTERM)
            try: code=proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL)
                code=proc.wait(timeout=10)
    result={'name':name,'command':args,'cwd':str(cwd),'started_utc':started,'seconds':round(time.monotonic()-begin,3),
            'exit_code':code,'timeout':timed_out,'nice':10,'log':log.name,'log_sha256':digest(log)}
    (HERE/(name+'.json')).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result

def main() -> None:
    if sys.argv[1]=='snapshot':
        value=snapshot(sys.argv[2]); print(json.dumps({'source_files':len(value['source']),'git_files':len(value['git']),'head':value['head']},ensure_ascii=False)); return
    if sys.argv[1]=='check':
        env=environment()
        prepare_build_cache()
        shell=SCRATCH/'check-shell'
        shell.write_text('#!/bin/sh\nif [ "$1" = "-c" ] && [ "$2" = "uv run --frozen lint-imports" ]; then\nexec /bin/sh -c \'uv run --frozen lint-imports --cache-dir '+str(SCRATCH/'import-linter')+'\'\nfi\nexec /bin/sh "$@"\n')
        shell.chmod(0o700)
        env['PYTEST_ADDOPTS']='--force-reruns 0 --basetemp='+str(SCRATCH/'pytest-check')+' --junitxml='+str(HERE/'pytest-check.xml')+' --cov-report=json:'+str(HERE/'coverage-full.json')
        r=run('make-check',['make','check','SHELL='+str(shell)],timeout=1600,env=env)
        raise SystemExit(r['exit_code'])
    name=sys.argv[1]
    r=run(name,sys.argv[2:],timeout=1200)
    raise SystemExit(r['exit_code'])

if __name__=='__main__': main()
