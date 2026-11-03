"""Recompile frozen product C without invoking any candidate writer."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAND = ROOT/'firmware/engine_v36_r28/candidate'
PRODUCT = CAND/'containers/product'
RES = ROOT/'firmware/resident_v34c/resident'
OUT = HERE/'host'

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def run(args, label):
    env = dict(os.environ, TMPDIR=str(HERE/'tmp'), CLANG_MODULE_CACHE_PATH=str(HERE/'tmp/modules'),
               ASAN_OPTIONS='detect_leaks=0:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
               PYTHONDONTWRITEBYTECODE='1', LC_ALL='C')
    result = subprocess.run([str(a) for a in args], cwd=ROOT, env=env, capture_output=True, timeout=600)
    (OUT/(label+'.stdout')).write_bytes(result.stdout)
    (OUT/(label+'.stderr')).write_bytes(result.stderr)
    with (OUT/'commands.jsonl').open('a') as f:
        f.write(json.dumps(dict(argv=[str(a) for a in args], label=label, returncode=result.returncode))+'\n')
    if result.returncode:
        raise RuntimeError(label+' '+result.stderr.decode(errors='replace')[-1800:])
    return result.stdout.decode()

def compile_all():
    OUT.mkdir(exist_ok=True);(HERE/'tmp').mkdir(exist_ok=True)
    fixture = (PRODUCT/'host_checks.c').read_text().split('static void flow(void)')[0]
    fixture = fixture.replace('"../../local/native_seed_model.h"', '"'+str(CAND/'local/native_seed_model.h')+'"')
    (OUT/'fixture.inc.c').write_text(fixture)
    source = (CAND/'host_v34c.c').read_text()
    source = source.replace('"local/v34c-host/fixture.inc.c"', '"'+str(OUT/'fixture.inc.c')+'"')
    source = source.replace('"../baseline/engine_services/native_seed.c"',
                            '"'+str(CAND.parent/'baseline/engine_services/native_seed.c')+'"')
    source = source.replace('int main(int argc,char **argv)',
                            (HERE/'extra_cases.inc.c').read_text()+'\nint main(int argc,char **argv)')
    source = source.replace('if(!strcmp(argv[1],"seed115"))seed115(argv[7]);',
        'if(!strcmp(argv[1],"review"))review_cases(old,old_bytes);\n    else if(!strcmp(argv[1],"seed115"))seed115(argv[7]);')
    (OUT/'host_v34c.c').write_text(source)
    history = (CAND/'host_history34c.c').read_text().replace('"host_v34c.c"','"'+str(OUT/'host_v34c.c')+'"')
    (OUT/'history.c').write_text(history)
    sys.path.insert(0,str(PRODUCT))
    b = load(PRODUCT/'build.py','review_build_sources')
    flags = ['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function',
             '-fno-omit-frame-pointer','-fsanitize=address,undefined','-fno-sanitize-recover=all',
             '-DRV_HOST','-DENG_HOST','-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER',
             '-DACCEPTANCE_ENTRIES_HEADER="'+str(CAND/'local/product-r13/entries.h')+'"',
             '-I',PRODUCT,'-I',CAND,'-I',RES]
    sources = [(s,service) for s,service in b.sources() if s.suffix=='.c']
    sources += [(RES/n,False) for n in ('resident.c','loader.c','shared.c','hooks.c','runtime.c','validate_envelope.inc.c')]
    sources += [(ROOT/'firmware/resident_v34c/local/resident/trust.c',False)]
    objects = []
    for i,(src,service) in enumerate(sources):
        obj=OUT/f'{i:02}-{src.stem}.o';objects.append(obj)
        extra=['-DRV_ENGINE_SERVICES'] if service else []
        if src.name=='services.c':extra+=['-Drv_service=fixture_service']
        if src.name=='runtime.c':extra+=['-Dmemcpy='+('es_memcpy' if service else 'rv_memcpy'),'-Dmemset='+('es_memset' if service else 'rv_memset')]
        if src.name=='gxts.c':extra+=['-include',b.SRC/'firmware/engine/core/eng_crc_bindings.h']
        run(['/usr/bin/clang',*flags,*extra,'-c',src,'-o',obj],f'compile-{i:02}')
    for name,source in [('host',OUT/'host_v34c.c'),('history',OUT/'history.c')]:
        obj=OUT/(name+'.o')
        run(['/usr/bin/clang',*flags,'-c',source,'-o',obj],'compile-'+name)
        run(['/usr/bin/clang',*flags,*objects,obj,'-o',OUT/name],'link-'+name)
    print('PASS independent ASan/UBSan compilation',len(sources)+2,'translation units',flush=True)

def cases():
    data=json.loads((CAND.parent/'local/verification115.json').read_text())
    final=CAND/'local/full-r13'
    result=[]
    for index,row in enumerate(data['runs']):
        case,unit=row['case'],row['unit']
        if row['generation']==113:old=CAND.parent/'baseline/local/full-r11/GXRCE.DAT'
        elif row['generation']==114:old=CAND.parent/'local/reproduced114/GXRCE.DAT'
        else:
            v=load(CAND/'verify_v34c.py','frozen_case_paths')
            old=(v.OLD.get(row['generation'],ROOT/'firmware/resident_v34b/acceptance/local/full-r10'))/'GXRCE.DAT'
        extra=row.get('extra','0')
        if case in ('seed115','blackbox','sticky115'):extra=str(OUT/f'{case}-{unit}.BIN')
        binary=OUT/('history' if case=='history' else 'host')
        label=f'case-{index:03}-{case}-{unit}'
        text=run([binary,case,unit,final/'GXRCE.DAT',final/'trust.bin',final/'effective-rows.bin',old,extra,*row.get('tail',[])],label)
        assert text.splitlines()[-1].startswith('OK '),(label,text[-1000:])
        result.append(dict(case=case,unit=unit,status='PASS',label=label))
        if len(result)%40==0:print('PASS rerun',len(result),'/',len(data['runs']),flush=True)
    independent()
    (OUT/'results.json').write_text(json.dumps(dict(reruns=result, independent_units=3, status='PASS_HOST_MODEL'),indent=2)+'\n')
    print('PASS rerun',len(result),'author cases plus independent cases on three units',flush=True)

def independent():
    final=CAND/'local/full-r13'
    for unit in range(3):
        text=run([OUT/'host','review',unit,final/'GXRCE.DAT',final/'trust.bin',final/'effective-rows.bin',
                  CAND.parent/'baseline/local/full-r11/GXRCE.DAT','0'],'independent-'+str(unit))
        assert text.splitlines()[-1].startswith('OK ')
    print('PASS independent mutation/lifetime/stale113_OK cases on three units',flush=True)

if __name__=='__main__':
    assert len(sys.argv)==2 and sys.argv[1] in ('compile','cases','independent')
    {'compile':compile_all,'cases':cases,'independent':independent}[sys.argv[1]]()
