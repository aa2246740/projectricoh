"""Serial offline checks. Wait only on load admission; never retry a real failure."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

def main():
    p=argparse.ArgumentParser(); p.add_argument('plan',type=Path); p.add_argument('--resume-state',type=Path)
    p.add_argument('--deadline',default=C.DEADLINE); a=p.parse_args()
    C.setup(); os.environ['LUTPROBE_ACTIVE_DEADLINE_UTC']=a.deadline
    plan=json.loads(a.plan.read_text()); status=C.LOCAL/'queue-status.json'
    rows=json.loads(a.resume_state.read_text())['completed'] if a.resume_state else []
    completed={row['id'] for row in rows if row['returncode']==0}
    for job in plan:
        if job['id'] in completed: continue
        while True:
            try: C.gate(job['id'])
            except RuntimeError as error:
                if not str(error).startswith('LOAD_DEFERRED'): raise
                C.save(status,dict(status='LOAD_DEFERRED',job=job['id'],load1=os.getloadavg()[0],completed=rows))
                time.sleep(20); continue
            C.save(status,dict(status='RUNNING',job=job['id'],load1=os.getloadavg()[0],completed=rows))
            argv=[sys.executable,'-I','-B',str(C.ROOT/job['script']),*job.get('args',[])]
            log=C.LOCAL/'logs'/('queue-'+job['id']+'.log'); log.parent.mkdir(exist_ok=True)
            attempt=0
            while log.with_name(log.name+'.'+str(attempt)).exists(): attempt+=1
            log=log.with_name(log.name+'.'+str(attempt))
            with log.open('w') as f: result=subprocess.run(argv,cwd=C.ROOT,stdout=f,stderr=subprocess.STDOUT)
            text=log.read_text()
            if result.returncode and 'LOAD_DEFERRED' in text:
                C.save(status,dict(status='LOAD_DEFERRED',job=job['id'],completed=rows,log=str(log.relative_to(C.ROOT))))
                time.sleep(20); continue
            row=dict(id=job['id'],returncode=result.returncode,log=str(log.relative_to(C.ROOT)))
            rows.append(row); C.save(status,dict(status='PASS' if not result.returncode else 'FAIL',job=job['id'],completed=rows))
            print(json.dumps(row),flush=True)
            if result.returncode: return result.returncode
            break
    C.save(status,dict(status='COMPLETE',completed=rows)); return 0

if __name__=='__main__': sys.exit(main())
