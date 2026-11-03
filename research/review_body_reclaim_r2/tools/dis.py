#!/usr/bin/python3 -I
"""Disassemble a range of the official 1.51 ilaunch3 by run-time address.

Usage: dis.py <start> <end>         print disassembly of [start,end)
       dis.py --word <addr> [n]     print n big-endian words
       dis.py --refs <value>        list 4-byte aligned words equal to value
       dis.py --calls <target>      list bl/bra (24-bit) to target in code sections
Output contains stock instructions; keep it under the ignored local/ tree.
"""
import struct, subprocess, sys, tempfile
from pathlib import Path

R = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
IMG = R / 'artifacts/firmware/gxr-1.51/ilaunch3'
OBJDUMP = R / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
raw = IMG.read_bytes()
rows = [struct.unpack_from('>5I', raw, 0x20 + 20 * i) for i in range(16)]
rows = [r for r in rows if r[2]]


def offset(a, n=4):
    for src, base, size, _, _ in rows:
        if base <= a and a + n <= base + size:
            return src + 0x200 + a - base
    raise ValueError(hex(a))


def read(a, n):
    o = offset(a, n)
    return raw[o:o + n]


def dis(a, b):
    with tempfile.NamedTemporaryFile(suffix='.bin') as f:
        f.write(read(a, b - a)); f.flush()
        out = subprocess.run([OBJDUMP, '-D', '-b', 'binary', '-m', 'm32r', '-EB',
                              f'--adjust-vma=0x{a:x}', f.name], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.strip().startswith(('2', '3', '1', '0')) and ':' in line and '\t' in line:
            print(line)


def main():
    if sys.argv[1] == '--word':
        a = int(sys.argv[2], 0); n = int(sys.argv[3], 0) if len(sys.argv) > 3 else 1
        for i in range(n):
            print(f'0x{a+4*i:08x} {read(a+4*i,4).hex()}')
    elif sys.argv[1] == '--refs':
        v = struct.pack('>I', int(sys.argv[2], 0))
        for src, base, size, _, _ in rows:
            blob = raw[src + 0x200:src + 0x200 + size]
            i = blob.find(v)
            while i >= 0:
                if i % 2 == 0:
                    print(f'0x{base+i:08x}')
                i = blob.find(v, i + 1)
    elif sys.argv[1] == '--calls':
        t = int(sys.argv[2], 0)
        for src, base, size, _, _ in rows:
            blob = raw[src + 0x200:src + 0x200 + size]
            for i in range(0, len(blob) - 3, 4):
                w = int.from_bytes(blob[i:i + 4], 'big')
                op = w >> 24
                if op in (0xfe, 0xff, 0xfd, 0xfc):  # bl24 / bra24 / bnc24 / bc24
                    d = w & 0xffffff
                    if d & 0x800000:
                        d -= 1 << 24
                    if base + i + 4 * d == t:
                        kind = {0xfe: 'bl', 0xff: 'bra', 0xfd: 'bnc', 0xfc: 'bc'}[op]
                        print(f'0x{base+i:08x} {kind}')
    else:
        dis(int(sys.argv[1], 0), int(sys.argv[2], 0))


if __name__ == '__main__':
    main()
