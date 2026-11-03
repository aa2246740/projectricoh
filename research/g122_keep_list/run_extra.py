"""Finish the remaining model groups in a foreground unit queue."""
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,DAT,file_sha,save

unit=sys.argv[1]
selected=[('recovery_cases.py',unit),
    ('field_cases.py',unit,'--only','fn2_right_left','disp','panel_keys','prewrite_busy','partial_busy',
     'row_reset','ready_busy','capture_exit','capture_open','capture_after_fn2'),
    ('boundary_cases.py',unit),('allocation_cases.py',unit),('notice_cases.py',unit),
    ('bounded_moves.py',unit),('list_counts.py',unit)]
rows=[];folder=OUT/'commands';folder.mkdir(exist_ok=True)
for index,parts in enumerate(selected):
    label='extra-'+unit+'-'+str(index+1).zfill(2)+'-'+parts[0].removesuffix('.py')
    log=folder/(label+'.log');start=time.monotonic();print('RUN',label,flush=True)
    with log.open('w') as output:
        r=subprocess.run(['/usr/bin/python3','-I','-B',str(OUT/parts[0]),*parts[1:]],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
    rows.append(dict(command=parts,returncode=r.returncode,seconds=time.monotonic()-start,
        log=str(log.relative_to(OUT)),dat_sha256=file_sha(DAT),script_sha256=file_sha(OUT/parts[0])))
    save('extra-'+unit+'.json',dict(unit=unit,dat_sha256=file_sha(DAT),commands=rows,total=len(selected)))
    print('DONE',label,r.returncode,flush=True)
