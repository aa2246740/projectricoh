#!/usr/bin/env python3
"""Offline research only. All writes are confined to this directory."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIRM = ROOT / 'artifacts/firmware/gxr-1.51'
DIS = ROOT / 'research/tooling_m32r/disasm'

def image(name):
    data = (FIRM / name).read_bytes()
    return data, [(s + 512, v, n) for s, v, n, _, _ in
                  (struct.unpack_from('>IIIII', data, 32 + 20 * i) for i in range(16))]

def mapped(sections, va):
    for off, base, n in sections:
        if base <= va < base + n:
            return off + va - base
    raise ValueError(hex(va))

def lines(name):
    for path in sorted(DIS.glob(name + '-sec*.disasm.txt')):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            parts = line.split('\t')
            if len(parts) >= 3 and re.fullmatch('[0-9a-f]+:', parts[0].strip()):
                yield int(parts[0].strip()[:-1], 16), parts[2], path.name, number, line, bytes.fromhex(parts[1])

def references(name):
    regs = {}
    for va, ins, path, number, raw, code in lines(name):
        for op in re.split(r'\s*(?:\|\||->)\s*', ins):
            m = re.fullmatch(r'seth (\w+),#0x([0-9a-f]+)', op)
            if m:
                regs[m[1]] = int(m[2], 16) << 16
                continue
            m = re.fullmatch(r'(ldi|ld24) (\w+),(?:#)?(-?\d+|0x[0-9a-f]+)', op)
            if m:
                regs[m[2]] = int(m[3], 0)
                yield va, regs[m[2]], 'immediate', op, path, number
                continue
            m = re.fullmatch(r'(or3|add3) (\w+),(\w+),#(0x[0-9a-f]+|-?\d+)', op)
            if m:
                a, b = regs.get(m[3]), int(m[4], 0)
                regs[m[2]] = None if a is None else ((a | b) if m[1] == 'or3' else (a + b) & 0xffffffff)
                if regs[m[2]] is not None:
                    yield va, regs[m[2]], 'constant', op, path, number
                continue
            m = re.fullmatch(r'mv (\w+),(\w+)', op)
            if m:
                regs[m[1]] = regs.get(m[2])
                continue
            m = re.fullmatch(r'(ld\w*|st\w*) (\w+),@(?:\((-?\d+),(\w+)\)|(\w+))', op)
            if m:
                a, delta = regs.get(m[4] or m[5]), int(m[3] or 0)
                if a is not None and a > 0x10000:
                    yield va, (a + delta) & 0xffffffff, m[1], op, path, number
                if m[1].startswith('ld'):
                    regs[m[2]] = None
                continue
            m = re.fullmatch(r'(jl|jmp) (\w+)', op)
            if m:
                a = regs.get(m[2])
                if a is not None:
                    yield va, a, 'call' if m[1] == 'jl' else 'jump', op, path, number
                if m[1] == 'jl':
                    for i in range(8):
                        regs['r' + str(i)] = None
                else:
                    regs = {}
                continue
            m = re.fullmatch(r'(bl|bra) (0x[0-9a-f]+)', op)
            if m:
                yield va, int(m[2], 16), 'call' if m[1] == 'bl' else 'branch', op, path, number
                regs = {}
                continue
            m = re.match(r'(\w+) (r\d+|fp|lr|sp)(?:,|$)', op)
            if m and m[1] not in ['cmp', 'cmpu', 'cmpi', 'cmpui', 'beqz', 'bnez', 'beq', 'bne', 'push', 'st', 'stb', 'sth']:
                regs[m[2]] = None

def dump(name, start, end, label):
    data, secs = image(name)
    out = [f'# {name} VMA {start:#010x}..{end:#010x} (end exclusive)',
           f'# SHA256 {hashlib.sha256(data).hexdigest()}',
           '# Each instruction is verified against the original firmware. Offset is a firmware file offset.']
    source = None
    count = 0
    for va, ins, path, number, raw, code in lines(name):
        if start <= va < end:
            off = mapped(secs, va)
            assert data[off:off + len(code)] == code, (hex(va), raw)
            if path != source:
                out.append('# source: ' + path)
                source = path
            out.append(f'{raw}  # file={off:#x}; source_line={number}')
            count += 1
    (HERE / (label + '.disasm.txt')).write_text('\n'.join(out) + '\n')
    print(label, count, 'verified instructions')

def index(name):
    with (HERE / (name + '-refs.tsv')).open('w') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['source_vma', 'target', 'kind', 'instruction', 'source_file', 'source_line'])
        for va, target, kind, op, path, number in references(name):
            writer.writerow([hex(va), hex(target), kind, op, path, number])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', action='store_true')
    ap.add_argument('--dump', nargs=4)
    ap.add_argument('--refs', nargs='+')
    args = ap.parse_args()
    if args.index:
        for name in ['ilaunch3', 'jlaunch3']:
            index(name)
    if args.dump:
        name, start, end, label = args.dump
        dump(name, int(start, 0), int(end, 0), label)
    if args.refs:
        name, *targets = args.refs
        targets = set(int(t, 0) for t in targets)
        with (HERE / (name + '-refs.tsv')).open() as f:
            for row in csv.DictReader(f, delimiter='\t'):
                if int(row['target'], 0) in targets:
                    print(row['source_vma'], row['target'], row['kind'], row['instruction'])

if __name__ == '__main__':
    main()
