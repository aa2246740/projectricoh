"""Independent host compilation, selected regressions, and adversarial probes."""
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c

OUT = c.LOCAL / 'host'
FLAGS = ['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function',
         '-fno-omit-frame-pointer','-fsanitize=address,undefined','-fno-sanitize-recover=all',
         '-DRV_HOST','-DENG_HOST','-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER',
         '-DACCEPTANCE_GENERATION=113','-DACCEPTANCE_03_MODE=1',
         '-DACCEPTANCE_ENTRIES_HEADER="' + str(c.ACCEPT / 'local/product-r11/entries.h') + '"',
         '-I',c.PRODUCT,'-I',c.ACCEPT,'-I',c.RES/'resident','-I',OUT]


def sources():
    src = c.PRODUCT / 'src'; core=src/'firmware/engine/core'; panel=src/'firmware/engine/panel'; co=src/'firmware/card_container_v2'
    rows=[(c.PRODUCT/n,False) for n in ('adapter.c','memory.c','blackbox.c')]
    rows += [(core/n,False) for n in ('eng_core.c','eng_data.c','eng_crc_compat.c','eng_semantic.c','eng_pin_stub.c','eng_mem.c')]
    rows += [(panel/n,False) for n in ('panel.c','panel_ui.c','panel_native.c','panel_port.c','panel_store.c','panel_gxts.c','panel_gxts_bind.c')]
    rows += [(co/n,False) for n in ('gate.c','common.c','api.c','gxts.c','gxts_io.c')]
    rows += [(src/'research/recipe_tweak/r2/tweak_int.c',False)]
    rows += [(c.ACCEPT/'engine_services'/n,True) for n in ('services.c','api.c','runtime.c','crc.c','mark.c','native_seed.c')]
    rows += [(c.RES/'resident/shared.c',True)]
    rows += [(c.RES/'resident'/n,False) for n in ('resident.c','loader.c','shared.c','hooks.c','runtime.c','validate_envelope.inc.c')]
    rows += [(c.RES/'local/resident/trust.c',False)]
    return rows


def compile_all():
    OUT.mkdir(exist_ok=True)
    fixture=(c.PRODUCT/'host_checks.c').read_text().split('static void flow(void)')[0]
    (OUT/'fixture.inc.c').write_text(fixture)
    driver=(c.ACCEPT/'host_v34c.c').read_text().replace('"local/v34c-host/fixture.inc.c"','"fixture.inc.c"')
    driver=driver.replace('"entry_projection.inc.c"','"'+str(c.ACCEPT/'entry_projection.inc.c')+'"')
    (OUT/'driver.c').write_text(driver)
    objects=[];proof=[]
    for index,(src,service) in enumerate(sources()):
        obj=OUT/(str(index)+'-'+src.stem+'.o');objects.append(obj)
        extra=['-DRV_ENGINE_SERVICES'] if service else []
        if src.name=='services.c': extra+=['-Drv_service=fixture_service']
        if src.name=='runtime.c':extra+=['-Dmemcpy='+('es_memcpy' if service else 'rv_memcpy'),'-Dmemset='+('es_memset' if service else 'rv_memset')]
        if src.name=='gxts.c':extra+=['-include',c.PRODUCT/'src/firmware/engine/core/eng_crc_bindings.h']
        c.run(['/usr/bin/clang',*FLAGS,*extra,'-c',src,'-o',obj],'host-compile-'+str(index))
        proof.append(dict(source=str(src.relative_to(c.ROOT)),sha256=c.sha(src),service=service,object_sha256=c.sha(obj)))
    for name,src in [('candidate',OUT/'driver.c'),('attacks',c.HERE/'attacks.c')]:
        obj=OUT/(name+'.o')
        c.run(['/usr/bin/clang',*FLAGS,'-c',src,'-o',obj],'host-compile-'+name)
        c.run(['/usr/bin/clang',*FLAGS,*objects,obj,'-o',OUT/name],'host-link-'+name)
    c.save('host-sources.json',proof)
    (OUT/'objects.json').write_text(json.dumps(list(map(str,objects))))
    print('PASS host C compilation with ASan/UBSan; product sources unchanged')


def execute(binary,case,unit,extra='0',old=None):
    old=old or c.ROOT/'firmware/resident_v33/acceptance/local/full-r9/GXRCE.DAT'
    name='-'.join(map(str,(binary,case,unit,Path(str(extra)).name)))
    p=c.run([OUT/binary,case,unit,c.PACKAGE/'SD_ROOT/GXRCE.DAT',c.FINAL/'trust.bin',c.FINAL/'effective-rows.bin',old,extra],name,timeout=180)
    assert re.search(r'^OK ',p.stdout,re.M),name
    return dict(binary=binary,case=case,unit=unit,extra=extra,rc=p.returncode,
                log='logs/'+name+'.stdout',assertions=re.findall(r'assertions=(\d+)',p.stdout))


def suite():
    rows=[]
    for unit in range(3):
        for case in ('basic','service-quarantine','log-fault','conflict','same-conflict','accepted-f02','neighbour','rpc-faults'):
            rows.append(execute('candidate',case,unit))
        for mode in range(10): rows.append(execute('candidate','ctl',unit,str(mode)))
        for mode in range(3): rows.append(execute('candidate','t',unit,str(mode)))
        for mode in range(7): rows.append(execute('candidate','rejected',unit,str(mode),c.ROOT/'firmware/resident_v34b/acceptance/local/full-r10/GXRCE.DAT'))
        for mode in range(6):
            rows.append(execute('candidate','daily',unit,str(mode)))
        for mode in (0,1):rows.append(execute('candidate','store-fault',unit,str(mode)))
        for mode in (0,1,2):rows.append(execute('candidate','publish-failure',unit,str(mode)))
        for case in ('cold','ctl-fuzz','panel-cancel','late-card','quarantine-reset'):
            rows.append(execute('attacks',case,unit))
        if unit!=1:
            rows.append(execute('candidate','r33',unit))
            for n in (0,1,127,128,254,255):rows.append(execute('candidate','iso',unit,str(n)))
    c.save('host-suite.json',dict(status='PASS_ASSERTIONS',runs=len(rows),cases=rows,
           limits='Real product/resident C; native file, memory, UI and RPC boundaries are doubles. Complete M32R engine is not executed.'))
    print('PASS',len(rows),'host programs; includes documented limitation probes')


def compile_attacks():
    objects=json.loads((OUT/'objects.json').read_text())
    c.run(['/usr/bin/clang',*FLAGS,'-c',c.HERE/'attacks.c','-o',OUT/'attacks.o'],'host-compile-attacks')
    c.run(['/usr/bin/clang',*FLAGS,*objects,OUT/'attacks.o','-o',OUT/'attacks'],'host-link-attacks')


if __name__=='__main__':
    {'compile':compile_all,'attacks-compile':compile_attacks,'suite':suite}[sys.argv[1]]()
