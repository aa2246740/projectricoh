"""Reproduce the old product failure with only native missing-open changed."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c


def main():
    c.guard();out=c.LOCAL/'before';out.mkdir(exist_ok=True)
    p=c.UPSTREAM/'containers/product'
    layout=json.loads((c.UPSTREAM/'local/product/candidates/full/layout.json').read_text())
    (out/'entries.h').write_text(''.join(f'#define OFF_{name.upper()} {offset}u\n'for name,offset in layout['entries'].items()))
    text=(p/'host_checks.c').read_text()
    old='if(i<0||(!write&&!files[i].exists))return -2;'
    assert text.count(old)==1
    text=text.replace(old,'if(i<0||(!write&&!files[i].exists))return -1;')
    text=text.replace('#include "../../local/product/entries.h"','#include "'+str(out/'entries.h')+'"')
    driver=out/'host_checks.c';driver.write_text(text)
    build=c.load(p/'build.py','frozen_before_source_list')
    rows=[r for r in build.sources()if r[0].suffix=='.c']+[(driver,False)]
    rows += [(c.RESIDENT/n,False)for n in ('resident.c','loader.c','shared.c','hooks.c','runtime.c','validate_envelope.inc.c')]
    rows += [(c.UPSTREAM/'local/resident/trust.c',False)]
    flags=['-std=c11','-O1','-g','-fno-omit-frame-pointer','-fsanitize=address,undefined',
           '-fno-sanitize-recover=all','-Wall','-Wextra','-Werror','-DRV_HOST','-DENG_HOST',
           '-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER','-I',p,'-I',c.RESIDENT]
    objects=[]
    for i,(src,service)in enumerate(rows):
        obj=out/(str(i)+'-'+src.stem+'.o');objects.append(obj);extra=[]
        if service:extra+=['-DRV_ENGINE_SERVICES']
        if src.name=='runtime.c':extra+=['-Dmemcpy='+('es_memcpy'if service else 'rv_memcpy'),
                                       '-Dmemset='+('es_memset'if service else 'rv_memset')]
        if src.name=='gxts.c':extra+=['-include',p/'src/firmware/engine/core/eng_crc_bindings.h']
        c.run(['/usr/bin/clang',*flags,*extra,'-c',src,'-o',obj],'before-compile-'+str(i))
    binary=out/'checks';c.run(['/usr/bin/clang','-fsanitize=address,undefined',*objects,'-o',binary],'before-link')
    folder=c.UPSTREAM/'local/product/candidates/full';checks=[]
    for unit in range(3):
        r=c.run([binary,'flow',unit,folder/'GXRCE.DAT',folder/'GXRCE.DAT',folder/'trust.bin',
                 folder/'effective-rows.bin',folder/'effective-rows.bin'],f'before-native-minus1-{unit}',check=False)
        assert r.returncode==1 and 'state=6 fault=-5' in r.stderr
        checks.append(dict(unit=unit,expected_failure=True,returncode=r.returncode,output=r.stderr.strip()))
    c.save(c.LOCAL/'baseline-native-minus1.json',dict(checks=checks,actual_frozen_sources=True,
        only_fixture_change='Missing native read-only open returns -1 instead of -2',
        source_hashes={str(src.relative_to(c.ROOT)):c.sha(src)for src,_ in rows}))
    print('PASS expected pre-fix failures: 3/3 units, frozen engine/resident C, native missing=-1')


if __name__=='__main__':main()
