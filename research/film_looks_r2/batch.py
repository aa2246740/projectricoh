"""Load-gated, restartable batches. Workers independently obtain a shared lease."""
import argparse
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

assert sys.flags.isolated
HERE=Path(__file__).resolve().parent
LOCAL=HERE/'local'
UNITS=('a12-50','a12-28','mount-a12')


def load1():
    line=subprocess.check_output(['/usr/bin/uptime'],text=True).strip()
    match=re.search(r'load averages?:\s*([\d.]+)',line)
    if not match:raise RuntimeError('Cannot parse uptime: '+line)
    return float(match[1]),line


def main():
    if os.getpriority(os.PRIO_PROCESS,0)<15:
        os.nice(15-os.getpriority(os.PRIO_PROCESS,0))
    assert os.getpriority(os.PRIO_PROCESS,0)==15
    p=argparse.ArgumentParser();p.add_argument('--stage',default='acros',choices=('acros',))
    p.add_argument('--max-workers',type=int,default=2);args=p.parse_args()
    assert 1<=args.max_workers<=6
    jobs={}
    prior=None
    for stage in ('prepare',):
        jobs[stage]=dict(command=['acros.py',stage],out=LOCAL/'acros_profiles.json',deps=[])
        prior=stage
    for unit in UNITS:
        prior='prepare'
        for stage,nfev in (('iterate',160),('exact',400),('assess',0)):
            key=unit+'-'+stage
            out=LOCAL/('assessment' if stage=='assess' else 'fits')/unit/'14'/((stage+'.json') if stage!='assess' else '.unused')
            if stage=='assess':out=LOCAL/'assessment'/unit/'14.json'
            jobs[key]=dict(command=['acros.py',stage,'--unit',unit]+(['--nfev',str(nfev)] if nfev else []),out=out,deps=[prior])
            prior=key
    receipt=[];running={};failed=set();last_defer=0
    logdir=LOCAL/'logs';logdir.mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        while True:
            for key,future in list(running.items()):
                if not future.done():continue
                row=future.result();receipt.append(row);del running[key]
                print('FINISH',key,'exit',row['exit_code'],flush=True)
                if row['exit_code'] not in (0,75):failed.add(key)
            pending=[key for key,job in jobs.items() if not job['out'].exists() and key not in running and key not in failed]
            if not pending and not running:break
            if failed and not running:break
            load,line=load1();limit=0 if load>10 else min(args.max_workers,6 if load<5 else 2)
            available=[key for key in pending if all(jobs[d]['out'].exists() for d in jobs[key]['deps'])]
            while available and len(running)<limit:
                key=available.pop(0);job=jobs[key]
                command=[sys.executable,'-I','-B',str(HERE/job['command'][0]),*job['command'][1:]]
                log=logdir/(key+'-'+datetime.datetime.now().strftime('%H%M%S')+'.log')
                def one(key=key,command=command,log=log,line=line):
                    began=time.monotonic()
                    with log.open('w') as f:result=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
                    return dict(key=key,command=command,admission_uptime=line,exit_code=result.returncode,
                        seconds=time.monotonic()-began,log=str(log))
                running[key]=pool.submit(one)
                print('START',key,'load1',load,flush=True)
            if limit==0 and time.monotonic()-last_defer>30:
                print('DEFER',line,flush=True);last_defer=time.monotonic()
            time.sleep(3)
    (LOCAL/'batch-acros.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    if failed:raise SystemExit('Failed: '+','.join(sorted(failed)))


if __name__=='__main__':main()
