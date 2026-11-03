#!/usr/bin/env python3
"""Measure freestanding M32R ELF files; never emit loadable firmware/card files."""
import hashlib
import ast
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess

HERE = Path(__file__).resolve().parent
_s = importlib.util.spec_from_file_location('card2_pack', HERE/'pack.py')
pack = importlib.util.module_from_spec(_s); _s.loader.exec_module(pack)
GCC = pack.ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD = pack.ROOT/'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
OBJDUMP = pack.ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
FLAGS = ['-std=c11','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector',
         '-fno-common','-fno-pic','-m32r','-mmodel=large','-msdata=none','-G0',
         '-Wall','-Wextra','-Werror','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fstack-usage']
OUT = HERE/'local/m32r'


def elf_sections(path):
    data = path.read_bytes()
    if data[:6] != b'\x7fELF\x01\x02':
        raise ValueError('not ELF32 big endian')
    off = struct.unpack_from('>I', data,32)[0]
    stride,count,strings = struct.unpack_from('>HHH', data,46)
    rows = [struct.unpack_from('>10I',data,off+i*stride) for i in range(count)]
    st = rows[strings]; names=data[st[4]:st[4]+st[5]]
    return [dict(name=names[r[0]:].split(b'\0',1)[0].decode(),type=r[1],flags=r[2],
                 address=r[3],offset=r[4],size=r[5]) for r in rows]


def main():
    pack.preflight(); OUT.mkdir(parents=True,exist_ok=True)
    resident_build=pack.ROOT/'firmware/resident_v2/build.py'
    resident_flags=next(ast.literal_eval(n.value) for n in ast.parse(resident_build.read_text()).body
                        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FLAGS' for t in n.targets))
    if FLAGS!=resident_flags:
        raise ValueError('M32R options differ from resident_v2/build.py')
    tmp=OUT/'tmp'; tmp.mkdir(exist_ok=True)
    env=dict(os.environ,TMPDIR=str(tmp),LC_ALL='C',PYTHONDONTWRITEBYTECODE='1')
    commands=[]
    def run(name,args):
        p=subprocess.run([str(x) for x in args],cwd=HERE,env=env,text=True,capture_output=True,timeout=30)
        pack.write_bytes(OUT/(name+'.log'),(p.stdout+p.stderr).encode())
        commands.append(dict(name=name,argv=[str(x) for x in args],returncode=p.returncode))
        pack.write_json(OUT/'commands.json',commands)
        if p.returncode:
            with (OUT/'failures.log').open('a') as log:
                log.write(name+'\n'+p.stdout+p.stderr+'\n')
            raise RuntimeError(f'{name}: {p.stderr[-2000:]}')
        return p.stdout
    run('gcc-version',[GCC,'--version'])
    for name in ('common','gate','semantic','sha256','api','gxts','gxts_io'):
        run('compile-'+name,[GCC,*FLAGS,'-mmodel=medium','-I',HERE,'-c',HERE/(name+'.c'),'-o',OUT/(name+'.o')])
    results={}
    variants={'gate':['common','gate'],'semantic':['common','semantic','sha256'],
              'full':['common','gate','semantic','sha256','api'],
              'full_with_gxts':['common','gate','semantic','sha256','api','gxts','gxts_io'],
              'engine_semantics_gxts':['common','semantic','sha256','gxts','gxts_io']}
    for name,sources in variants.items():
        elf=OUT/(name+'.elf')
        run('link-'+name,[LD,'--no-undefined','-T',HERE/'measure.ld','-Map='+str(OUT/(name+'.map')),
                          '-o',elf,*[OUT/(s+'.o') for s in sources]])
        secs=elf_sections(elf)
        if any(s['flags']&2 and s['size'] and s['name'] not in ('.text','.rodata','.data','.bss') for s in secs):
            raise ValueError('unmeasured allocated section')
        if any(s['type'] in (4,9) and s['size'] for s in secs):
            raise ValueError('unexpected remaining relocation')
        sizes={s['name']:s['size'] for s in secs if s['name'] in ('.text','.rodata','.data','.bss')}
        symbols=run('symbols-'+name,[OBJDUMP,'-t',elf])
        if '*UND*' in symbols:
            raise ValueError('undefined symbol in final measurement ELF')
        if name=='gate' and 'sha256' in symbols:
            raise ValueError('SHA-256 must not be linked into gate')
        results[name]=dict(sections=sizes,code_rodata_bytes=sizes.get('.text',0)+sizes.get('.rodata',0),
                           undefined_symbols=0,remaining_relocations=0,sha256=pack.sha(elf.read_bytes()))
    stacks={p.name:p.read_text().splitlines() for p in sorted(OUT.glob('*.su'))}
    result=dict(schema='gxrce2-m32r-size/1',measurement_only=True,flags=FLAGS,
                implementation_sha256={p.name:pack.sha(p.read_bytes()) for p in sorted(HERE.iterdir())
                    if p.suffix in ('.c','.h','.ld') or p.name=='build.py'},
                resident_build_source_sha256=pack.sha(resident_build.read_bytes()),
                c_model_override='-mmodel=medium, exactly as resident_v2/build.py',
                tools={str(p.relative_to(pack.ROOT)):pack.sha(p.read_bytes()) for p in (GCC,LD,OBJDUMP)},
                gate_has_sha256=False,
                results=results,stack_usage=stacks,
                semantic_increment_bytes=results['full']['code_rodata_bytes']-results['gate']['code_rodata_bytes'],
                gxts_increment_bytes=results['full_with_gxts']['code_rodata_bytes']-results['full']['code_rodata_bytes'])
    pack.write_json(OUT/'size.json',result)
    pack.checksums(OUT)
    for name,value in results.items():
        print(f'{name}: code+rodata={value["code_rodata_bytes"]} sections={value["sections"]} undefined=0')


if __name__=='__main__':
    main()
