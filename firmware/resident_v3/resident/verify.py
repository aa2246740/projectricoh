#!/usr/bin/env python3
"""Exercise changed resident boundaries and unified services with sanitizer doubles."""
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
TASK=HERE.parent
spec=importlib.util.spec_from_file_location('final_resident_build',HERE/'build.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

def main():
    b.preflight()
    cross=(b.LOCAL/'commands.json').read_text()
    (b.LOCAL/'cross-commands.json').write_text(cross)
    assert b.build_identity().hex()==json.loads((b.LOCAL/'trust.json').read_text())['resident_build_id']
    b.run([sys.executable,'-I','-B',HERE/'make_fixture.py'],'fixtures')
    out=b.LOCAL/'host';out.mkdir(exist_ok=True)
    flags=['clang','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-DRV_HOST',
           '-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',HERE]
    sources=[(HERE/n,False) for n in ('resident.c','loader.c','shared.c','hooks.c','runtime.c','validate_envelope.inc.c')]
    sources += [(TASK/'engine_services'/n,True) for n in ('services.c','api.c','runtime.c','crc.c','mark.c','native_seed.c')]
    sources += [(HERE/'shared.c',True),(HERE/'v3_checks.c',False),(b.LOCAL/'trust.c',False)]
    objects=[]
    for i,(src,service) in enumerate(sources):
        obj=out/(str(i)+'-'+src.stem+'.o');objects.append(obj)
        extra=['-DRV_ENGINE_SERVICES'] if service else []
        if src.name=='runtime.c':
            extra+=['-Dmemcpy='+('es_test_memcpy' if service else 'rv_test_memcpy'),
                    '-Dmemset='+('es_test_memset' if service else 'rv_test_memset')]
        b.run([*flags,*extra,'-c',src,'-o',obj],'host-compile-'+str(i))
    binary=out/'checks'
    b.run(['clang','-fsanitize=address,undefined',*objects,'-o',binary],'host-link')
    # run() records raw errors as well as successful output; LeakSanitizer is unavailable on macOS.
    import os
    os.environ['ASAN_OPTIONS']='detect_leaks=0:halt_on_error=1'
    os.environ['UBSAN_OPTIONS']='halt_on_error=1:print_stacktrace=1'
    p=b.run([binary,b.LOCAL/'fixtures/synthetic-container.fixture'],'host-checks')
    cases=re.findall(r'^CASE (.+)$',p.stdout,re.M)
    assert len(cases)==21
    (b.LOCAL/'host-results.json').write_text(json.dumps(dict(status='PASS',cases=cases,
        checks=int(re.search(r'PASS_HOST checks=(\d+)',p.stdout).group(1)),sanitizer='ASan+UBSan',
        native_m32r_execution=False,mock_engine=True,mock_transport=True),indent=2)+'\n')
    (b.LOCAL/'host-commands.json').write_text((b.LOCAL/'commands.json').read_text())
    (b.LOCAL/'commands.json').write_text(cross)
    print(p.stdout.splitlines()[-1])

if __name__=='__main__':main()
