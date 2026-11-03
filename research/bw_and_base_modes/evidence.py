#!/usr/bin/env python3
"""Read-only M32R evidence viewer; generated JSON stays beside this script."""
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
NAMES = {'body': 'ilaunch3', 'module': 'jlaunch3'}


def mapped(data, va):
    for i in range(16):
        off, base, size, _, _ = struct.unpack_from('>IIIII', data, 32 + i * 20)
        if base <= va < base + size:
            return off + 512 + va - base
    raise ValueError(f'unmapped VMA {va:#x}')


def lines(name):
    for path in sorted(DIS.glob(name + '-sec*.disasm.txt')):
        with path.open() as stream:
            for no, line in enumerate(stream, 1):
                parts = line.rstrip().split('\t')
                if len(parts) >= 3 and re.fullmatch(r'[0-9a-f]+:', parts[0]):
                    yield int(parts[0][:-1], 16), parts[1], parts[2], path, no


def window(name, start, end):
    data = (FIRM / name).read_bytes()
    out = []
    for va, raw, instruction, path, no in lines(name):
        if start <= va < end:
            off = mapped(data, va)
            machine = bytes.fromhex(raw)
            assert data[off:off + len(machine)] == machine, (name, hex(va))
            out.append(dict(vma=f'0x{va:08x}', file_offset=hex(off), raw=machine.hex(),
                            instruction=instruction, original=path.name, line=no))
    if not out:
        raise ValueError('empty window')
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['window', 'refs', 'find', 'verify'])
    parser.add_argument('target', choices=['body', 'module'])
    parser.add_argument('values', nargs='*')
    args = parser.parse_args()
    name = NAMES[args.target]
    if args.operation == 'window':
        for row in window(name, *(int(v, 0) for v in args.values)):
            print(f"{row['vma']} [file {row['file_offset']}]: {row['raw']}  {row['instruction']}")
    elif args.operation == 'refs':
        targets = {int(v, 0) for v in args.values}
        with (ROOT / f'research/hidden_processing/{name}-refs.tsv').open() as stream:
            for row in csv.DictReader(stream, delimiter='\t'):
                if int(row['target'], 0) in targets:
                    print(row)
    elif args.operation == 'find':
        pattern = re.compile(' '.join(args.values))
        for va, raw, instruction, path, no in lines(name):
            if pattern.search(instruction):
                print(f'{va:#010x}: {raw}  {instruction}')
    else:
        spec = json.loads((HERE / 'windows.json').read_text())
        results = {key: window(name, int(start, 0), int(end, 0))
                   for key, target, start, end in spec if target == args.target}
        inventory = {'file': str(FIRM / name),
                     'sha256': hashlib.sha256((FIRM / name).read_bytes()).hexdigest(),
                     'instruction_count': sum(map(len, results.values())),
                     'windows': results}
        (HERE / f'{name}-evidence.json').write_text(json.dumps(inventory, indent=2) + '\n')
        print(json.dumps({'target': args.target, 'sha256': inventory['sha256'],
                          'windows': len(results),
                          'verified_instruction_rows': inventory['instruction_count']}))


if __name__ == '__main__':
    main()
