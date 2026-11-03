#!/usr/bin/python3
"""Run one review workload with fixed write paths and a recorded timeout."""
import json,os,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-body-reclaim-r2')
name=sys.argv[1]; seconds=int(sys.argv[2]); argv=sys.argv[3:]
assert name.replace('-','').replace('_','').isalnum()
env=os.environ.copy(); env.update(TMPDIR=str(TEMP),PYTHONDONTWRITEBYTECODE='1',CLANG_MODULE_CACHE_PATH=str(TEMP/'clang-cache'),GIT_OPTIONAL_LOCKS='0')
start=time.monotonic(); log=HERE/'local'/f'{name}.log'
with log.open('w') as stream:
 try:
  p=subprocess.run(['/usr/bin/nice','-n','10',*argv],cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=seconds)
  result=p.returncode
 except subprocess.TimeoutExpired:
  result=124
row=dict(name=name,argv=argv,returncode=result,elapsed_seconds=round(time.monotonic()-start,3),timeout_seconds=seconds,log=str(log.relative_to(HERE)))
with (HERE/'local/workloads.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
print(json.dumps(row))
if result:print(log.read_text()[-6000:])
sys.exit(result)
