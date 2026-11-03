#!/usr/bin/env python3
"""Compile only this pure calculation core, never a firmware or card payload."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import json
import re
import subprocess
import runtime as r


def main():
    r.setup()
    out=r.LOCAL/'m32r';out.mkdir(exist_ok=True)
    gcc=r.ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    objdump=r.ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    runs=[]
    def run(args,name):
        p=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=55)
        result=dict(argv=[str(x) for x in args],exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)
        r.dump(out/(name+'.json'),result);runs.append(name)
        if p.returncode: raise RuntimeError(name+' failed, see local/m32r/'+name+'.json')
        return p.stdout
    assert run([gcc,'-dumpmachine'],'target').strip()=='m32r-elf'
    obj=out/'tweak_int.o';linked=out/'tweak_with_div.o'
    flags=['-std=c11','-Os','-ffreestanding','-fno-builtin','-fno-common','-fno-pic',
           '-fno-stack-protector','-m32r','-mmodel=large','-msdata=none','-G0',
           '-Wall','-Wextra','-Werror','-fstack-usage']
    run([gcc,*flags,'-c',r.HERE/'tweak_int.c','-o',obj],'compile')
    text=run([objdump,'-h','-t',obj],'core_headers')
    unresolved=[s.strip() for s in text.splitlines() if '*UND*' in s]
    run([gcc,'-nostdlib','-r',obj,'-o',linked],'link_division')
    final=run([objdump,'-h','-t',linked],'linked_headers')
    assert not [s for s in final.splitlines() if '*UND*' in s]
    sections=lambda txt:{m[1]:int(m[2],16) for m in re.finditer(r'^\s*\d+\s+(\.\S+)\s+([0-9a-f]+)\s+',txt,re.M)}
    header=linked.read_bytes()[:20]
    assert header[:6]==b'\x7fELF\x01\x02' and header[18:20]==bytes((0,88))
    stack=(out/'tweak_int.su').read_text()
    report=dict(scope='M32R relocatable computation object only; never a loadable camera payload',
        compiler_sha256=r.sha(gcc),core_source_sha256=r.sha(r.HERE/'tweak_int.c'),
        core_sections=sections(text),linked_sections=sections(final),core_undefined=unresolved,
        linked_undefined=[],division='native M32R divu, no libgcc dependency',stack_usage=stack,
        firmware_ready=False,camera_acceptance=False)
    r.dump(out/'result.json',report)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__': main()
