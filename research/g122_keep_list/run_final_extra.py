"""Run final-unit counts and bounded checks within the remaining timebox."""
from pathlib import Path
import datetime
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,DAT,file_sha,save

unit=sys.argv[1]
assert unit in ('50mm','28mm','mount')
commands=[('fn2_quality.py','measure',unit),('fn2_quality.py','retain',unit),
    ('bounded_moves.py',unit),('allocation_cases.py',unit),('notice_cases.py',unit),
    ('boundary_cases.py',unit),('list_counts.py',unit)]
rows=[]
folder=OUT/'commands';folder.mkdir(exist_ok=True)
for index,parts in enumerate(commands):
    if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat('2026-10-28T06:42:22+00:00'):break
    print('RUN final extra',unit,list(parts),flush=True)
    start=time.monotonic();log=folder/('final-extra-'+unit+'-'+str(index+1)+'.log')
    with log.open('w') as stream:
        result=subprocess.run(['/usr/bin/python3','-I','-B',str(OUT/parts[0]),*parts[1:]],
            cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    rows.append(dict(command=parts,returncode=result.returncode,seconds=time.monotonic()-start,
        dat_sha256=file_sha(DAT),script_sha256=file_sha(OUT/parts[0]),log=str(log.relative_to(OUT))))
    save('final-extra-'+unit+'.json',dict(unit=unit,dat_sha256=file_sha(DAT),commands=rows,total=len(commands)))
    print('DONE final extra',unit,list(parts),result.returncode,flush=True)
