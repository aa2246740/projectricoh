#!/usr/bin/env python3
"""Annotate literal address constructions with official ASCII strings."""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('audit', HERE/'audit.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
name = sys.argv[1]
im = a.Image(name)
out = []
for rel in __import__('json').loads((HERE/f'{name}-full-disasm.json').read_text()):
    registers = {}
    for line in (HERE/(rel+'.asm')).read_text().splitlines():
        if not re.match('^[0-9a-f]{8}:', line):
            continue
        for insn in re.split(r'\s*(?:->|\|\|)\s*', line.split('\t')[-1]):
            m = re.fullmatch(r'seth (\w+),#(0x[0-9a-f]+)', insn)
            if m:
                registers[m[1]] = int(m[2],16)<<16
            m = re.fullmatch(r'or3 (\w+),(\w+),#(0x[0-9a-f]+)', insn)
            if not m or m[2] not in registers:
                continue
            value = registers[m[2]] | int(m[3],16)
            registers[m[1]] = value
            try:
                raw = im.read(value,1)
                off = im.offset(value)
            except AssertionError:
                continue
            raw = im.data[off:off+220].split(b'\0')[0]
            if len(raw)<5 or not all(32<=b<127 or b in (9,10,13) for b in raw):
                continue
            out.append(f"{line[:8]} -> {value:08x} file={off:08x} {raw.decode('ascii')!r}")
a.write(f'evidence/{name}-literal-strings.txt', '\n'.join(out)+'\n')
print(name,len(out),'literal string candidates; CFG and code/data require manual review')
