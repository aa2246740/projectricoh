"""At most two nice-15 acceptance jobs, ordered by user priority, until deadline."""
from pathlib import Path
import datetime
import json
import os
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import accept_r2 as A
C.setup();A.DIR.mkdir(exist_ok=True)
queue=A.DIR/'queue.json';status=A.DIR/'progress.json'
finished=json.loads(status.read_text()).get('finished',{}) if status.exists() else {}
running={};deadline=datetime.datetime.fromisoformat('2026-11-04T16:35:57+00:00').timestamp()
while time.time()<deadline:
    tasks=json.loads(queue.read_text())
    for key,(child,task,stream) in list(running.items()):
        code=child.poll()
        if code is None:continue
        stream.close();del running[key]
        output=Path(task['log']).read_text()
        if code and 'LOAD_DEFERRED' in output:continue
        finished[key]=dict(returncode=code,log=task['log'],ended_utc=A.now())
        print(json.dumps(dict(task=key,returncode=code)),flush=True)
    load1=os.getloadavg()[0];cap=0 if load1>10 else 2
    for task in tasks:
        if len(running)>=cap:break
        key=task['id']
        if key in finished or key in running:continue
        if any(finished.get(n,{}).get('returncode')!=0 for n in task.get('needs',[])):continue
        assert task['script'] in ('run.py','prepare_accept_r2.py','verify_accept_r2.py','reference_input.py','ui_text_evidence.py')
        log=Path(task['log']);log.parent.mkdir(exist_ok=True,parents=True);stream=log.open('w')
        child=subprocess.Popen([sys.executable,'-I','-B',str(C.HERE/task['script']),*task.get('args',[])],cwd=C.ROOT,stdout=stream,stderr=subprocess.STDOUT)
        running[key]=(child,task,stream)
        with (A.DIR/'load.jsonl').open('a') as f:f.write(json.dumps(dict(task=key,pid=child.pid,load1=load1,nice=os.getpriority(os.PRIO_PROCESS,0),utc=A.now()))+'\n')
    C.save(status,dict(finished=finished,running={k:v[0].pid for k,v in running.items()},pending=[t['id'] for t in tasks if t['id'] not in finished and t['id'] not in running],load1=load1))
    if not running and all(t['id'] in finished for t in tasks):break
    time.sleep(5)
stopped=[]
for key,(child,task,stream) in running.items():
    child.terminate()
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:child.kill();child.wait()
    stream.close();stopped.append(dict(task=key,pid=child.pid,status='DEADLINE_OPEN'))
C.save(A.DIR/'finished.json',dict(finished=finished,deadline=time.time()>=deadline,stopped=stopped,utc=A.now()))
