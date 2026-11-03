#!/usr/bin/env python3
"""Find bounded address constructions; these are references, not a call graph."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sp = importlib.util.spec_from_file_location('study', HERE / 'study.py')
S = importlib.util.module_from_spec(sp)
sp.loader.exec_module(S)


def references(lines, targets):
    found = {hex(v): [] for v in targets}
    pending = {}
    for va in sorted(lines.rows):
        asm = lines.rows[va][1]
        for part in re.split(r'\s*(?:->|\|\|)\s*', asm):
            m = re.fullmatch(r'seth (r\d+|fp|lr),#(0x[0-9a-f]+)', part)
            if m:
                pending[m[1]] = (int(m[2], 16) << 16, va)
                continue
            m = re.fullmatch(r'or3 (r\d+|fp|lr),(r\d+|fp|lr),#(0x[0-9a-f]+)', part)
            if m:
                if m[2] in pending:
                    high, start = pending[m[2]]
                    value = high | int(m[3], 16)
                    if va - start <= 48 and value in targets:
                        lines.get(start)
                        lines.get(va)
                        found[hex(value)].append({'start': hex(start), 'end': hex(va),
                                                  'register': m[1]})
                pending.pop(m[1], None)
            elif part.startswith(('jl ', 'bl ', 'jmp ')):
                pending.clear()
            elif not part.startswith(('st ', 'sth ', 'stb ', 'cmp', 'b', 'push ', 'nop')):
                m = re.match(r'\w+ (r\d+|fp|lr)(?:,|$)', part)
                if m:
                    pending.pop(m[1], None)
    return found


def main():
    assert sys.flags.isolated and sys.dont_write_bytecode
    parser = argparse.ArgumentParser()
    parser.add_argument('image')
    parser.add_argument('tag')
    parser.add_argument('targets', nargs='+', type=lambda v: int(v, 0))
    args = parser.parse_args()
    lines = S.listing(args.image)
    refs = references(lines, set(args.targets))
    S.put('references/' + args.tag + '.json', refs)
    prior = json.loads((S.LOCAL / 'reads.json').read_text())
    S.put('reads.json', {**prior, **S.READS})
    print(json.dumps({key: {'count': len(rows), 'first': rows[:5]} for key, rows in refs.items()}))


if __name__ == '__main__':
    main()
