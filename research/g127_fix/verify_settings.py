#!/usr/bin/python3
"""Exercise the retained settings and H07 cases on the final package."""
from pathlib import Path
import concurrent.futures,hashlib,json,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'research/g127_fix'
DAT=ROOT/'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT'
PIN=hashlib.sha256(DAT.read_bytes()).hexdigest()
def run(job):
    name,unit=job
    command=['/usr/bin/python3','-I','-B',str(WORK/'run_existing.py'),'--fast-crc',f'research/review_g126/{name}.py','--unit',unit]
    start=time.monotonic()
    with (WORK/'local'/('release-'+name+'-'+unit+'.log')).open('w') as log:
        try:code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=1000).returncode
        except subprocess.TimeoutExpired:code=124
    assert hashlib.sha256(DAT.read_bytes()).hexdigest()==PIN
    return {'name':name+'-'+unit,'command':command,'dat_sha256':PIN,'returncode':code,'seconds':round(time.monotonic()-start,3)}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    for future in concurrent.futures.as_completed([pool.submit(run,(n,u)) for n in ('settings_cases','cold_exit') for u in ('50mm','28mm','mount')]):
        result=future.result()
        with (WORK/'evidence/settings-commands.jsonl').open('a') as stream:stream.write(json.dumps(result)+'\n')
        print(json.dumps(result),flush=True)
