"""Schedule independent film fits under the task-wide load/lease policy."""
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
HERE=Path(__file__).resolve().parent;LOCAL=HERE/'local'
UNITS=('a12-50','a12-28','mount-a12')


def main():
    p=argparse.ArgumentParser();p.add_argument('--films',default='0:20')
    p.add_argument('--max-workers',type=int,default=6);p.add_argument('--tag',required=True)
    p.add_argument('--routes');p.add_argument('--units',default=','.join(UNITS))
    p.add_argument('--screen-only',action='store_true')
    args=p.parse_args();lo,hi=map(int,args.films.split(':'))
    assert 0<=lo<hi<=20 and 1<=args.max_workers<=6 and Path(args.tag).name==args.tag
    if os.getpriority(os.PRIO_PROCESS,0)<15:os.nice(15-os.getpriority(os.PRIO_PROCESS,0))
    assert os.getpriority(os.PRIO_PROCESS,0)==15
    cat=json.loads((LOCAL/'catalog.json').read_text());jobs={}
    dep_routes={'scene_rgb':('scene_shared',),'scene_shared_matrix':(),
        'scene_rgb_matrix':('scene_shared_matrix',),'scene_weighted':('scene_structure',)}
    selected=set(args.routes.split(',')) if args.routes else set(cat['routes'])
    expanded=set(selected)
    while True:
        old=set(expanded)
        for route in old:expanded.update(dep_routes.get(route,()))
        if old==expanded:break
    for film in cat['films'][lo:hi]:
        ordinal=film['ordinal'];prep=f'{ordinal:02d}-prepare'
        active_routes=set(expanded)
        if ordinal==9 and 'scene_rgb_matrix' in active_routes:active_routes.update(('scene_shared','scene_rgb'))
        jobs[prep]=dict(args=['prepare','--film',str(ordinal)],out=LOCAL/'films'/f'{ordinal:02d}/prepared.json',deps=[])
        for unit in args.units.split(','):
            assert unit in UNITS
            for route in cat['routes']:
                if route not in active_routes:continue
                dependencies=dep_routes.get(route,())
                # The pilot metadata declared an additional plain L1 seed. Retain its exact history.
                if ordinal==9 and route=='scene_shared_matrix':dependencies=('scene_shared',)
                if ordinal==9 and route=='scene_rgb_matrix':dependencies=('scene_rgb','scene_shared_matrix')
                endpoint='iterate' if args.screen_only else 'exact'
                index=film['indices'][route];previous=[prep]+[f'{ordinal:02d}-{unit}-{r}-{endpoint}' for r in dependencies]
                phases=(('iterate',160),) if args.screen_only else (('iterate',160),('exact',400))
                for phase,nfev in phases:
                    key=f'{ordinal:02d}-{unit}-{route}-{phase}'
                    jobs[key]=dict(args=[phase,'--film',str(ordinal),'--unit',unit,'--route',route,'--nfev',str(nfev)],
                        out=LOCAL/'fits'/unit/f'{index:02d}'/(phase+'.json'),deps=list(previous))
                    previous=[key]
    root=LOCAL/'batches'/args.tag;root.mkdir(parents=True,exist_ok=False)
    running={};failed=set();receipts=[];last_defer=0;last_summary=0
    def load():
        line=subprocess.check_output(['/usr/bin/uptime'],text=True).strip()
        m=re.search(r'load averages?:\s*([\d.]+)',line)
        if not m:raise RuntimeError('Cannot parse uptime')
        return float(m[1]),line
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        while True:
            for key,f in list(running.items()):
                if not f.done():continue
                r=f.result();receipts.append(r);del running[key]
                print('FINISH',key,'exit',r['exit_code'],'seconds',round(r['seconds'],1),flush=True)
                if r['exit_code'] not in (0,75):failed.add(key)
                (root/'receipt.json').write_text(json.dumps(dict(rows=receipts,failed=sorted(failed)),indent=2)+'\n')
            pending=[k for k,v in jobs.items() if not v['out'].exists() and k not in running and k not in failed]
            if not pending and not running:break
            if failed:
                # Drain existing jobs and preserve their products; stop dispatching new work.
                if not running:break
                time.sleep(2);continue
            l,line=load();limit=0 if l>10 else min(args.max_workers,6 if l<5 else 2)
            ready=[k for k in pending if all(jobs[d]['out'].exists() for d in jobs[k]['deps'])]
            for key in ready[:max(0,limit-len(running))]:
                job=jobs[key];cmd=[sys.executable,'-I','-B',str(HERE/'library.py'),*job['args']]
                log=root/(key+'-'+datetime.datetime.now().strftime('%H%M%S')+'.log')
                def one(key=key,cmd=cmd,log=log,line=line):
                    start=time.monotonic()
                    with log.open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
                    return dict(key=key,command=cmd,uptime=line,exit_code=r.returncode,
                        seconds=time.monotonic()-start,log=str(log))
                running[key]=pool.submit(one);print('START',key,'load1',l,flush=True)
            now=time.monotonic()
            if l>10 and now-last_defer>30:print('DEFER',line,flush=True);last_defer=now
            if now-last_summary>60:
                print('PROGRESS',sum(v['out'].exists() for v in jobs.values()),'/',len(jobs),'running',len(running),flush=True)
                last_summary=now
            time.sleep(2)
    if failed:raise SystemExit('Failed jobs: '+','.join(sorted(failed)))
    print('BATCH COMPLETE',len(jobs),flush=True)


if __name__=='__main__':main()
