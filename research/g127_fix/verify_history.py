#!/usr/bin/python3
"""Run earlier failure cases against the final package."""
from pathlib import Path
import concurrent.futures,hashlib,json,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'research/g127_fix'
DAT=ROOT/'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT'
PIN=hashlib.sha256(DAT.read_bytes()).hexdigest()
jobs=[(g,u) for g in (122,123) for u in ('50mm','28mm','mount') ]
def run(job):
    generation,unit=job
    name=f'history{generation}-{unit}'
    command=['/usr/bin/python3','-I','-B',str(WORK/'run_existing.py'),'--fast-crc']+(['--reference-expectations'] if generation==122 else [])+[f'research/review_g{generation}/run_cases.py','suite','--generation','121' if generation==122 else '127','--unit',unit]
    start=time.monotonic()
    with (WORK/'local'/('final-'+name+'.log')).open('w') as log:
        try:code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=1200).returncode
        except subprocess.TimeoutExpired:code=124
    assert hashlib.sha256(DAT.read_bytes()).hexdigest()==PIN
    return {'name':name,'command':command,'dat_sha256':PIN,'returncode':code,'seconds':round(time.monotonic()-start,3)}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    for future in concurrent.futures.as_completed([pool.submit(run,x) for x in jobs]):
        result=future.result()
        with (WORK/'evidence/history-commands.jsonl').open('a') as stream:stream.write(json.dumps(result)+'\n')
        print(json.dumps(result),flush=True)
