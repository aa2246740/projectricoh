#!/usr/bin/python3
"""Use the first completed execution slot for the H07 parent check."""
from pathlib import Path
import argparse
import datetime
import json
import os
import select
import signal
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_g127'
PIN='9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6'

def run_batch(args):
    todo=[]
    for unit in ('28mm','mount'):
        todo.append(dict(name='history123-'+unit,kind='history123',args=[
            'research/review_g123/run_cases.py','suite','--generation','127','--unit',unit]))
        todo.append(dict(name='settings_cases-'+unit,kind='settings_cases',args=[
            'research/review_g126/settings_cases.py','--unit',unit]))
    queue=select.kqueue()
    old=set(args.children)
    running={}
    events=[]
    maximum=0
    deadline=datetime.datetime(2026,10,28,22,36,tzinfo=datetime.timezone.utc).timestamp()
    def track(pid):
        item=select.kevent(pid,filter=select.KQ_FILTER_PROC,flags=select.KQ_EV_ADD|select.KQ_EV_ONESHOT,fflags=select.KQ_NOTE_EXIT)
        queue.control([item],0,0)
    try:
        for pid in list(old):
            try:track(pid)
            except ProcessLookupError:old.remove(pid)
        while todo or running:
            while todo and len(old)+len(running)<3 and time.time()<deadline:
                job=todo.pop(0)
                cmd=['/usr/bin/sandbox-exec','-f',str(OUT/'write-fence.sb'),'/usr/bin/python3','-I','-B',
                     'research/g127_fix/run_existing.py','--fast-crc',*job['args']]
                env=dict(os.environ,TMPDIR=str(ROOT/'research/g127_fix/local/tmp'),PYTHONUNBUFFERED='1')
                proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
                running[proc.pid]=dict(job=job,proc=proc,command=cmd,start=time.monotonic(),
                    started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
                track(proc.pid)
                maximum=max(maximum,len(old)+len(running))
            if not running and not todo:
                break
            if time.time()>=deadline:
                for value in running.values():os.killpg(value['proc'].pid,signal.SIGKILL)
                todo.clear()
            limit=min([deadline]+[time.time()+max(0,4200-(time.monotonic()-value['start'])) for value in running.values()])
            ended=queue.control(None,8,max(0,limit-time.time()))
            for event in ended:
                pid=event.ident
                if pid in old:
                    old.remove(pid)
                    events.append(dict(pid=pid,original_exit_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
                    continue
                value=running.pop(pid,None)
                if value is None:continue
                raw=value['proc'].communicate()[0]
                code=value['proc'].returncode
                elapsed=round(time.monotonic()-value['start'],3)
                timed=code<0 and (elapsed>=4200 or time.time()>=deadline)
                row=dict(value['job'],command=value['command'],started_utc=value['started_utc'],
                    dat_sha256=PIN,returncode=124 if timed else code,raw_returncode=code,seconds=elapsed,
                    status='TIMEBOX' if timed else 'FINISHED' if code==0 else 'FAIL',output_bytes=len(raw),source='priority')
                with (OUT/'priority-batch-runs.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
                print(json.dumps(dict(name=row['name'],returncode=code,seconds=row['seconds'])),flush=True)
            for value in running.values():
                if time.monotonic()-value['start']>=4200:
                    os.killpg(value['proc'].pid,signal.SIGKILL)
        (OUT/'priority-batch.json').write_text(json.dumps(dict(maximum_active_commands=maximum,
            original_exits=events,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
    finally:
        queue.close()
        os.kill(args.coordinator,signal.SIGCONT)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--coordinator',type=int,required=True)
    parser.add_argument('--children',type=int,nargs='+',required=True)
    parser.add_argument('--batch',action='store_true')
    args=parser.parse_args()
    if args.batch:
        run_batch(args)
        return
    queue=select.kqueue()
    tracked=set(args.children)
    records=[]
    try:
        for pid in args.children:
            event=select.kevent(pid,filter=select.KQ_FILTER_PROC,flags=select.KQ_EV_ADD|select.KQ_EV_ONESHOT,fflags=select.KQ_NOTE_EXIT)
            try:
                queue.control([event],0,0)
            except ProcessLookupError:
                tracked.discard(pid)
        if len(tracked)==len(args.children):
            ended=queue.control(None,1,None)
            tracked.discard(ended[0].ident)
        start=time.monotonic()
        cmd=['/usr/bin/sandbox-exec','-f',str(OUT/'write-fence.sb'),'/usr/bin/python3','-I','-B',
             'research/review_g127/native_checks.py','--case','h07-parent','--unit','50mm']
        env=dict(os.environ,TMPDIR=str(ROOT/'research/g127_fix/local/tmp'))
        result=subprocess.run(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=4200)
        row=dict(name='h07-parent-rebuilt-50mm',command=cmd,returncode=result.returncode,
                 seconds=round(time.monotonic()-start,3),output_bytes=len(result.stdout),
                 remaining_original_processes_at_start=len(tracked),
                 completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        (OUT/'priority.json').write_text(json.dumps(row,indent=2)+'\n')
        print(json.dumps(dict(name=row['name'],returncode=row['returncode'],seconds=row['seconds'])),flush=True)
    finally:
        queue.close()
        os.kill(args.coordinator,signal.SIGCONT)

if __name__=='__main__':
    main()
