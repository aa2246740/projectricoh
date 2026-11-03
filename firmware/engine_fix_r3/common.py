"""Engine-only r3 build and evidence boundary."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local'
UP=ROOT/'firmware/engine_fix_r2'
PRODUCT=HERE/'containers/product'
RESIDENT=ROOT/'firmware/resident_v32/resident'
OLD=UP/'local/product/candidates/full-r3'
R4=ROOT/'firmware/full_r4/local/full-r4'
OUT=LOCAL/'full-r6'
TREES=('firmware/engine_fix_r1','firmware/engine_fix_r2','firmware/resident_v32',
       'firmware/full_r4','research/review_full_r4','firmware/stage2l_switch/tools',
       'research/huzi_luts/local/best_candidates','research/mount_calib_r1/local/entries')
EXPLICIT=('firmware/image_v3/local/candidate-v32/candidate/SD_ROOT/ilaunch3',
 'artifacts/firmware/gxr-1.51/ilaunch3',
 'research/gr4_nega_returns_r1/local/candidate/DEEPTBL_50mm_gr4_posi_nega_r1.DAT',
 'research/gr4_nega_returns_r1/local/mount/candidate/DEEPTBL_mount_gr4_posi_nega_r1.DAT',
 'research/gr4_dense_returns_r1/local/candidate/DEEPTBL_50mm_gr4_positive_r1.DAT',
 'research/gr4_dense_returns_r1/local/mount/candidate/DEEPTBL_mount_gr4_positive_r1.DAT',
 'research/stage2l_leica_0708/local/DEEPTBL_v6_leica.DAT',
 'research/refit_50mm_r7/local/v6/candidate_v6.DEEPTBL',
 'research/mount_calib_r1/local/DEEPTBL_mount_calibrated.DAT')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,name):
 spec=importlib.util.spec_from_file_location(name,p)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def write(p,data):
 p=Path(p);p.resolve().relative_to(HERE)
 assert not p.is_symlink() and not HERE.is_symlink()
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 assert p.read_bytes()==data

def save(p,obj):write(p,(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())

def guard():
 assert HERE==Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/engine_fix_r3')
 info=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
 assert info['MountPoint']=='/Volumes/Workspace' and info['FilesystemType']=='apfs'
 assert info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
 assert info['WritableVolume'] and info['WritableMedia'] and os.access('/Volumes/Workspace',os.W_OK)
 df=subprocess.check_output(['/bin/df','-h','/Volumes/Workspace'],text=True)
 (LOCAL/'tmp').mkdir(parents=True,exist_ok=True)
 ignore=subprocess.check_output(['git','check-ignore','-v',str(LOCAL/'probe')],cwd=ROOT,text=True)
 assert '/local/' in ignore
 save(LOCAL/'preflight.json',dict(volume={k:info[k] for k in ('MountPoint','FilesystemType','VolumeUUID','WritableVolume','WritableMedia')},df=df,ignore=ignore))

def snapshot():
 paths=set(ROOT/p for p in EXPLICIT)
 for tree in TREES:paths.update(p for p in (ROOT/tree).rglob('*') if p.is_file() and p.name!='decisions.tsv')
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}

def freeze():
 guard();p=LOCAL/'inputs-before.json';assert not p.exists()
 values=snapshot();save(p,values);print('frozen',len(values),'inputs; decisions.tsv excluded')

def unchanged():
 before=json.loads((LOCAL/'inputs-before.json').read_text());after=snapshot()
 changes=[p for p in before.keys()|after.keys() if before.get(p)!=after.get(p)]
 extra=LOCAL/'supplemental-inputs.json'
 if extra.exists():
  changes += [p for p,h in json.loads(extra.read_text()).items() if sha(ROOT/p)!=h]
 save(LOCAL/'scope.json',dict(unchanged=not changes,protected_files=len(before),changes=changes))
 assert not changes, 'STOP: protected inputs changed: '+repr(changes)
 return len(before)

def run(args,label,timeout=180,check=True,env=None):
 environment=dict(os.environ,TMPDIR=str(LOCAL/'tmp'),LC_ALL='C',PYTHONDONTWRITEBYTECODE='1',
 CLANG_MODULE_CACHE_PATH=str(LOCAL/'tmp/modules'),ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
 UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',GIT_OPTIONAL_LOCKS='0')
 environment.update(env or {})
 r=subprocess.run([str(a) for a in args],cwd=ROOT,env=environment,capture_output=True,text=True,timeout=timeout)
 write(LOCAL/'logs'/(label+'.log'),(r.stdout+r.stderr).encode())
 with (LOCAL/'commands.jsonl').open('a') as f:f.write(json.dumps(dict(label=label,argv=[str(a) for a in args],rc=r.returncode))+'\n')
 if check:assert r.returncode==0,label+': '+r.stdout[-1500:]+r.stderr[-3000:]
 return r

if __name__=='__main__':freeze()

GCC=ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'

LD=ROOT/'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'

OBJDUMP=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
