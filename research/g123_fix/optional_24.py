"""Run the original twenty-four commands per unit at lower CPU priority."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import datetime,json,os,signal,subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,DAT,file_sha,save
UNITS=('50mm','28mm','mount')
DEADLINE=datetime.datetime.fromisoformat('2026-10-28T10:17:00+00:00')

def run_unit(unit,catalog):
    records=[];folder=OUT/'local/optional-commands';folder.mkdir(parents=True,exist_ok=True)
    # Run shorter independent commands first. Keep the longest A-H session last.
    def rank(parts):
        if parts[:2]==['run_native.py','ah']:return 100
        if parts[:2]==['fn2_quality.py','failures']:return 90
        if parts[0]=='latch_paths.py':return 80
        return 0
    selected=sorted(catalog,key=rank);pin=file_sha(DAT)
    for index,parts in enumerate(selected):
        now=datetime.datetime.now(datetime.timezone.utc)
        if now>=DEADLINE:break
        label=unit+'-'+str(index+1).zfill(2)+'-'+'-'.join(parts).replace('.py','').replace('--','')
        log=folder/(label+'.log');argv=['/usr/bin/python3','-I','-B',str(OUT/parts[0]),*parts[1:]]
        dependencies={str(p.relative_to(ROOT)):file_sha(p) for p in OUT.glob('*.py')}
        print('RUN',unit,index+1,parts,flush=True);start=time.monotonic()
        with log.open('w') as stream:
            child=subprocess.Popen(argv,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True,
                env=dict(os.environ,TMPDIR=str(OUT/'local/tmp'),PYTHONDONTWRITEBYTECODE='1'))
            try:code=child.wait(timeout=max(1,(DEADLINE-now).total_seconds()))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=3)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                code='TIMEBOX'
        text=log.read_text();stable=file_sha(DAT)==pin
        records.append(dict(command=parts,argv=argv,returncode=code,seconds=time.monotonic()-start,
            dat_sha256=pin,dat_unchanged=stable,source_sha256=dependencies,
            log=str(log.relative_to(OUT)),log_sha256=file_sha(log),
            reused='REUSE completed' in text or 'PASS existing' in text))
        state='PASS' if len(records)==24 and all(x['returncode']==0 for x in records) else 'RUNNING'
        save('optional-24-'+unit+'.json',dict(status=state,unit=unit,total=24,commands=records,
            remaining=selected[len(records):],required_for_release=False))
        print('DONE',unit,index+1,code,round(records[-1]['seconds'],1),flush=True)
    state='PASS' if len(records)==24 and all(x['returncode']==0 and x['dat_unchanged'] for x in records) else 'FAIL' if any(x['returncode'] not in (0,'TIMEBOX') for x in records) else 'INCOMPLETE_TIMEBOX'
    save('optional-24-'+unit+'.json',dict(status=state,unit=unit,total=24,commands=records,
        remaining=selected[len(records):],required_for_release=False))
    return unit,state

def main():
    os.nice(10)
    path=ROOT/'research/g122_keep_list/acceptance.json';source=json.loads(path.read_text())
    catalog={u:[[('123' if x=='122' else x) for x in row['command']] for row in source['remaining_commands'][u]] for u in UNITS}
    assert all(len(rows)==24 for rows in catalog.values())
    save('optional-24-catalog.json',dict(source=str(path.relative_to(ROOT)),source_sha256=file_sha(path),commands=catalog))
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(lambda u:run_unit(u,catalog[u]),UNITS))
    save('optional-24-summary.json',dict(status='PASS' if all(s=='PASS' for _,s in results) else 'INCOMPLETE_OR_FAILED',units=dict(results)))
    print('FINISHED optional commands',results,flush=True)
if __name__=='__main__':main()
