#!/usr/bin/python3
"""Wait for the control exit and use its released slot for one observed continuation."""
import datetime
import json
import os
from pathlib import Path
import select
import signal
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
P='research/v310_body/fix/'


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    receipt=json.loads((HERE/'evidence/restore-v39-word-process.json').read_text())
    if receipt['status']=='RUNNING':
        q=select.kqueue()
        try:q.control([select.kevent(receipt['pid'],filter=select.KQ_FILTER_PROC,
            flags=select.KQ_EV_ADD|select.KQ_EV_ONESHOT,fflags=select.KQ_NOTE_EXIT)],1,None)
        except ProcessLookupError:pass
        finally:q.close()
    source=json.loads((HERE/'evidence/trace-input.json').read_text())['path']
    args=['/usr/bin/python3','-I','-B',P+'launch.py','--name','restore-v39-checksum-trace',
        '--timeout','14400','--',P+'recovery_trace.py','--name','restore-v39-checksum-trace',
        '--image','firmware/package_v39_g154_test/local/SD_ROOT/ilaunch3','--word-columns',
        '--resume',source,'--budget','800000000','--timeout','14400']
    child=subprocess.Popen(args,cwd=ROOT,start_new_session=True)
    deadline=datetime.datetime(2026,11,2,7,40,tzinfo=datetime.timezone.utc)
    remaining=(deadline-datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    try:code=child.wait(timeout=max(1,remaining))
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=30);raise RuntimeError('global time box reached')
    print(json.dumps(dict(trace_exit_code=code,controlled_boundary_expected=True)),flush=True)


if __name__=='__main__':main()
