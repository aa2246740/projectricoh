#!/usr/bin/env python3
"""Sanitized resident+engine acceptance against final packed candidates."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import HERE, ROOT, LOCAL, SRC, guard, run
import build

def compile_host():
    out=LOCAL/'host';out.mkdir(exist_ok=True)
    layouts=[json.loads((LOCAL/'candidates'/variant/'layout.json').read_text()) for variant in ('base','huzi')]
    assert layouts[0]['entries']==layouts[1]['entries']
    (LOCAL/'entries.h').write_text(''.join(f'#define OFF_{k.upper()} {v}u\n' for k,v in layouts[0]['entries'].items()))
    flags=['-std=c11','-O1','-g','-fno-omit-frame-pointer','-fsanitize=address,undefined',
           '-fno-sanitize-recover=all','-Wall','-Wextra','-Werror','-DRV_HOST','-DENG_HOST',
           '-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER','-I',str(HERE)]
    rows=[r for r in build.sources() if r[0].suffix=='.c']
    rows += [(HERE/'host_checks.c',False)]
    slim=SRC/'firmware/resident_slim'
    rows += [(slim/n,False) for n in ('resident.c','loader.c','shared.c','runtime.c','validate_envelope.inc.c')]
    rows += [(LOCAL/'resident-trust.c',False)]
    objects=[]
    for i,(src,service) in enumerate(rows):
        obj=out/(f'{i:02}-'+src.stem+'.o');objects.append(obj);extra=[]
        if service:extra+=['-DRV_ENGINE_SERVICES']
        if src.name=='runtime.c':extra+=['-Dmemcpy='+('es_memcpy' if service else 'rv_memcpy'),'-Dmemset='+('es_memset' if service else 'rv_memset')]
        if src.name=='gxts.c':extra+=['-include',str(SRC/'firmware/engine/core/eng_crc_bindings.h')]
        run(['cc',*flags,*extra,'-I',slim,'-c',src,'-o',obj],'host-compile-'+str(i))
    run(['cc',*flags,*objects,'-o',out/'host_checks'],'host-link')
    container=SRC/'firmware/card_container_v2'
    validator=[container/n for n in ('validate.c','gate.c','semantic.c','common.c','api.c')]
    run(['cc',*flags,'-include',SRC/'firmware/engine/core/eng_crc_bindings.h',*validator,HERE/'memory.c',
         SRC/'firmware/engine/core/eng_crc_compat.c','-o',out/'validate'],'validator-compile')
    return out

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--compile-only',action='store_true');a=parser.parse_args()
    guard();out=compile_host()
    if a.compile_only:return
    env={'ASAN_OPTIONS':'detect_leaks=0:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
    candidates=LOCAL/'candidates';base=candidates/'base';huzi=candidates/'huzi'
    checks=[]
    for folder in (base,huzi):
        for name in ('jlaunch','qlaunch','l08firm'):
            p=run([out/'validate',folder/'GXRCE.DAT',folder/'trust.bin',name],f'validate-{folder.name}-{name}',env=env)
            checks.append(dict(kind='full-c-validator',variant=folder.name,unit=name,output=p.stdout.strip()))
    scenarios=('flow','badcrc','bad-layout','bad-tweak','image-limit','truncated','readfail','rename-install','rename-mark','alloc-main','alloc-work',
               'notify-load','notify-write','notify-rpc','notify-panel')
    for scenario in scenarios:
        for unit in range(3):
            p=run([out/'host_checks',scenario,unit,base/'GXRCE.DAT',huzi/'GXRCE.DAT',base/'trust.bin',base/'effective-rows.bin',huzi/'effective-rows.bin'],f'e2e-{scenario}-{unit}',env=env)
            checks.append(dict(kind='e2e',scenario=scenario,unit=unit,output=p.stdout.strip()))
    (LOCAL/'acceptance.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(f'PASS: {len(checks)} checks, complete C validator + ASan/UBSan resident/engine flow')

if __name__=='__main__':main()
