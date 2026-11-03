"""Profile one full cutpoints group after the paired measurements finish."""
import collections,json,os,resource,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import ROOT,enable,emit

def main():
    enable();name='profile-group126-50mm-cutpoints'
    job=next(j for j in json.loads((HERE/'queue.json').read_text())['jobs'] if j['name']=='group126-50mm-cutpoints')
    folder=HERE/'run/local/profile';folder.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,GXR_HARNESS_BACKEND='c',GXR_HARNESS_UI_AUDIT='1',GXR_HOST_METRICS_DIR=str(HERE/'run/local/processes/profile'),GXR_HOST_PROFILE_DIR=str(folder),G139_PACKAGE='firmware/package_v38_g150',G139_ENGINE='firmware/engine_v58_g150',REVIEW_JOB=name)
    command=['/usr/bin/sandbox-exec','-f',str(HERE/'offline.sb'),sys.executable,'-I','-B',str(HERE/'run/profile_launch.py'),name,*job['args']]
    start=time.monotonic()
    with (folder/'raw.log').open('w') as stream:result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=10800)
    if result.returncode:raise RuntimeError((folder/'raw.log').read_text()[-2200:])
    totals={}
    for path in folder.glob('process-*.json'):
        for row in json.loads(path.read_text()):
            key=(row['file'],row['line'],row['function'])
            value=totals.setdefault(key,dict(row,self_cpu_seconds=0,cumulative_cpu_seconds=0,calls=0,primitive_calls=0))
            for field in ('self_cpu_seconds','cumulative_cpu_seconds','calls','primitive_calls'):value[field]+=row[field]
    rows=sorted(totals.values(),key=lambda row:row['self_cpu_seconds'],reverse=True)
    total=sum(r['self_cpu_seconds'] for r in rows)
    for row in rows:row['self_cpu_fraction']=row['self_cpu_seconds']/total if total else 0
    emit(HERE/'local/profile.json',{'passed':True,'scope':'complete 50mm cutpoints group, CPU timer, one separate instrumented run','wall_seconds':time.monotonic()-start,'profile_self_cpu_seconds':total,'processes':len(list(folder.glob('process-*.json'))),'top':rows[:60]})
    print(json.dumps({'profile_passed':True,'top':rows[:5]}),flush=True)
if __name__=='__main__':main()
