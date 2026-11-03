#!/usr/bin/env python3
"""Rebuild bounded CPU data flows from retained listings and official files."""
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('study', HERE / 'study.py')
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def excerpt(lines, lo, hi, tag):
    rows = []
    for va in sorted(lines.rows):
        if lo <= va < hi:
            size, asm, raw, source, no = lines.get(va)
            rows.append(f'{va:08x} file={lines.image.offset(va):#x} {raw.hex(" ")}  {asm}  [{source}:{no}]')
    assert rows, tag
    S.put(f'evidence/{tag}.txt', f'# {lines.image.name} SHA256 {S.digest(lines.image.data)}\n' + '\n'.join(rows) + '\n')
    return {'tag': tag, 'image': lines.image.name, 'lo': hex(lo), 'hi': hex(hi), 'rows': len(rows)}


def model(A, lines, defaults, mode, extra_f=None, changes=None, fast=False):
    vm = A.Arithmetic(lines, defaults)
    _, _, fields = A.fields(defaults, mode)
    for i in range(0x80):
        vm.store(0x20383F08 + i, 0, 1)
    for i, value in {**fields, **(extra_f or {})}.items():
        vm.store(0x20383F08 + i, value, 1)
    for addr, data in (changes or {}).items():
        for i, value in enumerate(data):
            vm.store(addr + i, value, 1)
    vm.put('r4', 0x20383F08)
    vm.run(0x20115E80 if fast else 0x20116850)
    if not fast:
        vm.put('lr', 0x7FFFFFFC)
        vm.put('r4', 0x2029C720)
        vm.put('r5', 0x20142B88)
        vm.run(0x20257690)
    return vm


def diff(base, other):
    return {hex(addr): [hex(value), hex(other.mmio[addr])]
            for addr, value in base.mmio.items() if value != other.mmio[addr]}


def main():
    assert sys.flags.isolated and sys.dont_write_bytecode
    assert S.git('check-ignore', str(S.LOCAL / 'check')).strip()
    A = S.load_prior()
    unit = A.Listing(S.Image('jlaunch3'))
    body = A.Listing(S.Image('ilaunch3'))
    windows = [
        (unit, 0x20110590, 0x20110790, 'general-record-fields'),
        (unit, 0x20111B28, 0x20111C20, 'mode-record-fields'),
        (unit, 0x20115E80, 0x2011659C, 'fast-type32'),
        (unit, 0x20116850, 0x201180E4, 'full-type32'),
        (unit, 0x20257690, 0x20257D00, 'type32-writer'),
        (unit, 0x20242B68, 0x20243178, 'v-w-x'),
        (unit, 0x20258324, 0x202583D0, 'type32-access'),
        (body, 0x20218D28, 0x20218E00, 'body-display-size'),
        (body, 0x203CB700, 0x203CB900, 'body-display-driver'),
    ]
    index = [excerpt(*row) for row in windows]
    defaults, origins = A.script()
    results = {}
    saved = json.loads(S.read(S.ROOT / 'research/peaking_color/local/register_reconstruction.json'))
    for mode in (1, 2):
        base = model(A, unit, defaults, mode)
        expected = {int(k, 16): int(v, 16) for k, v in saved[f'mode{mode}']['full_registers'].items()}
        assert base.mmio == expected
        fast = model(A, unit, defaults, mode, fast=True)
        assert all(base.mmio[k] == v for k, v in fast.mmio.items())
        results[f'mode{mode}'] = {'full_words': len(base.mmio), 'fast_words': len(fast.mmio)}
        for name, changes in [
            ('ramp_node', {0x20022000 + 0x2402: bytes([0x3F])}),
            ('block_first', {0x20022000 + 0x0B5C: bytes([0x40])}),
            ('block_second', {0x20022000 + 0x0BAC: bytes([0x40])}),
        ]:
            variant = model(A, unit, defaults, mode, changes=changes)
            results[f'mode{mode}_{name}'] = diff(base, variant)
        for field, value in [(0, 1), (1, 1), (0x25, 1), (0x25, 4), (0x25, 7),
                             (0x29, 1), (0x29, 2), (0x2A, 1), (0x2B, 1)]:
            variant = model(A, unit, defaults, mode, extra_f={field: value})
            results[f'mode{mode}_f{field:02x}_{value}'] = diff(base, variant)
    S.put('cpu_results.json', results)
    ranges = [(0x2012EF68, 160), (0x2012D58C, 96 * 8),
              (0x2012D88C, 96 * 8), (0x2012F01A, 96)]
    tables = {'rom': {hex(va): {'file': hex(unit.image.offset(va)),
                              'data': unit.image.bytes(va, n).hex(' ')} for va, n in ranges},
              't': {hex(lo): {'data': bytes(defaults.get(i, 0) for i in range(lo, lo + n)).hex(' '),
                             'fully_defined': all(i in defaults for i in range(lo, lo + n))}
                    for lo, n in [(0x0B4C, 192), (0x2400, 32), (0x3B00, 20)]}}
    S.put('table_sources.json', tables)
    S.put('evidence_index.json', index)
    prior_path = S.LOCAL / 'reads.json'
    prior = json.loads(prior_path.read_text())
    for rel, value in S.READS.items():
        assert rel not in prior or prior[rel] == value, rel
    S.put('reads.json', {**prior, **S.READS})
    print(json.dumps({'windows': len(index), 'instruction_rows': sum(r['rows'] for r in index),
                      'models': len(results)}))


if __name__ == '__main__':
    main()
