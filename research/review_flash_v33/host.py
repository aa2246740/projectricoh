"""Compile frozen product C for host verification; never build firmware."""
import hashlib
import importlib.util
import json
import re
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
import review as c
import artifacts as a
ACCEPT=c.ROOT/'firmware/resident_v33/acceptance'
PRODUCT=ACCEPT/'containers/product'
RES=c.ROOT/'firmware/resident_v33/resident'
HOST=c.LOCAL/'host'
FINAL=ACCEPT/'local/full-r9'
FLAGS=['-std=c11','-O1','-g','-fno-omit-frame-pointer','-fsanitize=address,undefined',
    '-fno-sanitize-recover=all','-Wall','-Wextra','-Werror','-DRV_HOST','-DENG_HOST',
    '-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER',
    '-DACCEPTANCE_GENERATION=111','-DACCEPTANCE_03_MODE=1',
    '-DACCEPTANCE_ENTRIES_HEADER="'+str(ACCEPT/'local/product-r9/entries.h')+'"',
    '-DACCEPTANCE_REVIEW_SUPPORT="'+str(c.LOCAL/'review_support.c')+'"',
    '-DACCEPTANCE_ADDITIONAL_SUPPORT="'+str(c.LOCAL/'additional_support.c')+'"',
    '-I',str(PRODUCT),'-I',str(RES),'-I',str(ACCEPT),'-I',str(c.LOCAL)]

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def source_list():
    src=PRODUCT/'src';core=src/'firmware/engine/core';panel=src/'firmware/engine/panel';cont=src/'firmware/card_container_v2'
    rows=[(PRODUCT/'adapter.c',False),(PRODUCT/'memory.c',False)]
    rows += [(core/n,False) for n in ('eng_core.c','eng_data.c','eng_crc_compat.c','eng_semantic.c','eng_pin_stub.c','eng_mem.c')]
    rows += [(panel/n,False) for n in ('panel.c','panel_ui.c','panel_native.c','panel_port.c','panel_store.c','panel_gxts.c','panel_gxts_bind.c')]
    rows += [(cont/n,False) for n in ('gate.c','common.c','api.c','gxts.c','gxts_io.c')]
    rows += [(src/'research/recipe_tweak/r2/tweak_int.c',False)]
    rows += [(ACCEPT/'engine_services'/n,True) for n in ('services.c','api.c','runtime.c','crc.c','mark.c','native_seed.c')]
    rows += [(RES/'shared.c',True)]
    rows += [(RES/n,False) for n in ('resident.c','loader.c','shared.c','hooks.c','runtime.c','validate_envelope.inc.c')]
    rows += [(c.ROOT/'firmware/resident_v33/local/resident/trust.c',False)]
    return rows

def compile_driver(name,source,extra=()):
    objects=json.loads((HOST/'objects.json').read_text())
    obj=HOST/(name+'.o')
    c.run(['/usr/bin/clang',*FLAGS,*extra,'-c',source,'-o',obj], 'logs/compile-'+name+'.log')
    c.run(['/usr/bin/clang',*FLAGS,*objects,obj,'-o',HOST/name], 'logs/link-'+name+'.log')

