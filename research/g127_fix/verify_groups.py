#!/usr/bin/python3
"""Run independent retained regression groups with bounded workers."""
from pathlib import Path
import concurrent.futures,hashlib,json,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'research/g127_fix'
DAT=ROOT/'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT'
PIN=hashlib.sha256(DAT.read_bytes()).hexdigest()
common=('safety','locked','nested','cutpoints','exits','transitions','values','view-reentry','reentry-six','users','project','labels','half')
jobs=[(g,u,part) for g in (126,124) for u in ('50mm','28mm','mount') for part in common+(('other-users',) if g==126 else ())]
def run(job):
    generation,unit,part=job
    name=f'group{generation}-{unit}-{part}'
    command=['/usr/bin/python3','-I','-B',str(WORK/'run_existing.py'),'--fast-crc',f'research/review_g{generation}/batch.py','--unit',unit,'--groups',part,'--tag','split127']
    start=time.monotonic()
    with (WORK/'local'/('release-'+name+'.log')).open('w') as log:
        try:code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=950).returncode
        except subprocess.TimeoutExpired:code=124
    assert hashlib.sha256(DAT.read_bytes()).hexdigest()==PIN
    return {'name':name,'command':command,'dat_sha256':PIN,'returncode':code,'seconds':round(time.monotonic()-start,3)}
with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
    for future in concurrent.futures.as_completed([pool.submit(run,x) for x in jobs]):
        result=future.result()
        with (WORK/'evidence/groups-commands.jsonl').open('a') as stream:stream.write(json.dumps(result)+'\n')
        print(json.dumps(result),flush=True)
