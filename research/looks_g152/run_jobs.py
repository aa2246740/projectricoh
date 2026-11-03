"""Run at most two foreground test children with completion-driven waits."""
from pathlib import Path
import argparse
import asyncio
import datetime
import hashlib
import json
import os
import signal
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g152')
sys.path.insert(0,str(HERE))
from controller_guard import controller_lease

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

async def run(job,semaphore,lease_fd):
    async with semaphore:
        target=HERE/'evidence/jobs';target.mkdir(exist_ok=True)
        receipt=target/(job['name']+'.json');log=target/(job['name']+'.log')
        assert not receipt.exists() and not log.exists(),'Use a new job name.'
        dat=ROOT/'firmware/package_v38_g152_test/local/SD_ROOT/GXRCE.DAT'
        command=['/usr/bin/nice','-n','10','/usr/bin/sandbox-exec','-f',str(HERE/'offline.sb'),
                 job.get('python','/usr/bin/python3'),'-I','-B',str(HERE/job['script']),*job.get('args',[])]
        environment=dict(os.environ,TMPDIR=str(TMP),REVIEW_JOB=job['name'],PYTHONDONTWRITEBYTECODE='1',
                         G139_ENGINE='firmware/engine_v60_g152',G139_PACKAGE='firmware/package_v38_g152_test',
                         G150_RELEASE_PACKAGE='firmware/package_v38_g152',G150_TEST_PACKAGE='firmware/package_v38_g152_test')
        environment.update(job.get('env',{}))
        environment['G152_CONTROLLER_LEASE_FD']=str(lease_fd)
        started=time.time_ns();tick=time.monotonic();result=dict(job=job,dat_sha256=digest(dat),started_ns=started,command=command,
            scripts={p.name:digest(p) for p in HERE.glob('*.py')},outputs=[])
        print(json.dumps(dict(event='start',job=job['name'],started_ns=started)),flush=True)
        cancelled=False
        with log.open('wb') as stream:
            spawning=asyncio.create_task(asyncio.create_subprocess_exec(*command,cwd=ROOT,env=environment,stdout=stream,
                stderr=asyncio.subprocess.STDOUT,start_new_session=True,pass_fds=(lease_fd,)))
            try:process=await asyncio.shield(spawning)
            except asyncio.CancelledError:
                process=await spawning;cancelled=True
            result['pid']=process.pid;result['controller_pid']=os.getpid()
            try:
                if cancelled:raise asyncio.CancelledError()
                result['returncode']=await asyncio.wait_for(process.wait(),job.get('timeout',10800))
            except (asyncio.TimeoutError,asyncio.CancelledError) as error:
                cancelled=isinstance(error,asyncio.CancelledError)
                if process.returncode is None:
                    try:os.killpg(process.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                await process.wait();result['returncode']='INTERRUPTED' if cancelled else 'TIMEOUT'
        result.update(ended_ns=time.time_ns(),seconds=time.monotonic()-tick,log_sha256=digest(log))
        for name in job.get('outputs',[]):
            path=HERE/name;row=dict(path=name,exists=path.is_file())
            if path.is_file():
                row.update(sha256=digest(path),mtime_ns=path.stat().st_mtime_ns,fresh=path.stat().st_mtime_ns>=started)
                if path.suffix=='.json':row['status']=json.loads(path.read_text()).get('status')
            result['outputs'].append(row)
        result['status']='PASS' if result['returncode']==0 and all(row.get('fresh') and row.get('status','PASS').startswith(('PASS','OBSERVED')) for row in result['outputs']) else 'FAIL'
        receipt.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(event='finish',job=job['name'],status=result['status'],seconds=result['seconds'])),flush=True)
        if cancelled:raise asyncio.CancelledError()
        return result

async def main():
    p=argparse.ArgumentParser();p.add_argument('queue');p.add_argument('--slots',type=int,choices=(1,2),default=2);args=p.parse_args()
    jobs=json.loads((HERE/args.queue).read_text());semaphore=asyncio.Semaphore(args.slots)
    with controller_lease(jobs) as lease_fd:
        main_task=asyncio.current_task();loop=asyncio.get_running_loop()
        for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,main_task.cancel)
        tasks=[asyncio.create_task(run(job,semaphore,lease_fd)) for job in jobs]
        try:results=await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            await asyncio.gather(*tasks,return_exceptions=True)
            raise
        except BaseException:
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            raise
    out=dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL',jobs=len(results),slots=args.slots,
             generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),results=results)
    (HERE/'evidence'/(Path(args.queue).stem+'-complete.json')).write_text(json.dumps(out,indent=2)+'\n')
    if out['status']!='PASS':raise SystemExit(1)

if __name__=='__main__':asyncio.run(main())
