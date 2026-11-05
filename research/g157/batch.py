"""Load-aware, nice-15 cold-run queue. Never resumes a Machine checkpoint."""
from pathlib import Path
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
def main():
    p=argparse.ArgumentParser();p.add_argument('queue',type=Path);p.add_argument('--max',type=int,default=2);a=p.parse_args()
    C.setup();assert 1<=a.max<=6
    rows=json.loads(a.queue.read_text());seen={r['label'] for r in rows};running={};finished=[]
    deadline=datetime.datetime.fromisoformat('2026-11-04T13:33:00+00:00').timestamp()
    while rows or running:
        now=time.time()
        try:
            for row in json.loads(a.queue.read_text()):
                if row['label'] not in seen:rows.append(row);seen.add(row['label'])
        except json.JSONDecodeError:
            pass  # The queue author is replacing its JSON; retry the next read.
        for pid,(child,row,log) in list(running.items()):
            code=child.poll()
            if code is None:continue
            log.close();del running[pid]
            output=Path(row['log']).read_text()
            if code and 'LOAD_DEFERRED' in output and now<deadline:rows.append(row)
            else:
                result=next((json.loads(line) for line in reversed(output.splitlines()) if line.startswith('{"label"')),None)
                finished.append(dict(**row,returncode=code,result=result))
                print(json.dumps(dict(label=row['label'],returncode=code,result=result)),flush=True)
        if now>=deadline:
            for child,row,log in running.values():child.terminate();log.close();finished.append(dict(**row,returncode='DEADLINE_STOP'))
            break
        load1=os.getloadavg()[0]
        cap=0 if load1>10 else min(a.max,2 if load1>=5 else 6)
        if (C.LOCAL/'BATCH_PAUSE').exists():cap=0
        while rows and len(running)<cap:
            row=rows.pop(0);Path(row['log']).parent.mkdir(parents=True,exist_ok=True)
            log=Path(row['log']).open('w')
            child=subprocess.Popen([sys.executable,'-I','-B',str(C.HERE/'run.py'),*row['args']],cwd=C.ROOT,stdout=log,stderr=subprocess.STDOUT)
            running[child.pid]=(child,row,log)
            with (C.LOCAL/'load.jsonl').open('a') as stream:stream.write(json.dumps(dict(batch=a.queue.name,label=row['label'],load1=load1,pid=child.pid,nice=os.getpriority(os.PRIO_PROCESS,0)))+'\n')
        C.save(a.queue.with_suffix('.progress.json'),dict(pending=[r['label'] for r in rows],running={pid:row['label'] for pid,(_,row,_) in running.items()},finished=finished,load1=load1))
        if rows or running:time.sleep(5)
    C.save(a.queue.with_suffix('.result.json'),dict(finished=finished,pending=rows))
if __name__=='__main__':main()
