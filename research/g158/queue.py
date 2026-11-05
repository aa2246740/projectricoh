"""Finite load-admitted nice-15 jobs; no work continues beyond the task deadline."""
from pathlib import Path
import datetime,json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'research/g158/local';OUT.mkdir(exist_ok=True)
assert os.getpriority(os.PRIO_PROCESS,0)>=15
deadline=datetime.datetime.fromisoformat('2026-11-05T05:00:24+00:00').timestamp()
def save(path,value):
    temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)
finished=json.loads((OUT/'queue-progress.json').read_text()).get('finished',{}) if (OUT/'queue-progress.json').exists() else {}
running={};(OUT/'logs').mkdir(exist_ok=True)
while time.time()<deadline:
    jobs=json.loads((OUT.parent/'jobs.json').read_text())
    for key,(child,job,stream) in list(running.items()):
        status=child.poll()
        if status is None:continue
        stream.close();del running[key]
        log=Path(job['log']).read_text()
        if status and 'LOAD_DEFERRED' in log:continue
        finished[key]=dict(returncode=status,log=job['log'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        print(json.dumps(dict(task=key,returncode=status)),flush=True)
    load=os.getloadavg()[0];cap=0 if load>10 else 2 if load>=5 else 6
    for job in jobs:
        if len(running)>=cap:break
        key=job['id']
        if key in finished or key in running or any(finished.get(k,{}).get('returncode')!=0 for k in job.get('needs',[])):continue
        path=Path(job['log']);stream=path.open('w')
        child=subprocess.Popen([sys.executable,'-I','-B',str(ROOT/job['script']),*job.get('args',[])],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        running[key]=(child,job,stream)
        with (OUT/'queue-load.jsonl').open('a') as f:f.write(json.dumps(dict(task=key,pid=child.pid,load1=load,cap=cap,nice=os.getpriority(os.PRIO_PROCESS,0)))+'\n')
    save(OUT/'queue-progress.json',dict(finished=finished,running={k:v[0].pid for k,v in running.items()},load1=load,pending=[j['id'] for j in jobs if j['id'] not in finished and j['id'] not in running]))
    if not running and all(j['id'] in finished for j in jobs):break
    time.sleep(5)
stopped=[]
for key,(child,job,stream) in running.items():
    child.terminate()
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:child.kill();child.wait()
    stream.close();stopped.append(key)
save(OUT/'queue-final.json',dict(finished=finished,stopped=stopped,deadline=time.time()>=deadline))
