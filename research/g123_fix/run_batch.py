"""Run independent unit checks with owned process groups and a fixed deadline."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import datetime,json,os,signal,subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,DAT,file_sha,save
DEADLINE=datetime.datetime.fromisoformat('2026-10-28T10:24:00+00:00')

def one(parts):
    pin=file_sha(DAT);label='-'.join(parts).replace('.py','').replace('--','')
    log=OUT/'local/commands'/(label+'.log');log.parent.mkdir(parents=True,exist_ok=True)
    tmp=OUT/'local/tmp';tmp.mkdir(exist_ok=True)
    argv=['/usr/bin/python3','-I','-B',str(OUT/parts[0]),*parts[1:]]
    started=time.monotonic();now=datetime.datetime.now(datetime.timezone.utc)
    remaining=max(1,(DEADLINE-now).total_seconds())
    with log.open('w') as stream:
        p=subprocess.Popen(argv,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True,
            env=dict(os.environ,TMPDIR=str(tmp),PYTHONDONTWRITEBYTECODE='1'))
        try:code=p.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGTERM)
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
            code='TIMEBOX'
    result=dict(command=parts,argv=argv,returncode=code,seconds=time.monotonic()-started,
        started_utc=now.isoformat(),dat_sha256=pin,dat_unchanged=file_sha(DAT)==pin,
        script_sha256=file_sha(OUT/parts[0]),log=str(log.relative_to(OUT)),log_sha256=file_sha(log))
    print('DONE',parts,code,round(result['seconds'],1),flush=True)
    return result

def main(group):
    if group=='matrix':commands=[['run_native.py','matrix',u] for u in ('50mm','28mm','mount')]
    elif group=='required':commands=[['run_cases.py','suite','--unit',u] for u in ('50mm','28mm','mount')]
    elif group=='first':commands=[['first_open.py',u] for u in ('50mm','28mm','mount')]
    elif group=='keep':commands=[['keep_cases.py',u,'--rerun'] for u in ('50mm','28mm','mount')]
    elif group=='official':commands=[['official_half.py','--hook-trace','--unit',u] for u in ('50mm','28mm','mount')]
    elif group=='locked':commands=[['locked_cases.py',u] for u in ('50mm','28mm','mount')]
    elif group=='safety':commands=[['safety_cases.py','--unit',u] for u in ('50mm','28mm','mount')]
    else:raise ValueError(group)
    records=[]
    save(group+'-commands.json',dict(status='RUNNING',total=len(commands),commands=[]))
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(one,x) for x in commands]
        for future in as_completed(futures):
            records.append(future.result());save(group+'-commands.json',dict(status='RUNNING',total=len(commands),commands=records))
    state='PASS' if len(records)==len(commands) and all(x['returncode']==0 and x['dat_unchanged'] for x in records) else 'FAIL'
    save(group+'-commands.json',dict(status=state,total=len(commands),commands=records))
    print(state,group,flush=True)
    assert state=='PASS',records
if __name__=='__main__':main(sys.argv[1])
