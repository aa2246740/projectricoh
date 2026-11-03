"""Run bounded jobs serially; a failed C case is replayed on Python."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['negative','unit','restart-native']);args=p.parse_args()
    guard();assert os.getpriority(os.PRIO_PROCESS,0)>=15
    records=[];logs=HERE/'local/runlogs';logs.mkdir(exist_ok=True)
    def run(name,script,options,backend='c',timeout=3600):
        command=['/usr/bin/python3','-I','-B',str(HERE/script),*options]
        started=time.monotonic()
        proc=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
            timeout=timeout,env=dict(os.environ,GXR_HARNESS_BACKEND=backend))
        (logs/(name+'.log')).write_text(proc.stdout)
        records.append(dict(name=name,backend=backend,returncode=proc.returncode,seconds=time.monotonic()-started,command=command))
        print(json.dumps({k:v for k,v in records[-1].items() if k!='command'}),flush=True)
        return proc.returncode
    if args.stage=='negative':
        for unit,prefix in [('mount','m'),('50mm','j'),('28mm','q')]:
            for kind in ('header-crc','payload-crc','effect-crc'):
                name=prefix+'-'+kind+'-final-c'
                opts=['--snapshot',str(HERE/'local/cold'/(prefix+'-final-cold')/'standby.snap.z'),
                    '--unit',unit,'--name',name,'--dat',str(HERE/'local/host'/(kind+'.DAT')),'--reject']
                code=run(name,'local/native_from_cold.py',opts)
                if code:
                    opts[opts.index(name)]=name+'-python'
                    run(name+'-python','local/native_from_cold.py',opts,'python')
                    raise AssertionError('C rejection failed; Python replay retained: '+name)
    elif args.stage=='unit':
        for backend in ('c','python'):
            name='unit-final-'+backend
            code=run(name,'local/unit_checks.py',['--name',name],backend)
            if code and backend=='c':
                run(name+'-replay','local/unit_checks.py',['--name',name+'-replay'],'python')
            assert code==0,name
        c=json.loads((HERE/'local/unit/unit-final-c/result.json').read_text())
        py=json.loads((HERE/'local/unit/unit-final-python/result.json').read_text());assert c['units']==py['units']
    else:
        for unit,prefix in [('mount','m'),('50mm','j'),('28mm','q')]:
            name=prefix+'-restart-native-final-c'
            opts=['--snapshot',str(HERE/'local/cold'/(prefix+'-restart-final')/'standby.snap.z'),
                '--unit',unit,'--name',name,'--initial-only']
            code=run(name,'local/native_from_cold.py',opts)
            if code:
                opts[opts.index(name)]=name+'-python';run(name+'-python','local/native_from_cold.py',opts,'python')
            assert code==0,name
    save(HERE/'evidence'/(args.stage+'.json'),dict(status='PASS',jobs=records,
        dat_sha256=sha((PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes()),parallel_jobs=1))


if __name__=='__main__':main()
