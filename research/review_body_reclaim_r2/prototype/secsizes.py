#!/usr/bin/python3 -I
"""Per-section sizes of a strictly linked (or rejected) prototype variant.

Usage: secsizes.py <variant_dir> [--diff <other_variant_dir>]
Reads <variant>/build/resident.map written by proto_strict.py (the map is
written even when the margin assertion rejects the link) and prints every
input section placed in .resident with its size. With --diff it prints the
per-section change against another variant.
"""
import re, sys
from pathlib import Path


def sections(v):
    text = (Path(v) / 'build/resident.map').read_text()
    out, in_res, pending = {}, False, None
    for line in text.splitlines():
        if line.startswith('.resident'):
            in_res = True
            continue
        if in_res and (line.startswith('.root') or line.startswith('__resident_code_end')):
            break
        if not in_res:
            continue
        m = re.match(r'^ (\.\S+)\s*$', line)
        if m:
            pending = m.group(1)
            continue
        m = re.match(r'^ (\.\S+)?\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S+)', line)
        if m:
            name = m.group(1) or pending
            pending = None
            size = int(m.group(3), 16)
            if name and size:
                key = f'{Path(m.group(4)).name}:{name}'
                out[key] = out.get(key, 0) + size
        elif re.match(r'^ \*fill\*\s+0x[0-9a-f]+\s+0x([0-9a-f]+)', line):
            n = int(re.match(r'^ \*fill\*\s+0x[0-9a-f]+\s+0x([0-9a-f]+)', line).group(1), 16)
            out['*fill*'] = out.get('*fill*', 0) + n
    return out


def main():
    a = sections(sys.argv[1])
    if len(sys.argv) > 3 and sys.argv[2] == '--diff':
        b = sections(sys.argv[3])
        for k in sorted(set(a) | set(b), key=lambda k: a.get(k, 0) - b.get(k, 0)):
            d = a.get(k, 0) - b.get(k, 0)
            if d:
                print(f'{d:+6d} {b.get(k, 0):6d} -> {a.get(k, 0):6d} {k}')
        print(f'{sum(a.values()) - sum(b.values()):+6d} total {sum(b.values())} -> {sum(a.values())}')
        return
    for k, n in sorted(a.items(), key=lambda kv: -kv[1]):
        print(f'{n:6d} {k}')
    print(f'{sum(a.values()):6d} total')


if __name__ == '__main__':
    main()
