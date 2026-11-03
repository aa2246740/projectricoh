"""Shared task-local guards; never imports or invokes another task's writers."""
import hashlib
import importlib.util
import os
from pathlib import Path
import plistlib
import subprocess
import time
import json
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LOCAL=HERE/'local'
def guard():
    volume=Path('/Volumes/Workspace')
    info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(volume)]))
    if (info.get('MountPoint')!=str(volume) or info.get('VolumeUUID')!='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
        or info.get('FilesystemType')!='apfs' or not info.get('WritableVolume') or not os.access(volume,os.W_OK)):
        raise RuntimeError('Workspace mount/APFS/UUID/writable mismatch')
    LOCAL.resolve().relative_to(HERE)
    r=subprocess.run(['git','check-ignore','-v',str(LOCAL/'probe.bin')],cwd=ROOT,capture_output=True,text=True,check=True)
    if 'firmware/engine/core/.gitignore:1:/local/' not in r.stdout: raise RuntimeError(r.stdout)
    (LOCAL/'tmp').mkdir(parents=True,exist_ok=True)
    os.environ['TMPDIR']=str(LOCAL/'tmp')
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
def load(path,name):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); sys.modules[name]=m; s.loader.exec_module(m); return m
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(args,label):
    p=subprocess.run([str(x) for x in args],cwd=ROOT,capture_output=True,text=True)
    (LOCAL/(label+'.log')).write_text(p.stdout+p.stderr)
    record=dict(label=label,argv=[str(x) for x in args],returncode=p.returncode)
    with (LOCAL/'commands.jsonl').open('a') as log: log.write(json.dumps(record)+'\n')
    if p.returncode:
        failures=LOCAL/'failures'; failures.mkdir(exist_ok=True)
        (failures/(label+'-'+str(time.time_ns())+'.log')).write_text(p.stdout+p.stderr)
    if p.returncode: raise RuntimeError(f'{label}: exit={p.returncode}\n{(p.stdout+p.stderr)[-2200:]}')
    return p.stdout
