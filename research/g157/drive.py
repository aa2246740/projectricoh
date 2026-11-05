"""One load-aware scheduler for links, host probes and fresh MAIN acceptance."""
from pathlib import Path
import datetime
import json
import os
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

def main():
    C.setup()
    path=C.LOCAL/'r1-work.json'
    tasks=json.loads(path.read_text())
    finished={};running={}
    status=C.LOCAL/'r1-work.progress.json'
    if status.exists():finished=json.loads(status.read_text()).get('finished',{})
    deadline=datetime.datetime.fromisoformat('2026-11-04T13:33:00+00:00').timestamp()
    while time.time()<deadline:
        tasks=json.loads(path.read_text())
        known={t['id'] for t in tasks}
        for dataset in ('model','control'):
            tag='r2' if dataset=='model' else 'r1'
            replay=C.LOCAL/('persistence-'+tag+'-'+dataset)/'replays.queue.json'
            if not replay.exists():continue
            rows=json.loads(replay.read_text())
            for row in rows:
                if row['label'] not in known:
                    tasks.append(dict(id=row['label'],script='run.py',args=row['args'],log=row['log']))
                    known.add(row['label'])
            key=dataset+'-S48-verification'
            if key not in known:tasks.append(dict(id=key,script='replay.py',args=['--dataset',dataset,'--tag',tag,'--verify'],needs=[r['label'] for r in rows],log=str(C.LOCAL/'logs'/(key+'.log'))))
        if len(tasks)!=len(json.loads(path.read_text())):
            tmp=path.with_suffix('.tmp');C.save(tmp,tasks);tmp.replace(path)
        for key,(child,task,log) in list(running.items()):
            code=child.poll()
            if code is None:continue
            log.close();del running[key]
            output=Path(task['log']).read_text()
            if code and 'LOAD_DEFERRED' in output:continue
            finished[key]=dict(returncode=code,log=task['log'],ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
            print(json.dumps(dict(task=key,returncode=code)),flush=True)
        load1=os.getloadavg()[0]
        cap=0 if load1>10 else 2 if load1>=5 else 6
        for task in tasks:
            key=task['id']
            if len(running)>=cap:break
            if key in running or key in finished:continue
            if any(finished.get(d,{}).get('returncode')!=0 for d in task.get('needs',[])):continue
            # Building shares generated objects, so links remain sequential.
            if task.get('link') and any(t.get('link') for _,t,_ in running.values()):continue
            log=Path(task['log']);log.parent.mkdir(parents=True,exist_ok=True);stream=log.open('w')
            child=subprocess.Popen([sys.executable,'-I','-B',str(C.HERE/task['script']),*task.get('args',[])],cwd=C.ROOT,stdout=stream,stderr=subprocess.STDOUT)
            running[key]=(child,task,stream)
            with (C.LOCAL/'load.jsonl').open('a') as f:f.write(json.dumps(dict(task=key,load1=load1,pid=child.pid,nice=os.getpriority(os.PRIO_PROCESS,0)))+'\n')
        C.save(status,dict(finished=finished,running={k:v[0].pid for k,v in running.items()},pending=[t['id'] for t in tasks if t['id'] not in finished and t['id'] not in running],load1=load1))
        if not running and all(t['id'] in finished for t in tasks):break
        time.sleep(5)
    for child,task,log in running.values():child.terminate();log.close()
    C.save(C.LOCAL/'r1-work.result.json',dict(finished=finished,deadline=time.time()>=deadline))

if __name__=='__main__':main()
