import asyncio
import datetime as dt
import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_v38_g137'
QUEUE=OUT/sys.argv[1]
LIMIT=int(sys.argv[2]) if len(sys.argv)>2 else 1
assert 1<=LIMIT<=3
jobs=json.loads(QUEUE.read_text())
names=[job['name'] for job in jobs]
if len(names)!=len(set(names)):raise SystemExit('Duplicate job names; choose unique names before running.')
existing=[name for name in names if (OUT/'evidence/receipts'/f'{name}.json').exists() or (OUT/'local/jobs'/name).exists()]
if existing:raise SystemExit('Existing job results; choose fresh names and empty job folders: '+', '.join(existing))
(OUT/'evidence/receipts').mkdir(exist_ok=True)
gate=None
budget_file=OUT/'evidence/resume-budget.json'
DEADLINE=(dt.datetime.fromisoformat(json.loads(budget_file.read_text())['deadline_utc']) if budget_file.exists()
          else dt.datetime(2026,10,30,8,56,28,tzinfo=dt.timezone.utc))
async def run(job):
    async with gate:
        started=time.monotonic()
        worker_sha=hashlib.sha256((OUT/'legacy_call.py').read_bytes()).hexdigest()
        env=dict(os.environ);env.update(job.get('env',{}))
        env['UBSAN_OPTIONS']='halt_on_error=1:print_stacktrace=0'
        env['ASAN_OPTIONS']='halt_on_error=1:detect_leaks=0'
        command=['sandbox-exec','-f',str(OUT/'offline.sb'),'/usr/bin/python3','-I','-B',str(OUT/'legacy_call.py'),job['name'],*job['args']]
        print(json.dumps({'event':'start','name':job['name'],'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'timeout':4200}),flush=True)
        process=await asyncio.create_subprocess_exec(*command,cwd=str(ROOT),env=env,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,start_new_session=True,limit=4*1024*1024)
        async def output():
            with (OUT/'local'/f'{job["name"]}.log').open('w') as stream:
                while True:
                    line=await process.stdout.readline()
                    if not line:break
                    text=line.decode('utf-8','replace')
                    if text.startswith('    ') and not text.lstrip().startswith('File '):continue
                    stream.write(text);stream.flush()
            return await process.wait()
        status='DONE'
        available=max(0.01,(DEADLINE-dt.datetime.now(dt.timezone.utc)).total_seconds())
        try:code=await asyncio.wait_for(output(),timeout=min(4200,available))
        except asyncio.TimeoutError:
            status='TIMEBOX' if available<4200 else 'TIMEOUT';os.killpg(process.pid,signal.SIGKILL);code=await process.wait()
        result={'name':job['name'],'returncode':code,'status':status,'seconds':round(time.monotonic()-started,3),
                'args':job['args'],'env':job.get('env',{}),'timeout_seconds':4200,'pid':process.pid,
                'utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                'worker_sha256':worker_sha}
        receipt=OUT/'evidence/receipts'/f'{job["name"]}.json'
        assert not receipt.exists()
        receipt.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(result,event='finish')),flush=True)
        return result
async def main():
    global gate
    gate=asyncio.Semaphore(LIMIT)
    results=await asyncio.gather(*(run(job) for job in jobs))
    print(json.dumps({'event':'complete','jobs':len(results),'nonzero':sum(r['returncode']!=0 for r in results)}),flush=True)
asyncio.run(main())
