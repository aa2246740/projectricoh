#!/usr/bin/env python3
"""Finite foreground replay from the existing private sources. No jobs, sleeps, or polling."""
import sys
sys.dont_write_bytecode = True
import importlib.util
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('bw03_replay_common',HERE/'run.py')
r=importlib.util.module_from_spec(sp);sp.loader.exec_module(r)


def call(filename,*args):
    env=os.environ.copy()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
        env[key]='1'
    env['TMPDIR']='/tmp/bw03_r3'
    p=subprocess.run([sys.executable,'-I','-B',str(HERE/filename),*args],cwd=r.ROOT,env=env,
                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode:
        raise RuntimeError(f'{filename} {args} failed ({p.returncode})\n{p.stdout[-1200:]}\n{p.stderr[-2000:]}')
    last=p.stdout.strip().splitlines()
    print(last[-1] if last else f'{filename} passed',flush=True)


if __name__=='__main__':
    r.guard()
    snapshot=r.LOCAL/'input_snapshot.json'
    if snapshot.exists():
        for path,meta in r.read(snapshot).items():
            assert r.sha(r.ROOT/path)==meta['sha256'],path
    r.LOCAL.mkdir(exist_ok=True);r.TMP.mkdir(exist_ok=True)
    call('run.py','prepare');call('run.py','validate-targets')
    for role in ('full','0','1'):
        call('run.py','fit-y','--role',role)
        call('run.py','t1-cache','--role',role)
        for i in range(len(r.t1_mixes())):
            call('run.py','fit-t1','--role',role,'--index',str(i))
        call('flex.py','cache','--role',role)
        call('flex.py','solve','--role',role,'--phase','free')
        call('flex.py','solve','--role',role,'--phase','fixed')
    call('finish.py')
    for stage in ('real','synthetic','final'):
        call('verify.py','--stage',stage)
    call('finish.py');call('verify.py','--stage','hashes')
