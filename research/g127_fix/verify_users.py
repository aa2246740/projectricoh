from pathlib import Path
import concurrent.futures,hashlib,json,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'research/g127_fix'
PIN=hashlib.sha256((ROOT/'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT').read_bytes()).hexdigest()
jobs=[(g,u,n) for g in (124,126) for u in ('50mm','28mm','mount') for n in (('user_acceptance','other_users') if g==126 else ('user_acceptance',))]
def run(job):
 g,u,n=job;name=f'users{g}-{u}-{n}'
 command=['/usr/bin/python3','-I','-B',str(WORK/'run_existing.py'),'--fast-crc',f'research/review_g{g}/{n}.py','--unit',u]
 with (WORK/'local'/('release-'+name+'.log')).open('w') as log:
  try:code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=800).returncode
  except subprocess.TimeoutExpired:code=124
 return {'name':name,'command':command,'returncode':code,'dat_sha256':PIN}
with concurrent.futures.ThreadPoolExecutor(max_workers=9) as pool:
 for f in concurrent.futures.as_completed([pool.submit(run,x) for x in jobs]):
  result=f.result()
  with (WORK/'evidence/users-commands.jsonl').open('a') as stream:stream.write(json.dumps(result)+'\n')
  print(json.dumps(result),flush=True)
