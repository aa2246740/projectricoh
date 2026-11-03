#!/usr/bin/env python3
"""Conservative linear T taint candidates, never a control-flow proof."""
import csv
from pathlib import Path
import re
import runpy

HERE = Path(__file__).resolve().parent
A = runpy.run_path(str(HERE / 'analyze.py'))
regs = {}
accesses = []
calls = []
pointers = []
def show(v):
    return '' if v is None else (f'T+{v[1]:#x}' if v[0] == 'T' else hex(v[1]))
for va, ins, path, number, raw, code in A['lines']('jlaunch3'):
    for op in re.split(r'\s*(?:\|\||->)\s*', ins):
        m = re.fullmatch(r'seth (\w+),#0x([0-9a-f]+)', op)
        if m:
            regs[m[1]] = ('K', int(m[2], 16) << 16)
            continue
        m = re.fullmatch(r'(ldi|ld24) (\w+),(?:#)?(-?\d+|0x[0-9a-f]+)', op)
        if m:
            regs[m[2]] = ('K', int(m[3], 0))
            continue
        m = re.fullmatch(r'(or3|add3) (\w+),(\w+),#(0x[0-9a-f]+|-?\d+)', op)
        if m:
            a, b = regs.get(m[3]), int(m[4], 0)
            regs[m[2]] = None if a is None else (a[0], (a[1] | b) if m[1] == 'or3' else a[1] + b)
            if regs[m[2]] is not None and regs[m[2]][0] == 'T':
                pointers.append([hex(va), hex(regs[m[2]][1]), op, path, number])
            continue
        m = re.fullmatch(r'addi (\w+),#(-?\d+)', op)
        if m:
            a = regs.get(m[1])
            regs[m[1]] = None if a is None else (a[0], a[1] + int(m[2]))
            continue
        m = re.fullmatch(r'mv (\w+),(\w+)', op)
        if m:
            regs[m[1]] = regs.get(m[2])
            continue
        m = re.fullmatch(r'(ld\w*|st\w*) (\w+),@(?:\((-?\d+),(\w+)\)|(\w+))', op)
        if m:
            a, delta = regs.get(m[4] or m[5]), int(m[3] or 0)
            effective = None if a is None else (a[0], a[1] + delta)
            if effective and effective[0] == 'T':
                accesses.append([hex(va), hex(effective[1]), m[1], show(regs.get(m[2])), op, path, number])
            if m[1].startswith('ld'):
                regs[m[2]] = ('T', 0) if effective == ('K', 0x200b2cf0) else None
            continue
        m = re.fullmatch(r'(jl|jmp) (\w+)', op)
        if m:
            a = regs.get(m[2])
            if m[1] == 'jl' and any(regs.get('r' + str(i), ('', 0)) is not None and regs.get('r' + str(i), ('', 0))[0] == 'T' for i in range(4, 8)):
                calls.append([hex(va), show(a), *[show(regs.get('r' + str(i))) for i in range(4, 8)], path, number])
            if m[1] == 'jl':
                for i in range(8): regs['r' + str(i)] = None
            else: regs = {}
            continue
        if op.startswith(('bra ', 'bl ')):
            regs = {}
            continue
        m = re.match(r'(\w+) (r\d+|fp|lr|sp)(?:,|$)', op)
        if m and m[1] not in ['cmp', 'cmpu', 'cmpi', 'cmpui', 'beqz', 'bnez', 'beq', 'bne', 'push', 'st', 'stb', 'sth']:
            regs[m[2]] = None
for name, header, rows in [('t-access-candidates.tsv', ['vma', 'offset', 'kind', 'value', 'instruction', 'source_file', 'source_line'], accesses),
                           ('t-call-candidates.tsv', ['vma', 'target', 'r4', 'r5', 'r6', 'r7', 'source_file', 'source_line'], calls),
                           ('t-pointer-candidates.tsv', ['vma', 'offset', 'instruction', 'source_file', 'source_line'], pointers)]:
    with (HERE / name).open('w') as f:
        writer = csv.writer(f, delimiter='\t'); writer.writerow(header); writer.writerows(rows)
print('accesses', len(accesses), 'calls', len(calls))
for row in accesses:
    if row[2].startswith('st'): print('WRITE', *row[:5])
for row in calls:
    if row[2] == 'T+0x0' or row[3] == 'T+0x0': print('BASE-PASSED', *row[:6])
