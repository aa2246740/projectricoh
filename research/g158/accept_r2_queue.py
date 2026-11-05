"""Fresh finite load-admitted queue; never builds or modifies a DAT."""
from pathlib import Path
import argparse,datetime,json,os,signal,subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
sys.path.insert(0,str(C.ROOT/'tools'));import loadgate
p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');p.add_argument('--deadline',default='2026-11-05T08:03:27+00:00');a=p.parse_args()
C.setup();out=C.LOCAL/'accept-r2';deadline=datetime.datetime.fromisoformat(a.deadline).timestamp()
finished={};running={};(out/'logs').mkdir(exist_ok=True)
if a.resume:
    previous=json.loads((out/'queue-final.json').read_text())
    assert not previous['stopped'],'resume only after the old queue drained naturally'
    progress=json.loads((out/'progress.json').read_text());assert not progress['running']
    finished=previous['finished']
    transition=out/'loadgate-transition'
    C.save(transition/'queue-before-resume.json',previous)
    C.save(transition/'progress-after-drain.json',progress)
    C.save(out/'jobs.json',json.loads((transition/'jobs-full.json').read_text()))
    C.save(transition/'resumed.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),finished_ids=sorted(finished),admission_policy='tools/loadgate.py',deadline=a.deadline,old_children_signalled=False))
def stop(*_):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,stop)
try:
    while time.time()<deadline:
        jobs=json.loads((out/'jobs.json').read_text())
        for key,(child,job,stream) in list(running.items()):
            status=child.poll()
            if status is None:continue
            stream.close();del running[key]
            if status and 'LOAD_DEFERRED' in Path(job['log']).read_text():
                with (out/'deferred.jsonl').open('a') as f:f.write(json.dumps(dict(task=key,utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))+'\n')
                continue
            finished[key]=dict(returncode=status,log=job['log'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
            print(json.dumps(dict(task=key,returncode=status)),flush=True)
        cap,info=loadgate.cap(len(running));load=info['load1']
        uptime=subprocess.check_output(['uptime'],text=True).strip()
        with (out/'load.jsonl').open('a') as f:f.write(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),uptime=uptime,load1=load,cap=cap,running=len(running),nice=os.getpriority(os.PRIO_PROCESS,0),info=info,admission_policy='tools/loadgate.py'))+'\n')
        if len(running)<cap:
            for job in jobs:
                if len(running)>=cap:break
                key=job['id']
                if key in finished or key in running or any(finished.get(k,{}).get('returncode')!=0 for k in job.get('needs',[])):continue
                stream=Path(job['log']).open('w');child=subprocess.Popen([sys.executable,'-I','-B',str(C.ROOT/job['script']),*job.get('args',[])],cwd=C.ROOT,stdout=stream,stderr=subprocess.STDOUT)
                running[key]=(child,job,stream)
                with (out/'admissions.jsonl').open('a') as f:f.write(json.dumps(dict(task=key,pid=child.pid,load1=load,cap=cap,nice=os.getpriority(os.PRIO_PROCESS,0),info=info,admission_policy='tools/loadgate.py'))+'\n')
                break
        C.save(out/'progress.json',dict(finished=finished,running={k:v[0].pid for k,v in running.items()},load1=load,info=info,admission_policy='tools/loadgate.py',pending=[j['id'] for j in jobs if j['id'] not in finished and j['id'] not in running]))
        if not running and all(j['id'] in finished for j in jobs):break
        time.sleep(5)
except KeyboardInterrupt:
    pass
finally:
    stopped=[]
    for key,(child,job,stream) in running.items():
        child.terminate()
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:child.kill();child.wait()
        stream.close();stopped.append(key)
    C.save(out/'queue-final.json',dict(finished=finished,stopped=stopped,deadline=time.time()>=deadline,deadline_utc=a.deadline,admission_policy='tools/loadgate.py',utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