def compile_all():
    HOST.mkdir(parents=True,exist_ok=True)
    # Preserve the original driver and apply only a main rename, locally.
    support=(ACCEPT/'host_v33.c').read_text()
    for name,newmain in [('review_support.c','inherited_v33_main'),('additional_support.c','v33_fixture_main')]:
        assert support.count('int main(int argc,char **argv)')==1
        (c.LOCAL/name).write_text(support.replace('int main(int argc,char **argv)','int '+newmain+'(int argc,char **argv)'))
    for name in ('native_enum.h','native_get_mode.h'):
        shutil.copyfile(ACCEPT/'local'/name,c.LOCAL/name)
    objects=[];proof=[]
    for i,(source,service) in enumerate(source_list()):
        obj=HOST/(f'{i:02}-'+source.stem+'.o');objects.append(str(obj))
        extra=['-DRV_ENGINE_SERVICES'] if service else []
        if source.name=='runtime.c':
            extra+=['-Dmemcpy='+('es_memcpy' if service else 'rv_memcpy'),'-Dmemset='+('es_memset' if service else 'rv_memset')]
        if source.name=='gxts.c':extra+=['-include',PRODUCT/'src/firmware/engine/core/eng_crc_bindings.h']
        c.run(['/usr/bin/clang',*FLAGS,*extra,'-c',source,'-o',obj], 'logs/compile-'+str(i)+'.log')
        proof.append(dict(source=str(source.relative_to(c.ROOT)),sha256=c.digest(source),service=service,object_sha256=c.digest(obj)))
    (HOST/'objects.json').write_text(json.dumps(objects))
    c.write('host-source-proof.json',proof)
    for name in ('host_checks','host_legacy','host_review','host_v33','host_r6_cases','host_revision','host_first_frame','host_r9','host_additional'):
        source=ACCEPT/('host.c' if name=='host_checks' else name+'.c')
        compile_driver(name,source)
    compile_driver('host_upgrade_real',ACCEPT/'host_first_frame.c',['-DSTRICT_OLD_CARD'])
    compile_driver('host_upgrade_pair',ACCEPT/'host_first_frame.c',['-DSTRICT_OLD_CARD','-DPAIRED_OLD_IROM'])
    # Compile independent complete C expansion without importing or running a packer.
    vector=module(ACCEPT/'host_compile.py','expand_template').VECTOR
    cont=PRODUCT/'src/firmware/card_container_v2';core=PRODUCT/'src/firmware/engine/core'
    driver=HOST/'expand.c';driver.write_text(vector.replace('VALIDATOR',str(cont/'validate.c')))
    c.run(['/usr/bin/clang',*FLAGS,'-include',core/'eng_crc_bindings.h','-I',cont,driver,
        *[cont/n for n in ('gate.c','semantic.c','common.c','api.c','gxts.c')],
        ACCEPT/'engine_services/crc.c',PRODUCT/'memory.c',core/'eng_crc_compat.c','-o',HOST/'expand'], 'logs/compile-expand.log')
    print('PASS independently compiled frozen C objects and 11 drivers',flush=True)

RESULTS=[]
def execute(binary,scenario,unit,extra=(),folder=None,label=None):
    folder=folder or c.LOCAL/'compat/109'
    label=label or '-'.join(map(str,(binary,scenario,unit,*extra)))
    out=c.run([HOST/binary,scenario,unit,folder/'GXRCE.DAT',FINAL/'GXRCE.DAT',FINAL/'trust.bin',
        folder/'effective-rows.bin',FINAL/'effective-rows.bin',*extra], 'flows/'+label+'.log')
    match=re.search(r'OK .*assertions=(\d+)',out.splitlines()[-1]);assert match,out[-2000:]
    RESULTS.append(dict(label=label,assertions=int(match[1]),log='local/flows/'+label+'.log',
        safety_outcome='COUNTEREXAMPLE' if 'GUARD_PERSISTED' in out else 'EXPECTED_ASSERTIONS'))
    return out

def prepare():
    import zlib
    # Historical same-trust fixtures test data migration only; unmodified originals test trust changes separately.
    originals={105:c.ROOT/'firmware/engine_fix_r2/local/product/candidates/full-r3',106:c.ROOT/'firmware/full_r4/local/full-r4',
        107:c.ROOT/'firmware/full_r5/local/full-r5',108:c.ROOT/'firmware/engine_v33b/local/full-r6',
        109:c.ROOT/'firmware/engine_v33d/local/full-r7',110:ACCEPT/'local/full-r8'}
    final=(FINAL/'GXRCE.DAT').read_bytes()
    for gen,source in originals.items():
        target=c.LOCAL/'compat'/str(gen);target.mkdir(parents=True,exist_ok=True)
        old=(source/'GXRCE.DAT').read_bytes();raw=bytearray(old);raw[80:112]=final[80:112]
        raw[20:24]=bytes(4);struct.pack_into('>I',raw,20,zlib.crc32(raw[:256]))
        assert raw[256:]==old[256:]
        (target/'GXRCE.DAT').write_bytes(raw)
        shutil.copyfile(source/'effective-rows.bin',target/'effective-rows.bin')
        trust=bytearray((source/'trust.bin').read_bytes());trust[40:72]=final[80:112];(target/'trust.bin').write_bytes(trust)
    c.write('compatibility-fixtures.json',dict(production=False,description='Only the trust header and header CRC change. Historical machine code is not executed.',sources={str(k):str(v) for k,v in originals.items()}))
    print('PASS host-only historical fixtures prepared')
    return originals

