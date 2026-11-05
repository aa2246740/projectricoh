"""Offline write fence and load admission shared by this probe's tools."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import plistlib
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/lut_shadow_probe_r2'
LOCAL=HERE/'local'
ENGINE=ROOT/'firmware/engine_lutprobe_r2'
PACKAGE=ROOT/'firmware/package_v310_lutprobe_r2'
BASE=ROOT/'firmware/engine_v69_g157'
BODY=ROOT/'firmware/image_v310/local/ilaunch3'
RESIDENT=ROOT/'firmware/resident_v310_g155'
GCC=ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD=ROOT/'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
OBJDUMP=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
ALLOWED=(HERE,ENGINE,PACKAGE,ROOT/'tools/gxr_emulator_fast/strict_r4/panel.py',
         ROOT/'tools/gxr_emulator_fast/strict_r4/NATIVE_REGISTRY.json')
GENERATION=192
DEADLINE='2026-11-05T16:56:20Z'

def sha(data): return hashlib.sha256(data).hexdigest()
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module
    spec.loader.exec_module(module); return module
loadgate=load(ROOT/'tools/loadgate.py','lutprobe_shared_loadgate')
def save(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp-'+str(os.getpid()))
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n'); tmp.replace(path)
def setup():
    assert sys.flags.isolated, 'firmware Python requires -I'
    assert os.getpriority(os.PRIO_PROCESS,0)>=15, 'use nice -n 15'
    info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert info['FilesystemType']=='apfs' and info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['WritableVolume'] and os.path.ismount('/Volumes/Workspace')
    assert all(not p.is_symlink() for p in ALLOWED)
    sys.dont_write_bytecode=True
    def audit(event,args):
        if event in ('socket.connect','socket.bind','socket.getaddrinfo'): raise PermissionError('probe is offline')
        paths=[]
        if event=='open':
            path,mode,flags=args
            if isinstance(path,(str,bytes,os.PathLike)) and os.fsdecode(path).startswith(('/dev/disk','/dev/rdisk')):
                raise PermissionError('physical device fence')
            if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND): paths=[path]
        elif event in ('os.mkdir','os.remove','os.rmdir','os.chmod','os.truncate','os.utime'): paths=[args[0]]
        elif event in ('os.rename','os.link','os.symlink'): paths=list(args[:2])
        for path in paths:
            if isinstance(path,(str,bytes,os.PathLike)):
                target=Path(os.fsdecode(path)).resolve()
                if target!=Path('/dev/null') and not any(target.is_relative_to(p) for p in ALLOWED):
                    raise PermissionError('probe write fence: '+str(target))
    sys.addaudithook(audit)
    (LOCAL/'tmp').mkdir(parents=True,exist_ok=True)
    os.environ.update(TMPDIR=str(LOCAL/'tmp'),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',
        CLANG_MODULE_CACHE_PATH=str(LOCAL/'tmp/modules'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
def _admission(label,count,info):
    with (LOCAL/'load.jsonl').open('a') as f:
        f.write(json.dumps(dict(label=label,load1=info['load1'],nice=os.getpriority(os.PRIO_PROCESS,0),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),info=info))+'\n')
    deadline=os.environ.get('LUTPROBE_ACTIVE_DEADLINE_UTC')
    if deadline and time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())>=deadline: raise RuntimeError('TASK_DEADLINE')
    if not count: raise RuntimeError('LOAD_DEFERRED '+json.dumps(info,sort_keys=True))
    return count
def gate(label):
    count,info=loadgate.workers()
    return _admission(label,count,info)
def run(argv,label,timeout=1200,check=True):
    result=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,text=True,timeout=timeout,
                          env=dict(os.environ,LC_ALL='C'))
    (LOCAL/'logs').mkdir(exist_ok=True)
    (LOCAL/'logs'/(label+'.log')).write_text(result.stdout+result.stderr)
    if check and result.returncode: raise RuntimeError(label+': '+(result.stdout+result.stderr)[-6000:])
    return result
