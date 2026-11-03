#!/usr/bin/python3 -I
"""List code that builds any address in [lo,hi) with seth/or3 (or seth/add3),
and enclosing function starts (nearest preceding `push lr` prologue heuristic).

Usage: addr_refs.py <lo> <hi>
"""
import sys
from pathlib import Path

sys.argv, argv = sys.argv[:1], sys.argv[1:]
exec((Path(__file__).parent / 'dis.py').read_text().split('def main')[0])


def main():
    lo, hi = int(argv[0], 0), int(argv[1], 0)
    for src, base, size, _, _ in rows:
        blob = raw[src + 0x200:src + 0x200 + size]
        for i in range(0, len(blob) - 7, 2):
            a = int.from_bytes(blob[i:i + 2], 'big')
            if (a & 0xf0ff) != 0xd0c0:
                continue
            rx = (a >> 8) & 15
            h = int.from_bytes(blob[i + 2:i + 4], 'big')
            for j in range(i + 4, min(i + 14, len(blob) - 3), 2):
                b = int.from_bytes(blob[j:j + 2], 'big')
                if (b & 0xf0f0) in (0x80e0, 0x80a0):
                    if (b & 15) != rx:
                        continue
                    l = int.from_bytes(blob[j + 2:j + 4], 'big')
                    v = (h << 16) | l if (b & 0xf0) == 0xe0 else ((h << 16) + (l - 0x10000 if l & 0x8000 else l)) & 0xffffffff
                    if lo <= v < hi:
                        print(f'0x{base+i:08x} builds 0x{v:08x}')
                    break


if __name__ == '__main__':
    main()
