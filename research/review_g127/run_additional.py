#!/usr/bin/python3
"""Start supplemental checks on the coordinator exit event, without polling."""
from pathlib import Path
import argparse
import concurrent.futures
import datetime
import json
import os
import select
import signal
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_g127'
PY=['/usr/bin/python3','-I','-B']
DEADLINE=datetime.datetime(2026,10,28,22,42,tzinfo=datetime.timezone.utc).timestamp()

def jobs():
    yield dict(name='crc-native-rebound',expected=0,args=[
        'research/g127_fix/run_existing.py','--postcheck','research/review_g127/crc_reopen.py',
        'research/review_g126/ownership_settings.py','--generation','127','--unit','50mm'])
    for case in ('preview-window','settings-check','h07-parent'):
        yield dict(name='repeat-'+case+'-mount',expected=0,args=[
            'research/review_g127/native_checks.py','--case',case,'--unit','mount'])
    for unit in ('50mm','28mm'):
        yield dict(name='repeat-settings-check-'+unit,expected=0,args=[
            'research/review_g127/native_checks.py','--case','settings-check','--unit',unit])
    for unit in ('50mm','28mm','mount'):
        yield dict(name='preview-deferred-'+unit,expected=0,args=[
            'research/review_g127/native_checks.py','--case','preview-deferred','--unit',unit])
    yield dict(name='pending-read-50mm',expected=0,args=[
        'research/review_g127/native_checks.py','--case','pending-read','--unit','50mm'])
    yield dict(name='plain-ascii-control',expected=0,args=['research/review_g127/binding_probe.py'])
    yield dict(name='rebound-ascii-control',expected=1,args=[
        'research/g127_fix/run_existing.py','research/review_g127/binding_probe.py'])
    yield dict(name='rebound-assertion-control',expected=1,args=[
        'research/g127_fix/run_existing.py','research/review_g127/binding_probe.py','--case','assertion'])

def run(job):
    started=time.monotonic()
    cmd=['/usr/bin/sandbox-exec','-f',str(OUT/'write-fence.sb'),*PY,*job['args']]
    if time.time()>=DEADLINE:
        return dict(job,returncode=None,seconds=0,status='NOT_STARTED',command=cmd)
    env=dict(os.environ,TMPDIR=str(ROOT/'research/g127_fix/local/tmp'),PYTHONUNBUFFERED='1')
    proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        raw=proc.communicate(timeout=min(4200,max(1,DEADLINE-time.time())))[0]
        code=proc.returncode
        status='PASS' if code==job['expected'] else 'FAIL'
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid,signal.SIGKILL)
        raw=proc.communicate()[0]
        code=124
        status='TIMEBOX'
    return dict(job,returncode=code,seconds=round(time.monotonic()-started,3),status=status,
                command=cmd,output_bytes=len(raw),PASS=int(status=='PASS'),FAIL=int(status=='FAIL'))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--after-pid',type=int,required=True)
    args=parser.parse_args()
    pending=list(jobs())
    (OUT/'additional-plan.json').write_text(json.dumps(dict(after_pid=args.after_pid,
        workers=3,timeout_seconds=4200,deadline_utc='2026-10-28T22:42:00+00:00',jobs=pending),indent=2)+'\n')
    queue=select.kqueue()
    event=select.kevent(args.after_pid,filter=select.KQ_FILTER_PROC,
                       flags=select.KQ_EV_ADD|select.KQ_EV_ONESHOT,fflags=select.KQ_NOTE_EXIT)
    try:
        queue.control([event],1,None)
    except ProcessLookupError:
        pass
    finally:
        queue.close()
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for future in concurrent.futures.as_completed([pool.submit(run,job) for job in pending]):
            row=future.result()
            rows.append(row)
            (OUT/'additional.json').write_text(json.dumps(rows,indent=2)+'\n')
            print(json.dumps({key:row.get(key) for key in ('name','returncode','seconds','PASS','FAIL','status')}),flush=True)

if __name__=='__main__':
    main()