def first_frame():
    for policy in (0,1):
        for unit in (0,2):
            for memory in range(9):
                for action in (0,1,2):execute('host_first_frame','matrix',unit,[policy,memory,action])
            execute('host_first_frame','movement',unit,[policy])
        execute('host_first_frame','matrix',1,[policy,0,2])

def upgrades():
    originals=json.loads((c.LOCAL/'compatibility-fixtures.json').read_text())['sources']
    for gen,path in originals.items():
        for binary in ('host_upgrade_real','host_upgrade_pair'):
            for policy in (0,1):
                for unit in range(3):
                    for state in ((0,1,2,3) if unit!=1 else (0,)):
                        execute(binary,'actual-upgrade',unit,[policy,state],Path(path),f'{binary}-{gen}-{policy}-{unit}-{state}')

def regressions():
    for policy in (0,1):
        for unit in (0,2):
            for scenario in ('remember03','remember05','remember-corrupt','remember-stale','remember-missing','remember-unreadable','remember-hidden09','remember-hidden10','invalid-row-0','invalid-row-9','invalid-row-16'):
                execute('host_v33',scenario,unit,[policy])
            for scenario in ('parent-empty','parent-remember03','poison-write-panel','poison-write-same','poison-rename-panel','poison-close-same','survivor-A','survivor-B','survivor-AB','write-frequency'):
                execute('host_r6_cases',scenario,unit,[policy],c.LOCAL/'compat/105')
            execute('host_revision','write-policy',unit,[policy],c.LOCAL/'compat/105')
            for stage in (5,15,6,7):
                for key in (0,1,2):execute('host_revision','forced-during',unit,[policy,stage,key],c.LOCAL/'compat/105')
            for scenario in ('power','transitions'):execute('host_r9',scenario,unit,[policy])
            for gen in range(105,111):
                execute('host_r9','migration03',unit,[policy],Path(json.loads((c.LOCAL/'compatibility-fixtures.json').read_text())['sources'][str(gen)]),f'migrate-{gen}-{policy}-{unit}')
        for unit in range(3):
            for scenario in ('partial-both','direct-repeat'):execute('host_additional',scenario,unit,[policy],c.LOCAL/'compat/105')

def faults():
    traces=[]
    for kind in ('tweak','last'):
        for initial in (0,1,2):
            out=execute('host_v33','trace-'+kind,0,[1,initial])
            counts={int(op):int(n) for op,n in re.findall(r'op(\d+)=(\d+)',out)}
            traces.append(dict(kind=kind,initial=initial,operations=counts))
            for unit in (0,2):
                for policy in (0,1):
                    for op in range(2,9):
                        for ordinal in range(1,counts[op]+1):
                            for code in (-1,-2):execute('host_v33','fault-'+kind,unit,[policy,initial,op,ordinal,code])
    c.write('fault-traces.json',traces)

def guard():
    support=(ACCEPT/'host_first_frame.c').read_text().replace('int main(int argc,char **argv)','int inherited_first_frame_main(int argc,char **argv)')
    (c.LOCAL/'first_frame_support.c').write_text(support)
    compile_driver('guard_attacks',c.HERE/'guard_attacks.c')
    original=c.ROOT/'firmware/engine_v33d/local/full-r7'
    for unit in (0,2):
        for policy in (0,1):
            for scenario in ('browse','explicit'):
                for op,code in ((2,-2),(2,-1),(6,-2),(6,-1)):
                    execute('guard_attacks',scenario,unit,[policy,op,code],original)

if __name__=='__main__':
    phase=sys.argv[1]
    {'compile':compile_all,'prepare':prepare,'first-frame':first_frame,'upgrades':upgrades,
     'regressions':regressions,'faults':faults,'guard':guard}[phase]()
    c.write('host-'+phase+'.json',dict(status='PASS',runs=len(RESULTS),assertions=sum(r['assertions'] for r in RESULTS),cases=RESULTS))
    print('PASS',phase,'host runs',len(RESULTS),flush=True)
