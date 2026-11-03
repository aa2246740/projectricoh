#!/usr/bin/python3
"""Run cold cases and their independent checks sequentially within one test slot."""
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PREFIX='research/v310_body/fix/'
DEADLINE=datetime.datetime(2026,11,2,7,45,tzinfo=datetime.timezone.utc)


def run(name,command,timeout=7200):
    seconds=(DEADLINE-datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    if seconds<=0:raise RuntimeError('task time box reached')
    args=['/usr/bin/python3','-I','-B',PREFIX+'launch.py','--name',name,'--timeout',str(timeout),'--',*command]
    child=subprocess.Popen(args,cwd=ROOT,start_new_session=True)
    try:code=child.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=30)
        raise RuntimeError('task time box reached during '+name)
    if code:raise RuntimeError(name+' returned '+str(code))


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    for recipe,unit in [('mount-builtin','mount'),('mount-look','mount'),('mount-user','mount'),
                        ('28mm-builtin','28mm'),('50mm-user','50mm')]:
        name='valid-'+recipe+'-r5'
        print(json.dumps(dict(start=name)),flush=True)
        run(name,[PREFIX+'record_run.py','--name',name,'--unit',unit,
            '--dat','firmware/package_v310_g155b_test/local/SD_ROOT/GXRCE.DAT',
            '--settings-source',PREFIX+'local/'+recipe+'-settings.bin',
            '--expected-target',PREFIX+'local/'+recipe+'-target.bin',
            '--word-columns','--preview-link','--budget','1000000000','--timeout','7200'])
        run('check-'+name,[PREFIX+'case_check.py','--name',name,'--unit',unit,
            '--recipe',recipe,'--expect','apply'],900)
        print(json.dumps(dict(completed=name)),flush=True)


if __name__=='__main__':main()
