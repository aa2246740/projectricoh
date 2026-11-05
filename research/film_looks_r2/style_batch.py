"""Load-gated exact comparison for digital Looks; same shared numerical leases."""
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

HERE=Path(__file__).resolve().parent;LOCAL=HERE/'local';UNITS=('a12-50','a12-28','mount-a12')
INDICES=(0,1,2,3,6,9,10,15,16,17,18,23,50,51,52)


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--max-workers',type=int,default=2)
    a=p.parse_args();assert sys.flags.isolated
    if os.getpriority(os.PRIO_PROCESS,0)<15:os.nice(15-os.getpriority(os.PRIO_PROCESS,0))
    assert os.getpriority(os.PRIO_PROCESS,0)==15
    root=LOCAL/'batches'/a.tag;root.mkdir(parents=True,exist_ok=False)
    jobs={'prepare':dict(args=['prepare'],out=LOCAL/'styles.json',deps=[])}
    # Existing likely safe Looks go first; all g157 Looks remain in the eventual audit.
    order=(6,17,18,23,16,10,50,51,52,9,15,0,1,2,3)
    for i in order:
        for unit in UNITS:
            dep=['prepare']
            for level in (0,1):
                index=3000+10*i+level
                for phase,nfev in (('iterate',160),('exact',400)):
                    key=f'{i:02d}-{unit}-L{level}-{phase}'
                    jobs[key]=dict(args=[phase,'--index',str(index),'--unit',unit,'--nfev',str(nfev)],
                        out=LOCAL/'fits'/unit/f'{index:02d}'/(phase+'.json'),deps=list(dep))
                    dep=[key]
    running={};rows=[];failed=set();last=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.max_workers) as pool:
        while True:
            for key,f in list(running.items()):
                if not f.done():continue
                r=f.result();rows.append(r);del running[key]
                print('FINISH',key,r['exit_code'],round(r['seconds'],1),flush=True)
                if r['exit_code'] not in (0,75):failed.add(key)
                (root/'receipt.json').write_text(json.dumps(dict(rows=rows,failed=sorted(failed)),indent=2)+'\n')
            pending=[k for k,v in jobs.items() if not v['out'].exists() and k not in running and k not in failed]
            if not pending and not running:break
            if failed:
                if not running:break
                time.sleep(2);continue
            line=subprocess.check_output(['/usr/bin/uptime'],text=True).strip();m=re.search(r'load averages?:\s*([\d.]+)',line)
            if not m:raise RuntimeError('Cannot parse uptime')
            load=float(m[1]);limit=0 if load>10 else min(a.max_workers,6 if load<5 else 2)
            ready=[k for k in pending if all(jobs[d]['out'].exists() for d in jobs[k]['deps'])]
            for key in ready[:max(0,limit-len(running))]:
                cmd=[sys.executable,'-I','-B',str(HERE/'styles.py'),*jobs[key]['args']]
                log=root/(key+'-'+datetime.datetime.now().strftime('%H%M%S')+'.log')
                def one(key=key,cmd=cmd,log=log,line=line):
                    began=time.monotonic()
                    with log.open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
                    return dict(key=key,command=cmd,log=str(log),uptime=line,exit_code=r.returncode,seconds=time.monotonic()-began)
                running[key]=pool.submit(one);print('START',key,'load1',load,flush=True)
            if time.monotonic()-last>45:
                print('STYLES',sum(v['out'].exists() for v in jobs.values()),'/',len(jobs),'load1',load,flush=True);last=time.monotonic()
            time.sleep(3)
    if failed:raise SystemExit('Style failures: '+','.join(sorted(failed)))
    print('STYLES COMPLETE',len(jobs),flush=True)


if __name__=='__main__':main()
