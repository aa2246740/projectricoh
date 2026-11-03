"""Run one task script with a wall-clock bound and the task write fence."""
import runpy
import signal
import sys
import os,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE
enable()
seconds=int(sys.argv[1]);script=Path(sys.argv[2]).resolve()
listing=subprocess.run(['ps','-Ao','pid,ni,etime,pcpu,args'],capture_output=True,text=True,check=True,timeout=10).stdout
markers=('recovery_run.py','record_run.py','look_ceiling_r1/run.py')
occupied=[line.strip() for line in listing.splitlines() if any(marker in line for marker in markers)]
allocation=dict(script=str(script),pid=os.getpid(),nice=os.getpriority(os.PRIO_PROCESS,0),
                load=os.getloadavg(),limit=2 if occupied else 6,other_jobs=occupied)
with (HERE/'runs/process-allocation.jsonl').open('a') as log:log.write(json.dumps(allocation)+'\n')
sys.argv=[str(script),*sys.argv[3:]]
signal.alarm(seconds)
try:
    runpy.run_path(str(script),run_name='__main__')
finally:
    signal.alarm(0)
