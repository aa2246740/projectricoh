"""Analyze ready film profiles, exact-confirm selected records, then run 128 branches."""
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
HERE=Path(__file__).resolve().parent;LOCAL=HERE/'local';UNITS=('a12-50','a12-28','mount-a12')
ROUTES=('scene_shared_matrix','scene_rgb_matrix','scene_structure','scene_weighted')


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--max-workers',type=int,default=6)
    p.add_argument('--confirm-focus',action='store_true');args=p.parse_args()
    if os.getpriority(os.PRIO_PROCESS,0)<15:os.nice(15-os.getpriority(os.PRIO_PROCESS,0))
    assert os.getpriority(os.PRIO_PROCESS,0)==15
    cat=json.loads((LOCAL/'catalog.json').read_text());root=LOCAL/'batches'/args.tag
    root.mkdir(parents=True,exist_ok=False);running={};receipts=[];failed=set();last=0
    jobs={}
    def job(key,script,arguments,out):jobs[key]=dict(command=[sys.executable,'-I','-B',str(HERE/script),*arguments],out=out)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        while True:
            for key,f in list(running.items()):
                if not f.done():continue
                row=f.result();receipts.append(row);del running[key]
                print('FINISH',key,'exit',row['exit_code'],'seconds',round(row['seconds'],1),flush=True)
                if row['exit_code'] not in (0,75):failed.add(key)
                (root/'receipt.json').write_text(json.dumps(dict(rows=receipts,failed=sorted(failed)),indent=2)+'\n')
            complete=0
            for film in cat['films']:
                ordinal=film['ordinal']
                for unit in UNITS:
                    prefix=f'{ordinal:02d}-{unit}';output=LOCAL/'analysis'/f'{ordinal:02d}'/unit
                    if (output/'final.json').exists():complete+=1;continue
                    if not all((LOCAL/'fits'/unit/f'{film["indices"][r]:02d}/iterate.json').exists() for r in ROUTES):continue
                    if not (output/'screen.json').exists():
                        job(prefix+'-screen','analyze.py',['--film',str(ordinal),'--unit',unit,'--phase','screen'],output/'screen.json');continue
                    screen=json.loads((output/'screen.json').read_text())
                    confirm={screen['selected_route'],'scene_shared_matrix'}
                    if args.confirm_focus:confirm.add(screen['focused_training_winner'])
                    for route in sorted(confirm):
                        index=film['indices'][route];out=LOCAL/'fits'/unit/f'{index:02d}/exact.json'
                        if not out.exists():job(prefix+'-'+route+'-exact','library.py',
                            ['exact','--film',str(ordinal),'--unit',unit,'--route',route,'--nfev','400'],out)
                    if all((LOCAL/'fits'/unit/f'{film["indices"][r]:02d}/exact.json').exists() for r in confirm):
                        job(prefix+'-final','analyze.py',['--film',str(ordinal),'--unit',unit,'--phase','final'],output/'final.json')
            if complete==60 and not running:break
            pending=[k for k,j in jobs.items() if not j['out'].exists() and k not in running and k not in failed]
            if failed:
                if not running:break
                time.sleep(2);continue
            line=subprocess.check_output(['/usr/bin/uptime'],text=True).strip()
            m=re.search(r'load averages?:\s*([\d.]+)',line)
            if not m:raise RuntimeError('Cannot parse uptime')
            load=float(m[1]);limit=0 if load>10 else min(args.max_workers,6 if load<5 else 2)
            for key in pending[:max(0,limit-len(running))]:
                command=jobs[key]['command'];log=root/(key+'-'+datetime.datetime.now().strftime('%H%M%S')+'.log')
                def one(key=key,command=command,log=log,line=line):
                    start=time.monotonic()
                    with log.open('w') as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
                    return dict(key=key,command=command,log=str(log),uptime=line,
                        seconds=time.monotonic()-start,exit_code=r.returncode)
                running[key]=pool.submit(one);print('START',key,'load1',load,flush=True)
            if time.monotonic()-last>45:
                print('PIPELINE',complete,'/60 final, ready',len(pending),'running',len(running),'load1',load,flush=True);last=time.monotonic()
            time.sleep(3)
    if failed:raise SystemExit('Pipeline failures: '+','.join(sorted(failed)))
    print('PIPELINE COMPLETE 60 final profiles',flush=True)


if __name__=='__main__':main()
