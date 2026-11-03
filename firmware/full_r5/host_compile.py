"""Full C validation, 48 expanded slots, real -1 fixture flows and old GXTS."""
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c

VECTOR = r'''
#define main original_validator_main
#include "VALIDATOR"
#undef main
#include "gxts.h"
static void hex(const uint8_t *p,unsigned n){unsigned i;for(i=0;i<n;++i)printf("%02x",p[i]);}
static unsigned get32(const uint8_t *p){return (unsigned)p[0]<<24|(unsigned)p[1]<<16|(unsigned)p[2]<<8|p[3];}
int main(int argc,char **argv)
{
    Gxr2Trust trust;Gxr2View view;GxtsBinding binding;GxtsState state;
    uint8_t raw[GXR2_MAX_FILE],entry[448],encoded[GXTS_BYTES];size_t n;unsigned m,s,bank;
    if(argc!=3||!load_trust(argv[2],&trust)||!read_file(argv[1],raw,sizeof(raw),&n))return 2;
    for(m=0;m<3;++m){
        if(gxr2_validate(raw,n,&trust,&trust.modules[m].unit,0,&view)!=GXR2_OK)return 3;
        bank=get32(raw+view.sections[2].offset+64*m+16);
        for(s=1;s<=16;++s){
            if(gxr2_expand(&view,m,s,entry)!=GXR2_OK||gxts_bind(&view,m,s,&binding)!=GXTS_OK)return 4;
            gxts_defaults(&binding,&state);state.generation=7;
            if(gxts_encode(&binding,&state,encoded)!=GXTS_OK)return 5;
            printf("%u %u ",m,s);hex(entry,448);putchar(' ');hex(raw+bank+32+64*(s-1),64);
            putchar(' ');hex(binding.identity,160);putchar(' ');hex(encoded,GXTS_BYTES);putchar('\n');
        }
    }
    return 0;
}
'''


def compile_all(build):
    out = c.LOCAL / 'host'
    out.mkdir(exist_ok=True)
    flags = ['-std=c11', '-O1', '-g', '-fno-omit-frame-pointer', '-fsanitize=address,undefined',
             '-fno-sanitize-recover=all', '-Wall', '-Wextra', '-Werror', '-DRV_HOST', '-DENG_HOST',
             '-DPN_CORE_HEADER="../core/eng_core.h"', '-DPN_GXTS_SHARED_PARAMETER', '-I', c.PRODUCT]
    slim = c.RESIDENT
    rows = [r for r in build.sources() if r[0].suffix == '.c']
    rows += [(c.HERE / 'host.c', False)]
    rows += [(slim / n, False) for n in ('resident.c', 'loader.c', 'shared.c', 'hooks.c', 'runtime.c', 'validate_envelope.inc.c')]
    rows += [(c.ROOT / 'firmware/resident_v32/local/resident/trust.c', False)]
    objects = []
    for i, (src, service) in enumerate(rows):
        obj = out / (f'{i:02}-' + src.stem + '.o')
        objects.append(obj)
        extra = ['-DRV_ENGINE_SERVICES'] if service else []
        if src.name == 'runtime.c':
            extra += ['-Dmemcpy=' + ('es_memcpy' if service else 'rv_memcpy'),
                      '-Dmemset=' + ('es_memset' if service else 'rv_memset')]
        if src.name == 'gxts.c':
            extra += ['-include', build.SRC / 'firmware/engine/core/eng_crc_bindings.h']
        c.run(['/usr/bin/clang', *flags, *extra, '-I', slim, '-c', src, '-o', obj], 'host-compile-' + str(i))
    c.run(['/usr/bin/clang', *flags, *objects, '-o', out / 'host_checks'], 'host-link')
    container = build.SRC / 'firmware/card_container_v2'
    core = build.SRC / 'firmware/engine/core'
    crc = c.ROOT / 'firmware/engine_fix_r2/engine_services/crc.c'
    validator = [container / n for n in ('gate.c', 'semantic.c', 'common.c', 'api.c')]
    common = ['/usr/bin/clang', *flags, '-include', core / 'eng_crc_bindings.h', '-I', container]
    tail = [*validator, crc, c.PRODUCT / 'memory.c', core / 'eng_crc_compat.c']
    c.run([*common, container / 'validate.c', *tail, '-o', out / 'validate'], 'validator-compile')
    driver = out / 'expand.c'
    c.write(driver, VECTOR.replace('VALIDATOR', str(container / 'validate.c')).encode())
    c.run([*common, driver, container / 'gxts.c', *tail, '-o', out / 'expand'], 'expand-compile')
    return out

