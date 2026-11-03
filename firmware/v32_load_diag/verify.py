"""Run the real resident C loader plus real DIAG C under ASan/UBSan doubles."""
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('diag_common',Path(__file__).with_name('common.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def main():
    c.guard();out=c.LOCAL/'host';out.mkdir(exist_ok=True)
    flags=['/usr/bin/clang','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-DRV_HOST',
           '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',
           '-fno-builtin','-I',c.R,'-I',c.HERE]
    sources=[c.R/n for n in ('resident.c','loader.c','shared.c','hooks.c','runtime.c','validate_envelope.inc.c')]
    sources += [c.HERE/'diag.c',c.HERE/'host_checks.c',c.LOCAL/'trust.c']
    objects=[]
    for i,source in enumerate(sources):
        obj=out/(str(i)+'-'+source.stem+'.o');objects.append(obj)
        extra=['-Dmemcpy=rv_test_memcpy','-Dmemset=rv_test_memset'] if source.name=='runtime.c' else []
        c.run([*flags,*extra,'-c',source,'-o',obj],'host-compile-'+str(i))
    binary=out/'checks'
    c.run(['/usr/bin/clang','-fsanitize=address,undefined',*objects,'-o',binary],'host-link')
    cases=('good','unit-q','unit-m','missing-full','missing-diag','read-error','read-oversize',
           'close-error','short-0','short-255','short-256','truncated','trailing','header-crc',
           'body-id','build-id','abi-id','payload-crc','reloc-layout','reloc-cell','pin-mismatch',
           'unit-unknown','cmp-version','heap-low','heap-fragmented','free-error','allocation-header',
           'ui-array','ui-count0','ui-count3','ui-tag','ui-count2')
    result=[]
    decoder=c.load(c.HERE/'decode.py','diag_decoder')
    for case in cases:
        p=c.run([binary,c.LOCAL/'GXRCE.DAT',c.FULL,case],'host-'+case)
        assert f'CASE {case} PASS' in p.stdout
        result.append(dict(case=case,status='PASS',summary=p.stdout.splitlines()[-1]))
        if case=='good':
            rows='\n'.join(line for line in p.stdout.splitlines() if line.startswith('D'))+'\n'
            (c.LOCAL/'screen-example.txt').write_text(rows)
            decoded=decoder.decode(rows);c.save(c.LOCAL/'screen-example.json',decoded)
            for name,bad in [('crc',rows.replace('D04 ','D04 0',1)),('missing','\n'.join(rows.splitlines()[:-1])),
                             ('conflict',rows+'D00 00000000\n')]:
                try:decoder.decode(bad)
                except ValueError:result.append(dict(case='decoder-'+name,status='PASS'))
                else:raise AssertionError('decoder accepted '+name)
    c.save(c.LOCAL/'host-results.json',dict(status='PASS',cases=result,count=len(result),
        actual_resident_C_loader=True,actual_DIAG_C=True,packed_DIAG_envelope=True,
        sanitizers='ASan+UBSan',native_transport='double',
        m32r_execution=False,camera_acceptance=False,
        read_only='No RPC or file writes; S byte snapshot unchanged; undefined writer calls abort'))
    print(f'PASS: {len(cases)} loader/DIAG cases + 3 decoder negatives; ASan+UBSan; RPC/file/S writes=0')


if __name__=='__main__':main()
