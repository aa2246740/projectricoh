"""Offline g158 build and verification boundaries."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'research/g158'
LOCAL = HERE/'local'
ENGINE = ROOT/'firmware/engine_v70_g158'
BASE = ROOT/'firmware/engine_v69_g157'
PRODUCT = ENGINE/'candidate/containers/product'
BODY = ROOT/'firmware/resident_v310_g155'
PACKAGES = {p: ROOT/('firmware/package_v310_g158'+('_test' if p == 'test' else '')) for p in ('test','release')}
GCC = ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD = ROOT/'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
OBJDUMP = ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
ALLOWED = (HERE, ENGINE, *PACKAGES.values())
UNITS = ('50mm','28mm','mount')
RESTORE = ('Agfa LeBox','Y2K Plady','QianXi A','QianXi B','ARRI 709','Eterna BB','RED IPP2','Acros')
DATASET = os.environ.get('G158_DATASET','control')
def artifact(profile,dataset=None):
    dataset=dataset or DATASET
    assert dataset in ('control','model') and profile in PACKAGES
    package=PACKAGES[profile]/'local/variants'/dataset
    return dict(package=package,dat=package/'SD_ROOT/GXRCE.DAT',manifest=package/'MANIFEST',
        build=ENGINE/'candidate/local'/(dataset+'-'+('boot-on' if profile=='test' else 'boot-off')),
        records=LOCAL/('records.json' if dataset=='control' else 'model-records-'+profile+'.json'))
def receipt(name): return LOCAL/'acceptance'/DATASET/name

def sha(raw): return hashlib.sha256(raw).hexdigest()
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
def save(path, value):
    def plain(v):
        if isinstance(v,dict):return {(k if isinstance(k,(str,int,float,bool)) or k is None else repr(k)):plain(x) for k,x in v.items()}
        if isinstance(v,(list,tuple)):return [plain(x) for x in v]
        if isinstance(v,(set,frozenset)):return [plain(x) for x in sorted(v,key=repr)]
        return v
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_name(path.name+'.tmp-'+str(os.getpid()))
    temporary.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, default=lambda v: v.hex() if isinstance(v,bytes) else str(v))+'\n')
    temporary.replace(path)
def setup():
    assert os.getpriority(os.PRIO_PROCESS,0) >= 15, 'use nice -n 15'
    info = plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert info['MountPoint']=='/Volumes/Workspace'
    assert info['FilesystemType']=='apfs' and info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['WritableVolume'] and os.path.ismount('/Volumes/Workspace')
    assert all(not p.is_symlink() for p in ALLOWED)
    sys.dont_write_bytecode = True
    def audit(event,args):
        if event in ('socket.connect','socket.bind','socket.getaddrinfo'): raise PermissionError('g158 offline')
        paths=[]
        if event=='open':
            path,mode,flags=args
            if isinstance(path,(str,bytes,os.PathLike)) and os.fsdecode(path).startswith(('/dev/disk','/dev/rdisk')): raise PermissionError('physical device fence')
            if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND): paths=[path]
        elif event in ('os.mkdir','os.remove','os.rmdir','os.chmod','os.truncate','os.utime'): paths=[args[0]]
        elif event in ('os.rename','os.link','os.symlink'): paths=list(args[:2])
        for path in paths:
            if isinstance(path,(str,bytes,os.PathLike)):
                target=Path(os.fsdecode(path)).resolve()
                if target!=Path('/dev/null') and not any(target.is_relative_to(p) for p in ALLOWED): raise PermissionError('g158 write fence: '+str(target))
    sys.addaudithook(audit)
    (LOCAL/'tmp').mkdir(parents=True,exist_ok=True)
    os.environ.update(TMPDIR=str(LOCAL/'tmp'),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',
        CLANG_MODULE_CACHE_PATH=str(LOCAL/'tmp/modules'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
def compute_gate(label):
    sys.path.insert(0,str(ROOT/'tools'))
    import loadgate
    output=subprocess.check_output(['uptime'],text=True).strip()
    workers,info=loadgate.workers()
    with (LOCAL/'load.jsonl').open('a') as f: f.write(json.dumps(dict(label=label,uptime=output,load1=info['load1'],pid=os.getpid(),nice=os.getpriority(os.PRIO_PROCESS,0),info=info,admission_policy='tools/loadgate.py'))+'\n')
    if not workers: raise RuntimeError('LOAD_DEFERRED '+json.dumps(info))
    return workers
def run(args,label,**kwargs):
    logs=LOCAL/'logs';logs.mkdir(exist_ok=True)
    result=subprocess.run([str(x) for x in args],cwd=ROOT,text=True,capture_output=True,env=dict(os.environ,LC_ALL='C'),timeout=kwargs.get('timeout',1200))
    (logs/(label+'.log')).write_text(result.stdout+result.stderr)
    with (LOCAL/'commands.jsonl').open('a') as f: f.write(json.dumps(dict(label=label,argv=list(map(str,args)),returncode=result.returncode))+'\n')
    if kwargs.get('check',True) and result.returncode: raise RuntimeError(label+': '+(result.stdout+result.stderr)[-5000:])
    return result
D = load(ROOT/'research/v39_g153/dat_format.py','g158_dat_format')
