"""Run bounded acceptance stages serially; preserve each output and exit code."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def main():
    guard();logs=HERE/'local/runlogs';logs.mkdir(exist_ok=True);jobs=[]
    def run(name,script,args=(),timeout=1800):
        python=ROOT/'studio/.venv/bin/python' if script=='page_pixels.py' else Path('/usr/bin/python3')
        command=[str(python),'-I','-B',str(HERE/script),*args]
        started=time.monotonic()
        with (logs/(name+'.log')).open('w') as stream:
            proc=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout,
                env=dict(os.environ,GXR_HARNESS_BACKEND='c'))
        row=dict(name=name,returncode=proc.returncode,seconds=time.monotonic()-started)
        jobs.append(row);print(json.dumps(row),flush=True)
        assert proc.returncode==0,name
    run('page-pixels','page_pixels.py',timeout=300)
    run('python-codec','python_checks.py',timeout=300)
    run('restart-inputs','prepare_restart.py',timeout=300)
    for unit,prefix in [('mount','m'),('50mm','j'),('28mm','q')]:
        run(prefix+'-restart-cold','local/cold.py',[
            '--unit',unit,'--name',prefix+'-restart-final','--snapshot-only',
            '--settings-source',str(HERE/'local/restart-inputs'/(unit+'.bin'))],timeout=1800)
    run('negative-menus','run_checks.py',['negative'],timeout=1800)
    run('restart-menus','run_checks.py',['restart-native'],timeout=1800)
    run('unit-packers','run_checks.py',['unit'],timeout=1800)
    run('byte-rebuild','reproduce.py',timeout=1800)
    save(HERE/'evidence/serial-jobs.json',dict(status='PASS',dat_sha256=sha((PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes()),
        jobs=jobs,nice=os.getpriority(os.PRIO_PROCESS,0),parallel_jobs=1))


if __name__=='__main__':main()
