"""Score each style once its two exact fits exist, under the same load budget."""
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
INDICES=(0,1,2,3,6,9,10,15,16,17,18,23,50,51,52,53)
if os.getpriority(os.PRIO_PROCESS,0)<15:os.nice(15-os.getpriority(os.PRIO_PROCESS,0))
assert os.getpriority(os.PRIO_PROCESS,0)==15
root=LOCAL/'batches'/('style-analysis-'+datetime.datetime.now().strftime('%H%M%S'));root.mkdir(exist_ok=False)
running={};rows=[];failed=set();last=0
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    while True:
        for key,f in list(running.items()):
            if not f.done():continue
            r=f.result();rows.append(r);del running[key]
            if r['exit_code'] not in (0,75):failed.add(key)
            (root/'receipt.json').write_text(json.dumps(dict(rows=rows,failed=sorted(failed)),indent=2)+'\n')
            print('FINISH',key,r['exit_code'],flush=True)
        ready=[];complete=0
        for i in INDICES:
            for u in UNITS:
                out=LOCAL/'style_analysis'/f'{i:02d}'/(u+'.json');key=f'{i:02d}-{u}'
                if out.exists():complete+=1;continue
                a,b=(14,4053) if i==53 else (3000+10*i,3001+10*i)
                if all((LOCAL/'fits'/u/str(x)/'exact.json').exists() for x in (a,b)) and key not in running and key not in failed:
                    ready.append((key,i,u))
        if complete==48 and not running:break
        if failed:
            if not running:break
            time.sleep(2);continue
        line=subprocess.check_output(['/usr/bin/uptime'],text=True).strip();m=re.search(r'load averages?:\s*([\d.]+)',line)
        if not m:raise RuntimeError('Cannot parse uptime')
        load=float(m[1]);limit=0 if load>10 else 2
        for key,i,u in ready[:max(0,limit-len(running))]:
            cmd=[sys.executable,'-I','-B',str(HERE/'analyze_style.py'),'--index',str(i),'--unit',u]
            log=root/(key+'-'+datetime.datetime.now().strftime('%H%M%S')+'.log')
            def one(key=key,cmd=cmd,log=log,line=line):
                with log.open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
                return dict(key=key,command=cmd,log=str(log),exit_code=r.returncode,uptime=line)
            running[key]=pool.submit(one);print('START',key,'load1',load,flush=True)
        if time.monotonic()-last>45:print('STYLE ANALYSIS',complete,'/48 load1',load,flush=True);last=time.monotonic()
        time.sleep(3)
if failed:raise SystemExit('Style analysis failures: '+','.join(sorted(failed)))
print('STYLE ANALYSIS COMPLETE',flush=True)
