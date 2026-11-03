#!/usr/bin/python3
"""Run the retained per-unit suites and record completed commands."""
from pathlib import Path
import concurrent.futures,hashlib,json,os,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'research/g127_fix'
DAT=ROOT/'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT'
PIN=hashlib.sha256(DAT.read_bytes()).hexdigest()
jobs=[]
for family in (126,124):
    for unit in ('50mm','28mm','mount'):
        params=['--fast-crc',f'research/review_g{family}/batch.py','--unit',unit,'--tag','g127-final']
        if family==126:params+=['--groups','suite','safety','locked','nested','cutpoints','exits','transitions','values','view-reentry','reentry-six','users','other-users','project','labels','half']
        jobs.append((f'suite{family}-{unit}',params))
for unit in ('50mm','28mm','mount'):
    jobs.append((f'cold-{unit}',['research/review_g126/cold_reentry.py','--generation','127','--unit',unit]))
    options=['--postcheck','research/g127_fix/ownership_reopen.py']
    jobs.append((f'ownership-{unit}',options+['research/review_g126/ownership_settings.py','--generation','127','--unit',unit]))
def run(job):
    name,params=job
    command=['/usr/bin/python3','-I','-B',str(WORK/'run_existing.py')]+params
    start=time.monotonic()
    with (WORK/'local'/('final-'+name+'.log')).open('w') as log:
        try:code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=1450).returncode
        except subprocess.TimeoutExpired:code=124
    assert hashlib.sha256(DAT.read_bytes()).hexdigest()==PIN
    result={'name':name,'command':command,'dat_sha256':PIN,'returncode':code,'seconds':round(time.monotonic()-start,3)}
    return result
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    for future in concurrent.futures.as_completed([pool.submit(run,x) for x in jobs]):
        result=future.result()
        with (WORK/'evidence/native-commands.jsonl').open('a') as stream:stream.write(json.dumps(result)+'\n')
        print(json.dumps(result),flush=True)
