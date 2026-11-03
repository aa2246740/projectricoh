"""Build and run the C host model with ASan/UBSan; retain raw results."""
from pathlib import Path
import importlib.util
import json
import os

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('rv4_test_builder',HERE/'build.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)


def main():
    b.preflight();out=b.LOCAL/'host';out.mkdir(exist_ok=True)
    flags=['/usr/bin/clang','-std=c11','-O1','-g','-fno-builtin','-Wall','-Wextra','-Werror',
           '-DRV4_HOST','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',HERE]
    sources=[HERE/n for n in b.SOURCES if n not in ('native.c','bridges.S')]
    sources += [b.LOCAL/'trust.c',HERE/'host_test.c']
    objects=[]
    for i,source in enumerate(sources):
        obj=out/(str(i)+'-'+source.stem+'.o');objects.append(obj)
        extra=['-Dmemcpy=rv4_test_memcpy'] if source.name=='runtime.c' else []
        b.run([*flags,*extra,'-c',source,'-o',obj],'host-compile-'+str(i))
    binary=out/'checks'
    b.run(['/usr/bin/clang','-fsanitize=address,undefined',*objects,'-o',binary],'host-link')
    os.environ['ASAN_OPTIONS']='detect_leaks=0:halt_on_error=1'
    os.environ['UBSAN_OPTIONS']='halt_on_error=1:print_stacktrace=1'
    p=b.run([binary],'host-checks',True)
    cases=[json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')]
    result=dict(status='PASS' if p.returncode==0 else 'FAIL',returncode=p.returncode,cases=cases,
                driver_sha256=b.sha(HERE/'test_host.py'),
                sanitizers=['AddressSanitizer','UndefinedBehaviorSanitizer'],
                native_profile='host_fixture_proven_context_and_writer_protocol',
                native_profile_is_target_profile=False,binary_sha256=b.sha(binary),
                sources={str(p.relative_to(b.ROOT)):b.sha(p) for p in sources},
                target_identity=json.loads((HERE/'generated/identity.json').read_text()),
                log=str((b.LOCAL/'host-checks.log').relative_to(b.ROOT)))
    b.write(b.REPORT/'host-tests.json',result)
    print(p.stdout+p.stderr,end='')
    if p.returncode:raise SystemExit(p.returncode)


if __name__=='__main__':main()
