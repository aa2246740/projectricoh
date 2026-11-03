#!/usr/bin/python3
"""Wait for a recovery worker exit, then use its released test slot serially."""
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
DEADLINE=datetime.datetime(2026,11,2,7,45,tzinfo=datetime.timezone.utc)


def run(name,command,timeout=14400,backend='c'):
    remaining=(DEADLINE-datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    if remaining<=0:raise RuntimeError('global time box reached')
    env=dict(os.environ,GXR_HARNESS_BACKEND=backend)
    child=subprocess.Popen(['/usr/bin/python3','-I','-B',P+'launch.py','--name',name,
        '--timeout',str(timeout),'--',*command],cwd=ROOT,env=env,start_new_session=True)
    try:code=child.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=30)
        raise RuntimeError('global time box reached during '+name)
    print(json.dumps(dict(name=name,exit_code=code)),flush=True)
    return code


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    receipt=json.loads((HERE/'evidence/restore-v310-word-process.json').read_text())
    if receipt['status']=='RUNNING':
        pid=receipt['pid']
        queue=select.kqueue()
        try:
            queue.control([select.kevent(pid,filter=select.KQ_FILTER_PROC,
                flags=select.KQ_EV_ADD|select.KQ_EV_ONESHOT,fflags=select.KQ_NOTE_EXIT)],1,None)
        except ProcessLookupError:pass
        finally:queue.close()
    for unit in ('mount','28mm','50mm'):
        name='identity-'+unit+'-g155b-c'
        code=run(name,[P+'host_identity.py','--name',name,'--unit',unit])
        if code:
            run(name+'-python',[P+'host_identity.py','--name',name+'-python','--unit',unit],backend='python')
            raise RuntimeError('identity C case did not pass')
    name='identity-28mm-g155b-python'
    if run(name,[P+'host_identity.py','--name',name,'--unit','28mm'],backend='python'):
        raise RuntimeError('identity Python case did not pass')
    name='gate-cross-unit'
    if run(name,[P+'record_run.py','--name',name,'--unit','50mm',
        '--dat','firmware/package_v310_g155b_test/local/SD_ROOT/GXRCE.DAT',
        '--settings-source',P+'local/50mm-cross-unit-settings.bin','--word-columns','--preview-link',
        '--budget','500000000','--timeout','7200'],7200):raise RuntimeError('cross-unit run stopped')
    if run('check-gate-cross-unit',[P+'case_check.py','--name',name,'--unit','50mm','--expect','cross-unit'],900):
        raise RuntimeError('cross-unit acceptance stopped')
    name='restore-v39-legacy-negative'
    run(name,[P+'recovery_run.py','--name',name,
        '--image','firmware/package_v39_g154_test/local/SD_ROOT/ilaunch3',
        '--resume',P+'local/recovery-restore-v39-checkpoint-1003175242.pkl.z',
        '--budget','1200000000','--timeout','14400'])
    name='h52-real-mount'
    if run(name,[P+'record_run.py','--name',name,'--unit','mount',
        '--dat','firmware/package_v310_g155b_test/local/SD_ROOT/GXRCE.DAT',
        '--settings-source',P+'local/mount-look-settings.bin',
        '--expected-target',P+'local/mount-look-target.bin','--word-columns','--preview-link',
        '--shutter-during-dirty','--budget','1000000000','--timeout','7200'],7200):
        raise RuntimeError('actual DIRTY run stopped')
    run('check-h52-real-mount',[P+'case_check.py','--name',name,'--unit','mount',
        '--recipe','mount-look','--expect','apply'],900)
    for unit in ('mount','28mm','50mm'):
        name='release-'+unit+'-g155b'
        run(name,[P+'cold_run.py','--name',name,'--unit',unit,
            '--dat','firmware/package_v310_g155b/local/SD_ROOT/GXRCE.DAT',
            '--budget','500000000','--timeout','7200'],7200)


if __name__=='__main__':main()
