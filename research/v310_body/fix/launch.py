#!/usr/bin/python3
"""Launch one bounded test, preserving output and enforcing a three-process limit."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import signal
import shlex
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-body-pack-r1')
TESTS=('rehydrate_medium.py','media_audit.py','final_collect.py','proof_branch.py','recovery_read_trace.py','recovery_trace.py','recovery_reassemble.py','h52_check.py','continue_run.py','preview_check.py','nand_check.py','studio_check.py','case_check.py','activity_run.py','cold_run.py','host_identity.py','recovery_run.py','cold_session.py','host_shutter.py','record_run.py','proof_gate.py')


def active():
    result=[]
    raw=subprocess.check_output(['/bin/ps','-axo','pid=,args='],text=True)
    for line in raw.splitlines():
        fields=line.split(None,2)
        if len(fields)<3 or Path(fields[1]).name not in ('Python','python3','python'):
            continue
        script=next((item for item in shlex.split(fields[2]) if item.endswith('.py')),None)
        if script and Path(script).name in TESTS and 'research/v310_body/' in script:
            result.append(dict(pid=int(fields[0]),command=fields[1]+' '+fields[2]))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name',required=True)
    p.add_argument('--timeout',type=int,default=7200)
    p.add_argument('--interpreter',type=Path,default=Path('/usr/bin/python3'))
    p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args()
    assert a.name.replace('-','').isalnum()
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    command=a.command[1:] if a.command and a.command[0]=='--' else a.command
    assert command and Path(command[0]).name in TESTS
    log=HERE/'evidence'/f'{a.name}.log'
    receipt=HERE/'evidence'/f'{a.name}-process.json'
    assert not log.exists() and not receipt.exists()
    started=time.monotonic()
    record=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                command=command,timeout=a.timeout,nice=os.getpriority(os.PRIO_PROCESS,0))
    with (TEMP/'launch.lock').open('a') as lock,log.open('x') as stream:
        fcntl.flock(lock,fcntl.LOCK_EX)
        running=active()
        record['active_before']=running
        if len(running)>=3:
            record.update(status='REFUSED',reason='three tests already active')
            receipt.write_text(json.dumps(record,indent=2)+'\n')
            raise SystemExit(2)
        child=subprocess.Popen([str(a.interpreter),'-I','-B',*command],cwd=ROOT,
                               stdout=stream,stderr=subprocess.STDOUT)
        record.update(pid=child.pid,status='RUNNING')
        receipt.write_text(json.dumps(record,indent=2)+'\n')
        fcntl.flock(lock,fcntl.LOCK_UN)
        try:
            code=child.wait(timeout=a.timeout)
            record.update(status='COMPLETE',exit_code=code)
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
            record.update(status='TIMEOUT',exit_code=child.returncode)
        except BaseException:
            child.terminate()
            child.wait(timeout=10)
            record.update(status='INTERRUPTED',exit_code=child.returncode)
            raise
        finally:
            record.update(seconds=time.monotonic()-started,
                          finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
            receipt.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
    raise SystemExit(record['exit_code'])


if __name__=='__main__':
    main()
