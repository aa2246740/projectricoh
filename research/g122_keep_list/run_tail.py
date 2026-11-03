"""Run independent remaining native commands from the end of each unit list."""
from pathlib import Path
import datetime
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,DAT,file_sha,save
from run_queue import commands

unit=sys.argv[1]
selected=[p for p in commands() if unit in p and p[0]!='fn2_all.py' and p[:2]!=('run_native.py','matrix')]
selected=[p for p in reversed(selected) if p[:2]!=('run_native.py','ah')]
rows=[];folder=OUT/'commands';folder.mkdir(exist_ok=True)
for index,parts in enumerate(selected):
    now=datetime.datetime.now(datetime.timezone.utc)
    if now>=datetime.datetime.fromisoformat('2026-10-28T06:41:22+00:00'):break
    label='tail-'+unit+'-'+str(index+1).zfill(2)+'-'+parts[0].removesuffix('.py')
    print('RUN',label,list(parts[1:]),flush=True)
    start=time.monotonic();log=folder/(label+'.log')
    with log.open('w') as output:
        result=subprocess.run(['/usr/bin/python3','-I','-B',str(OUT/parts[0]),*parts[1:]],
                              cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
    rows.append(dict(command=parts,returncode=result.returncode,seconds=time.monotonic()-start,
        log=str(log.relative_to(OUT)),dat_sha256=file_sha(DAT),source_sha256=file_sha(OUT/parts[0])))
    save('tail-'+unit+'.json',dict(unit=unit,dat_sha256=file_sha(DAT),commands=rows,total=len(selected)))
    print('DONE',label,result.returncode,flush=True)
