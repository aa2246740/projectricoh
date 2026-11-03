#!/usr/bin/env python3
"""Compile two analysis-only .s files; never assemble, link, or package firmware."""
from pathlib import Path
import ast
import hashlib
import json
import os
import re
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'evidence/kernel/assembly'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'tmp').mkdir(exist_ok=True)
    source=(ROOT/'firmware/lut_p0_timing/kernel.c').read_text()
    header=(ROOT/'firmware/lut_p0_timing/kernel.h').read_text()
    tree=ast.parse((ROOT/'firmware/lut_p0_timing/build.py').read_text())
    flags=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FLAGS' for t in n.targets))
    flags=[x for x in flags if x!='-fstack-usage']
    gcc=ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    env=dict(os.environ,TMPDIR=str(OUT/'tmp'),LC_ALL='C',PYTHONDONTWRITEBYTECODE='1')
    results=[]
    codes=[]
    for n in (17,33):
        d=OUT/str(n);d.mkdir(exist_ok=True)
        code=source if n==17 else source.replace('{3,51,867}','{3,99,3267}').replace('*289u','*1089u').replace('*17u','*33u')
        h=header if n==17 else header.replace('P0_N=17, P0_NODES=17*17*17','P0_N=33, P0_NODES=33*33*33')
        (d/'kernel.c').write_text(code);(d/'kernel.h').write_text(h)
        cmd=[str(gcc),*flags,'-S',str(d/'kernel.c'),'-o',str(d/'kernel.s')]
        p=subprocess.run(cmd,capture_output=True,text=True,env=env)
        (d/'stdout.txt').write_text(p.stdout);(d/'stderr.txt').write_text(p.stderr)
        assert p.returncode==0,p.stderr
        asm=(d/'kernel.s').read_text()
        instructions=[l.strip() for l in asm.splitlines() if l.startswith('\t') and not l.startswith('\t.') and l.strip() and not l.strip().startswith(';')]
        # Keep registers, instruction names, labels and ordering. Normalize only numeric operands.
        normalized=[re.sub(r'(?<![\w.])(?:0x[0-9a-fA-F]+|[0-9]+)(?![\w.])','N',l) for l in instructions]
        codes.append(normalized)
        results.append(dict(n=n,argv=cmd,returncode=p.returncode,instruction_lines=len(instructions),
            source_sha256=hashlib.sha256(code.encode()).hexdigest(),assembly_sha256=hashlib.sha256(asm.encode()).hexdigest()))
    result=dict(scope='GCC -S only. Analysis source copies; no object, ELF, container or firmware package built.',
                compiler_version=subprocess.check_output([str(gcc),'--version'],text=True).splitlines()[0],
                normalized_instruction_sequences_equal=codes[0]==codes[1],results=results)
    (OUT/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
