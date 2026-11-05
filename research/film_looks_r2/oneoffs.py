"""Retry short verification jobs only when load and shared numerical leases allow."""
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
if os.getpriority(os.PRIO_PROCESS,0)<15:os.nice(15-os.getpriority(os.PRIO_PROCESS,0))
assert os.getpriority(os.PRIO_PROCESS,0)==15
root=LOCAL/'batches'/('oneoffs-'+datetime.datetime.now().strftime('%H%M%S'));root.mkdir(exist_ok=False)
jobs=[('contract','contracts.py',[],LOCAL/'studio_installation_contract.json'),
      ('photos','photos.py',[],LOCAL/'photo_brightness_audit.json'),
      ('acros-full-prepare','acros_full.py',['prepare'],LOCAL/'acros_full_profiles.json')]
for unit in ('a12-50','a12-28','mount-a12'):
    for phase,nfev in (('iterate',160),('exact',400)):
        jobs.append((unit+'-acros-full-'+phase,'acros_full.py',[phase,'--unit',unit,'--nfev',str(nfev)],
            LOCAL/'fits'/unit/'4053'/(phase+'.json')))
rows=[]
for name,script,args,out in jobs:
    while not out.exists():
        line=subprocess.check_output(['/usr/bin/uptime'],text=True).strip()
        m=re.search(r'load averages?:\s*([\d.]+)',line)
        if not m:raise RuntimeError('Cannot parse uptime')
        load=float(m[1])
        if load>10:
            print('DEFER',name,'load1',load,flush=True);time.sleep(20);continue
        log=root/(name+'-'+datetime.datetime.now().strftime('%H%M%S')+'.log')
        cmd=[sys.executable,'-I','-B',str(HERE/script),*args]
        start=time.monotonic()
        with log.open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
        rows.append(dict(name=name,command=cmd,log=str(log),exit_code=r.returncode,
            seconds=time.monotonic()-start,uptime=line))
        (root/'receipt.json').write_text(json.dumps(rows,indent=2)+'\n')
        print('FINISH',name,'exit',r.returncode,flush=True)
        if r.returncode not in (0,75):raise SystemExit('Failed '+name)
        if r.returncode==75:time.sleep(10)
print('ONEOFFS COMPLETE',flush=True)
