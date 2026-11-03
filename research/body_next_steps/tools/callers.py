#!/usr/bin/python3 -I
"""List call sites of a stock function in the official 1.51 ilaunch3.

Usage: callers.py <target> [--arg-window N]
Finds `seth rX,#hi ; or3 rX,rX,#lo` pairs that build the target address
(followed within a few words by `jl rX`), plus 24-bit bl/bra to it, and
prints the preceding N instruction words so the r4 argument is visible.
Output contains stock instructions; keep it under the ignored local/ tree.
"""
import sys
from pathlib import Path

sys.argv, argv = sys.argv[:1], sys.argv[1:]
exec((Path(__file__).parent / 'dis.py').read_text().split('def main')[0])


def main():
    target = int(argv[0], 0)
    window = int(argv[2], 0) if len(argv) > 2 and argv[1] == '--arg-window' else 6
    hi, lo = target >> 16, target & 0xffff
    hits = []
    for src, base, size, _, _ in rows:
        blob = raw[src + 0x200:src + 0x200 + size]
        for i in range(0, len(blob) - 7, 2):
            a = int.from_bytes(blob[i:i + 2], 'big')
            # seth rX,#imm16 : 0xD?C0 imm16
            if (a & 0xf0ff) == 0xd0c0 and int.from_bytes(blob[i + 2:i + 4], 'big') == hi:
                rx = (a >> 8) & 15
                for j in range(i + 4, min(i + 12, len(blob) - 3), 2):
                    b = int.from_bytes(blob[j:j + 2], 'big')
                    if b == (0x80e0 | (rx << 8) | rx) and int.from_bytes(blob[j + 2:j + 4], 'big') == lo:
                        hits.append((base + i, 'seth/or3'))
                        break
        for i in range(0, len(blob) - 3, 4):
            w = int.from_bytes(blob[i:i + 4], 'big')
            if w >> 24 in (0xfe, 0xff):
                d = w & 0xffffff
                if d & 0x800000:
                    d -= 1 << 24
                if base + i + 4 * d == target:
                    hits.append((base + i, 'bl' if w >> 24 == 0xfe else 'bra'))
    for a, kind in sorted(hits):
        print(f'== 0x{a:08x} {kind}')
        start = (a - 4 * window) & ~3
        try:
            dis(start, a + 12)
        except ValueError:
            pass


if __name__ == '__main__':
    main()
