#!/usr/bin/python3
"""Run requested checks serially, with bounded foreground processes and saved logs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_window'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1')


def run(label,script,args,confirm=False):
    directory=HERE/'jobs';directory.mkdir(exist_ok=True)
    log=directory/(label+'.log');receipt=directory/(label+'.json')
    command=['/usr/bin/nice','-n','10','/usr/bin/sandbox-exec','-f',str(HERE/'offline.sb'),
             '/usr/bin/python3','-I','-B',str(HERE/script),*args]
    start=time.monotonic()
    env=dict(os.environ,TMPDIR=str(TEMP),PYTHONDONTWRITEBYTECODE='1',GXR_EMULATOR_BATCH='1')
    with log.open('w') as stream:
        try:
            p=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=1800)
            code=p.returncode
        except subprocess.TimeoutExpired:
            code=124
    row=dict(label=label,argv=command,returncode=code,seconds=time.monotonic()-start,timeout=1800,
             nice=os.getpriority(os.PRIO_PROCESS,0),log=str(log.relative_to(ROOT)))
    receipt.write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps({k:row[k]for k in ['label','returncode','seconds']}),flush=True)
    if code and confirm:
        alternative=[*args,'--side','python']
        run(label+'-python-confirm',script,alternative,confirm=False)
    if code:raise RuntimeError(label+' failed; see '+str(log))


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['host','flow','routes','dirty','validation','cold','recovery','card'])
    p.add_argument('names',nargs='*');args=p.parse_args()
    names=args.names or ['baseline','root_shared','word_scan','aligned_reads','compiler','aligned_compiler','neutral']
    for name in names:
        if args.stage=='host':run('host-'+name,'host_c.py',[name])
        elif args.stage=='flow':
            for unit in ['50mm','28mm','mount']:
                run('flow-'+name+'-'+unit,'harness_check.py',[name,'--unit',unit],confirm=True)
        elif args.stage=='routes':
            for case in ['irom','fallback','identity','file-crc']:
                run(case+'-'+name,'harness_check.py',[name,'--case',case],confirm=True)
        elif args.stage=='dirty':run('dirty-'+name,'harness_check.py',[name,'--case','dirty'],confirm=True)
        elif args.stage=='validation':run('validation-'+name,'validation_check.py',[name],confirm=True)
        elif args.stage=='cold':run('cold-'+name,'cold_check.py',[name])
        elif args.stage=='recovery':run('recovery-'+name,'recovery_check.py',[name])
        elif args.stage=='card':
            for case in ['flow','irom','fallback']:
                run('card-'+case+'-'+name,'harness_check.py',[name,'--case',case],confirm=True)


if __name__=='__main__':main()
