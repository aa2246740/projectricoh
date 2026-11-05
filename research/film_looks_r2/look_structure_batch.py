"""Run the independent shared-structure control and confirm it when training selects it."""
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
if os.getpriority(os.PRIO_PROCESS,0)<15:os.nice(15-os.getpriority(os.PRIO_PROCESS,0))
assert os.getpriority(os.PRIO_PROCESS,0)==15
cat=json.loads((LOCAL/'catalog.json').read_text());root=LOCAL/'batches'/('shared-structure-'+datetime.datetime.now().strftime('%H%M%S'))
root.mkdir(exist_ok=False);running={};rows=[];jobs={};failed=set();last=0
def job(key,script,args,out):jobs[key]=dict(command=[sys.executable,'-I','-B',str(HERE/script),*args],out=out)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    while True:
        for key,f in list(running.items()):
            if not f.done():continue
            r=f.result();rows.append(r);del running[key]
            print('FINISH',key,r['exit_code'],round(r['seconds'],1),flush=True)
            if r['exit_code'] not in (0,75):failed.add(key)
            (root/'receipt.json').write_text(json.dumps(dict(rows=rows,failed=sorted(failed)),indent=2)+'\n')
        ready=0
        for film in cat['films']:
            o=film['ordinal']
            if not (LOCAL/'films'/f'{o:02d}/prepared.json').exists():continue
            prepared=LOCAL/'films'/f'{o:02d}/look-structure-prepared.json'
            if not prepared.exists():job(f'{o:02d}-prepare','look_structure.py',['--film',str(o)],prepared);continue
            for unit in UNITS:
                idx=film['indices']['scene_shared_structure'];folder=LOCAL/'fits'/unit/f'{idx:02d}'
                prefix=f'{o:02d}-{unit}'
                base=LOCAL/'fits'/unit/f'{film["indices"]["scene_shared_matrix"]:02d}'
                if not (base/'iterate.json').exists():continue
                if not (folder/'iterate.json').exists():
                    job(prefix+'-iterate','library.py',['iterate','--film',str(o),'--unit',unit,
                        '--route','scene_shared_structure','--nfev','160'],folder/'iterate.json');continue
                old=json.loads((base/('exact.json' if (base/'exact.json').exists() else 'iterate.json')).read_text())
                new=json.loads((folder/'iterate.json').read_text())
                if new['objective']<old['objective']-1e-10 and not (folder/'exact.json').exists():
                    job(prefix+'-exact','library.py',['exact','--film',str(o),'--unit',unit,
                        '--route','scene_shared_structure','--nfev','400'],folder/'exact.json');continue
                ready+=1
        if ready==60 and not running:break
        pending=[k for k,j in jobs.items() if not j['out'].exists() and k not in running and k not in failed]
        if failed:
            if not running:break
            time.sleep(2);continue
        line=subprocess.check_output(['/usr/bin/uptime'],text=True).strip();m=re.search(r'load averages?:\s*([\d.]+)',line)
        if not m:raise RuntimeError('Cannot parse uptime')
        load=float(m[1]);limit=0 if load>10 else (6 if load<5 else 2)
        for key in pending[:max(0,limit-len(running))]:
            cmd=jobs[key]['command'];log=root/(key+'-'+datetime.datetime.now().strftime('%H%M%S')+'.log')
            def one(key=key,cmd=cmd,log=log,line=line):
                began=time.monotonic()
                with log.open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
                return dict(key=key,command=cmd,log=str(log),uptime=line,exit_code=r.returncode,seconds=time.monotonic()-began)
            running[key]=pool.submit(one);print('START',key,'load1',load,flush=True)
        if time.monotonic()-last>45:print('SHARED STRUCTURE',ready,'/60 ready, load1',load,flush=True);last=time.monotonic()
        time.sleep(3)
if failed:raise SystemExit('Shared structure failures: '+','.join(sorted(failed)))
print('SHARED STRUCTURE COMPLETE',flush=True)
