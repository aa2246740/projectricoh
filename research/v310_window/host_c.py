#!/usr/bin/python3
"""Run the existing resident C acceptance groups without changing their assertions."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_window'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1')
GROUPS='caps handshake disabled epochs h09 h10 image restore lane check header discard'.split()


def run(name):
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    out=HERE/'evidence'/name;out.mkdir(parents=True,exist_ok=True)
    work=TEMP/'host-c'/name
    if work.exists():shutil.rmtree(work)
    resident=work/'resident'
    shutil.copytree(ROOT/'firmware/resident_v310_proto/options'/name/'resident',resident)
    services=work/'candidate/engine_services'
    shutil.copytree(ROOT/'firmware/resident_v310_proto/engine_services',services)
    binary=work/'host_v39'
    args=['clang','-std=c11','-O1','-g','-Wall','-Wextra','-Wno-unused-function','-Wno-unused-parameter',
          '-Wno-unknown-attributes','-D_FORTIFY_SOURCE=0','-U__OPTIMIZE__',
          '-fsanitize=address,undefined','-fno-sanitize-recover=all','-DRV_HOST',
          '-I'+str(resident),'-I'+str(services),str(ROOT/'research/body_v39/tests/host_v39.c')]
    args += [str(resident/(n+'.c'))for n in ['resident','shared','hooks','loader','validate_envelope.inc']]
    args += [str(services/(n+'.c'))for n in ['services','api','native_seed']]
    args += ['-o',str(binary)]
    start=time.monotonic()
    proc=subprocess.run(['/usr/bin/nice','-n','10',*args],cwd=ROOT,capture_output=True,text=True,timeout=1800)
    (out/'host-c-compile.log').write_text(proc.stdout+proc.stderr)
    assert proc.returncode==0,proc.stderr[-2000:]
    results=[];lines=[]
    for group in GROUPS:
        proc=subprocess.run(['/usr/bin/nice','-n','10',str(binary),group],cwd=ROOT,
                            env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                                     UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'),
                            capture_output=True,text=True,timeout=1800)
        (out/('host-c-'+group+'.log')).write_text(proc.stdout+proc.stderr)
        results.append(dict(group=group,returncode=proc.returncode,lines=len(proc.stdout.splitlines())))
        lines+=proc.stdout.splitlines()
        assert proc.returncode==0,(name,group,proc.stderr[-2000:])
    (out/'host-c.jsonl').write_text('\n'.join(lines)+'\n')
    result=dict(status='PASS',name=name,groups=results,lines=len(lines),seconds=time.monotonic()-start,
                nice=os.getpriority(os.PRIO_PROCESS,0),timeout=1800,
                assertions_source='research/body_v39/tests/host_v39.c')
    if name!='baseline':
        baseline=(HERE/'evidence/baseline/host-c.jsonl').read_text()
        assert baseline=='\n'.join(lines)+'\n'
        result['baseline_output_equal']=True
    (out/'host-c.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(name=name,status='PASS',groups=len(GROUPS),lines=len(lines),seconds=round(result['seconds'],3))),flush=True)


if __name__=='__main__':
    for name in __import__('sys').argv[1:]:run(name)
