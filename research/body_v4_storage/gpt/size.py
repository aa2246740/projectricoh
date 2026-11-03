#!/usr/bin/env python3
"""Compile one research-only relocatable object; never link a firmware image."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import evidence as e

def main():
    e.preflight()
    gcc=e.ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    assert gcc.is_file()
    out=e.OUT/'sizing'
    out.mkdir(exist_ok=True)
    env=dict(os.environ,TMPDIR=str(out),LC_ALL='C',PYTHONDONTWRITEBYTECODE='1')
    obj=out/'bridge_sizing.o'
    args=[str(gcc),'-std=c11','-Os','-fomit-frame-pointer','-ffreestanding','-fno-builtin',
      '-fno-stack-protector','-fno-common','-fno-pic','-m32r','-mmodel=large','-msdata=none','-G0',
      '-Wall','-Wextra','-Werror','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
      '-fstack-usage','-ffunction-sections','-fdata-sections','-c',str(HERE/'bridge_sizing.c'),'-o',str(obj)]
    result=subprocess.run(args,env=env,text=True,capture_output=True)
    (out/'compile.stdout').write_text(result.stdout)
    (out/'compile.stderr').write_text(result.stderr)
    assert result.returncode==0,result.stderr
    headers=subprocess.check_output([str(e.OBJDUMP),'-h',str(obj)],text=True)
    symbols=subprocess.check_output([str(e.OBJDUMP),'-t',str(obj)],text=True)
    disasm=subprocess.check_output([str(e.OBJDUMP),'-dr',str(obj)],text=True)
    (out/'sections.txt').write_text(headers)
    (out/'symbols.txt').write_text(symbols)
    (out/'disasm.txt').write_text(disasm)
    sections=[]
    for m in re.finditer(r'^\s*\d+\s+(\S+)\s+([0-9a-f]+)\s',headers,re.M):
        sections.append(dict(name=m[1],bytes=int(m[2],16)))
    trampoline=out/'bridge_trampoline.o'
    asm_args=[str(gcc),'-m32r','-c',str(HERE/'bridge_trampoline.S'),'-o',str(trampoline)]
    asm_result=subprocess.run(asm_args,env=env,text=True,capture_output=True)
    (out/'trampoline.stdout').write_text(asm_result.stdout)
    (out/'trampoline.stderr').write_text(asm_result.stderr)
    assert asm_result.returncode==0,asm_result.stderr
    asm_headers=subprocess.check_output([str(e.OBJDUMP),'-h',str(trampoline)],text=True)
    (out/'trampoline-sections.txt').write_text(asm_headers)
    (out/'trampoline-disasm.txt').write_text(subprocess.check_output([str(e.OBJDUMP),'-dr',str(trampoline)],text=True))
    asm_text=sum(int(m[2],16) for m in re.finditer(r'^\s*\d+\s+(\.text\S*)\s+([0-9a-f]+)\s',asm_headers,re.M))
    result=dict(status='MEASURED_RESEARCH_OBJECT_ONLY',compiler=str(gcc.relative_to(e.ROOT)),
      compiler_sha256=e.sha(gcc),compiler_version=subprocess.check_output([str(gcc),'--version'],text=True).splitlines()[0],
      source_sha256=e.sha(HERE/'bridge_sizing.c'),object_sha256=e.sha(obj),
      command=args,trampoline_command=asm_args,trampoline_sha256=e.sha(trampoline),
      trampoline_source_sha256=e.sha(HERE/'bridge_trampoline.S'),trampoline_text_bytes=asm_text,
      trampoline_saved_stack_bytes=40,sections=sections,
      unresolved_symbols=re.findall(r'\*UND\*\s+[0-9a-f]+\s+(\S+)',symbols),
      text_bytes=sum(s['bytes'] for s in sections if s['name'].startswith('.text')),
      data_bytes=sum(s['bytes'] for s in sections if s['name'].startswith(('.data','.rodata'))),
      bss_bytes=sum(s['bytes'] for s in sections if s['name'].startswith('.bss')),
      excluded=['Native ports, memcpy helper and firmware detours','All upstream capture/USB/module/card admission hooks',
         'Exposure identity ledger','Readback and CRC validation','Pin lifecycle and platform atomics',
         'Whole-program WCET, real stack high-water, relocation/link padding'])
    e.save('sizing.json',result)
    print(json.dumps({k:v for k,v in result.items() if k in ('status','compiler_version','text_bytes','data_bytes','bss_bytes','excluded')},indent=2))

if __name__=='__main__':main()
