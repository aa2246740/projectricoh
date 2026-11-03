"""Cross-compiled type sizes and offline recovery identity, no device I/O."""
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import hashlib
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TASK=ROOT/'firmware/engine_v35_publish'
CAND=TASK/'candidate'
sha=lambda b:hashlib.sha256(b).hexdigest()

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
    spec=load(ROOT/'firmware/stage2l_switch/tools/build.py','review_sizes_elf')
    import sys
    sys.path.insert(0,str(CAND/'containers/product'))
    build=load(CAND/'containers/product/build.py','review_layout_build')
    obj=HERE/'target_sizes.o'
    command=[str(build.GCC),*build.FLAGS,'-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER',
             '-I',str(CAND/'containers/product'),'-I',str(ROOT/'firmware/resident_v34c/resident'),
             '-c',str(CAND/'layout.c'),'-o',str(obj)]
    result=subprocess.run(command,cwd=ROOT,env=dict(os.environ,TMPDIR=str(HERE/'tmp')),capture_output=True)
    (HERE/'target_sizes.stdout').write_bytes(result.stdout);(HERE/'target_sizes.stderr').write_bytes(result.stderr)
    assert result.returncode==0,result.stderr
    elf=spec.Elf(obj);sym=elf.symbols['v33_target_sizes'];sec=elf.sections[sym['section']]
    off=sym['value']-sec['va'];values=struct.unpack('>8I',elf.content(sec)[off:off+32])
    names=('SessionWork','PnGxts','PsStore','RvLoadWork','RvUiSnapshot','Integrated','RvSession','RV_BLOCK_OVERHEAD')
    sizes=dict(zip(names,values));expected=json.loads((HERE/'artifacts.json').read_text())['heap_model']['sizes']
    assert sizes==expected
    zip_path=ROOT/'artifacts/downloads/gxr-151.zip'
    recovery={'official_zip_sha256':sha(zip_path.read_bytes()),'members':[]}
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if Path(name).name=='ilaunch3':
                raw=archive.read(name);baseline=(ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
                changes=[i for i,(a,b) in enumerate(zip(raw,baseline)) if a!=b]
                recovery['members'].append(dict(name=name,sha256=sha(raw),bytes=len(raw),baseline_sha256=sha(baseline),
                    baseline_differing_offsets=[hex(i) for i in changes]))
    stage=ROOT/'artifacts/flash-v32/card-backup-before-v32-20261024T005033Z/root'
    body=(stage/'ilaunch3').read_bytes()
    assert sha(body)=='efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7'
    recovery['stage2l_backup']=dict(path=str(stage.relative_to(ROOT)),body_sha256=sha(body),
        body_contains_GXRCE_literal=b'GXRCE' in body,
        files={str(f.relative_to(stage)):sha(f.read_bytes()) for f in sorted(stage.rglob('*')) if f.is_file()})
    recovery['live_card_A_checked']=False
    runtime_diffs=[]
    upstream=ROOT/'firmware/resident_v34c/acceptance'
    for p in sorted((TASK/'baseline').rglob('*')):
        if not p.is_file() or 'local' in p.relative_to(TASK/'baseline').parts or p.suffix not in ('.c','.h','.S'):continue
        rel=p.relative_to(TASK/'baseline');other=upstream/rel
        if other.is_file() and other.read_bytes()!=p.read_bytes():runtime_diffs.append(str(rel))
    assert runtime_diffs==[],runtime_diffs
    (HERE/'layout_recovery.json').write_text(json.dumps(dict(status='PASS_OFFLINE',sizes=sizes,
        layout_compile=command,baseline_vs_upstream_C_H_S_differences=runtime_diffs,recovery=recovery),indent=2)+'\n')
    print('PASS independent target sizes, baseline source equality and historical Stage2l identity',flush=True)

if __name__=='__main__':main()
