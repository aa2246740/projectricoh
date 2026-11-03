"""Compare actual R2 and R3 C modules using final packaged DAT bytes."""
from pathlib import Path
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g152/equivalence')
OLD=ROOT/'firmware/engine_v58_g150/candidate/containers/product'
NEW=ROOT/'firmware/engine_v60_g152/candidate/containers/product'
sys.path.insert(0,str(HERE))
from dat_format import expand,expand_effect,strict_effects,u32,sha

def run(command,timeout=2400):
    t=time.monotonic()
    p=subprocess.run(list(map(str,command)),cwd=ROOT,capture_output=True,text=True,timeout=timeout,check=True,
                     env=dict(os.environ,TMPDIR=str(TMP),CLANG_MODULE_CACHE_PATH=str(TMP/'clang-cache')))
    return p.stdout,time.monotonic()-t

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    TMP.mkdir(parents=True,exist_ok=True);started=time.time_ns()
    old=(ROOT/'firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT').read_bytes()
    dat=(ROOT/'firmware/package_v38_g152/local/SD_ROOT/GXRCE.DAT').read_bytes()
    strict_effects(dat)
    (TMP/'old.bin').write_bytes(old[u32(old,204)+3392:u32(old,204)+3392+17384])
    (TMP/'new.bin').write_bytes(dat[u32(dat,204)+3392:u32(dat,204)+3392+7904])
    (TMP/'old_entries.bin').write_bytes(b''.join(expand(old,u,s) for u in range(3) for s in range(1,9)))
    (TMP/'new_entries.bin').write_bytes(b''.join(expand(dat,u,s) for u in range(3) for s in range(1,9)))
    (TMP/'effects.bin').write_bytes(b''.join(expand_effect(dat,e) for _ in range(3) for e in range(10)))
    request_old=(OLD/'kv2/kv_data.c').read_text().split('\nint kv_data_request(',1)[1]
    request_new=(NEW/'kv2/kv_data.c').read_text().split('\nint kv_data_request(',1)[1]
    assert request_old==request_new
    assert (OLD/'kv2/kv_math.c').read_bytes()==(NEW/'kv2/kv_math.c').read_bytes()
    names=sorted(set(re.findall(r'\b(kv_data_\w+)\s*\(',(OLD/'kv2/kv_data.c').read_text())))
    ui_names=sorted(set(re.findall(r'\b(kv_ui_\w+)\s*\(',(NEW/'kv2/kv_ui.c').read_text())))
    objects=[];commands=[]
    for label,origin in (('old',OLD),('new',NEW)):
        dest=TMP/label;dest.mkdir(exist_ok=True)
        for name in ('kv_data.c','kv_data.h','kv_ui.c','kv_ui.h','kv_math.c','kv_math.h'):
            (dest/name).write_bytes((origin/'kv2'/name).read_bytes())
        macros=[f'-D{name}={label}_{name}' for name in names+ui_names]
        for name in ('kv_data','kv_ui','kv_math'):
            obj=dest/(name+'.o')
            command=['/usr/bin/clang','-std=c11','-O2','-fno-builtin','-Wall','-Wextra','-Werror',*macros,
                     '-Dkv_apply_work='+label+'_kv_apply_work','-c',dest/(name+'.c'),'-o',obj]
            run(command);commands.append(list(map(str,command)));objects.append(obj)
    text=(NEW/'../../engine_services/crc.c').read_text()
    text=text[text.index('uint32_t gxr2_crc_add'):text.index('uint32_t rv_crc_update')]
    common=(NEW/'src/firmware/card_container_v2/common.c').read_text()
    common=common[common.index('uint32_t gxr2_crc_begin'):common.index('Gxr2Row gxr2_raw_row')]
    window=(NEW/'ui_v2_data.c').read_text()
    window=window[window.index('void __attribute__((noinline)) uv_window'):window.index('const uint8_t *uv_extension')]
    (TMP/'support.c').write_text('#include "kv_ui.h"\ntypedef KvUiWindow UvWindow;\nenum {UV_PHYSICAL=8};\n'+text+common+window)
    command=['/usr/bin/clang','-std=c11','-O2','-fno-builtin','-Wall','-Wextra','-Werror','-I'+str(TMP/'old'),
             HERE/'host_equivalence.c',TMP/'support.c',*objects,'-o',TMP/'compare']
    run(command);commands.append(list(map(str,command)))
    command=[TMP/'compare',TMP/'old.bin',TMP/'new.bin',TMP/'old_entries.bin',TMP/'new_entries.bin',TMP/'effects.bin']
    stdout,seconds=run(command);result=json.loads(stdout)
    result.update(status='PASS',dat_sha256=sha(dat),test_dat_sha256=sha((ROOT/'firmware/package_v38_g152_test/local/SD_ROOT/GXRCE.DAT').read_bytes()),
                  started_ns=started,ended_ns=time.time_ns(),comparison_seconds=seconds,
                  request_function_unchanged=True,request_function_sha256=sha(request_old.encode()),
                  math_source_unchanged=True,math_source_sha256=sha((NEW/'kv2/kv_math.c').read_bytes()),
                  composition='Every control metadata and complete level/dose sequence agree. The unchanged request function independently assigns Amount or one dose field, rejects any missing level and rejects nondefault hidden controls. Thus every legal vector produces the same request; invalid vectors leave output unchanged.',
                  final_scope='552 bytes including all nine rows, T, row 14 and CRC fields, using final packed builtin bases and all ten final effect bases for each unit.',
                  commands=commands)
    (HERE/'evidence/kv_equivalence.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='commands'}))

if __name__=='__main__':main()
