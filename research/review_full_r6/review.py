"""Independent frozen-candidate review. All writes stay in this directory."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
BUILDER = ROOT / 'firmware/engine_v33b'
PRODUCT = BUILDER / 'containers/product'
PREVIOUS = ROOT / 'firmware/engine_fix_r2'
RESIDENT = ROOT / 'firmware/resident_v32/resident'
CARD = BUILDER / 'local/card_update/GXRCE.DAT'
OLD = PREVIOUS / 'local/product/candidates/full-r3'
R5 = ROOT / 'firmware/full_r5/local/full-r5'
NEW = BUILDER / 'local/full-r6'
RES_ELF = ROOT / 'firmware/resident_v32/local/resident/build/resident.elf'
APPROVED = ROOT / 'firmware/image_v3/local/candidate-v32/candidate/SD_ROOT/ilaunch3'
TC = ROOT / 'research/tooling_m32r/prefix/bin'
GCC = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD = ROOT / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write(p, data):
    p = Path(p)
    p.resolve().relative_to(HERE)
    assert not p.is_symlink()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode())

def save(p, data):
    write(p, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n')

def run(args, label, timeout=120, allow_failure=False):
    env = dict(os.environ, TMPDIR=str(LOCAL/'tmp'), LC_ALL='C',
               PYTHONDONTWRITEBYTECODE='1', CLANG_MODULE_CACHE_PATH=str(LOCAL/'tmp/modules'),
               ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1', GIT_OPTIONAL_LOCKS='0')
    r = subprocess.run([str(a) for a in args], cwd=ROOT, env=env,
                       text=True, capture_output=True, timeout=timeout)
    write(LOCAL/'logs'/(label+'.log'), r.stdout + r.stderr)
    with (LOCAL/'commands.jsonl').open('a') as f:
        f.write(json.dumps(dict(label=label, argv=[str(a) for a in args], rc=r.returncode))+'\n')
    if not allow_failure:
        assert r.returncode == 0, label + ': ' + r.stdout[-1500:] + r.stderr[-2000:]
    return r

def guard():
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_full_r6')
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert info['MountPoint']=='/Volumes/Workspace' and info['FilesystemType']=='apfs'
    assert info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['WritableVolume'] and info['WritableMedia'] and os.access('/Volumes/Workspace',os.W_OK)
    df = subprocess.check_output(['/bin/df','-h','/Volumes/Workspace'], text=True)
    (LOCAL/'tmp').mkdir(parents=True,exist_ok=True)
    ignore = subprocess.check_output(['git','check-ignore','-v',str(LOCAL/'probe')],cwd=ROOT,text=True)
    assert '/local/' in ignore
    if not (LOCAL/'preflight.json').exists():
        save(LOCAL/'preflight.json', dict(volume={k:info[k] for k in ('MountPoint','FilesystemType','VolumeUUID','WritableVolume','WritableMedia')},df=df,ignore=ignore))

def snapshot():
    paths = set()
    trees = [BUILDER, PREVIOUS, ROOT/'firmware/full_r4', ROOT/'firmware/full_r5',
             ROOT/'firmware/resident_v32', ROOT/'research/review_full_r4',
             ROOT/'research/review_engine_fix_r2']
    for tree in trees:
        paths.update(p for p in tree.rglob('*') if p.is_file())
    paths.update([APPROVED, TC/'m32r-elf-objdump', GCC, LD])
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths) if p.name!='decisions.tsv'}

def freeze():
    assert not (LOCAL/'inputs-before.json').exists(), 'Never overwrite initial evidence'
    before = snapshot()
    save(LOCAL/'inputs-before.json', before)
    write(LOCAL/'git-tracked-before.txt', subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=no'],cwd=ROOT))
    diffs=[]
    for tree in ('containers/product','engine_services'):
        for p in sorted((BUILDER/tree).rglob('*')):
            if not p.is_file(): continue
            relative=p.relative_to(BUILDER);old=PREVIOUS/relative
            if not old.exists() or sha(old)!=sha(p):
                diffs.append(dict(path=str(relative),old=sha(old) if old.exists() else None,new=sha(p)))
                if old.exists():
                    run(['/usr/bin/diff','-u',old,p], 'diff-'+str(relative).replace('/','-'), allow_failure=True)
    save(LOCAL/'source-differences.json', diffs)
    print('frozen', len(before), 'inputs;',len(diffs),'source differences')

def unchanged():
    before=json.loads((LOCAL/'inputs-before.json').read_text())
    after=snapshot()
    assert before==after, [p for p in before.keys()|after.keys() if before.get(p)!=after.get(p)]
    return len(before)

def load(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

if __name__=='__main__':
    guard()
    phase=sys.argv[1]
    if phase=='freeze': freeze()
    elif phase=='check': print('unchanged', unchanged())
    else:
        unchanged()
        sys.path.insert(0,str(HERE))
        load(HERE/'checks.py','review_checks').main(phase)
        print('unchanged', unchanged())
