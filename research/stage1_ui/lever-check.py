#!/usr/bin/env python3
"""Verify only lever evidence against the unchanged camera firmware."""
import bisect
import hashlib
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIRM = ROOT / 'artifacts/firmware/gxr-1.51'
DIS = ROOT / 'research/tooling_m32r/disasm'
D = (FIRM / 'ilaunch3').read_bytes()
D4 = (FIRM / 'ilaunch4').read_bytes()
SECS = [(i, s + 0x200, v, n) for i in range(16)
        for s, v, n, _, _ in [struct.unpack_from('>IIIII', D, 32 + 20 * i)]]


def offset(va):
    return next(s + va - v for _, s, v, n in SECS if v <= va < v + n)


def at(va, length):
    o = offset(va)
    return D[o:o + length]


originals = {}
excerpt_rows = []
for p in sorted(HERE.glob('lever-*.disasm.txt')):
    for no, line in enumerate(p.read_text().splitlines(), 1):
        m = re.match(r'([^:]+):(\d+) \| ([0-9a-f]+):\t([0-9a-f ]+)\t(.+)$', line)
        if not m:
            continue
        source, source_no, va = m[1], int(m[2]), int(m[3], 16)
        if source not in originals:
            originals[source] = (DIS / source).read_text().splitlines()
        assert originals[source][source_no - 1] == line.split(' | ', 1)[1]
        assert at(va, len(bytes.fromhex(m[4]))) == bytes.fromhex(m[4])
        excerpt_rows.append({'excerpt': p.name, 'excerpt_line': no,
                             'vma': hex(va), 'file_offset': hex(offset(va)),
                             'source': f'{source}:{source_no}'})

descriptor = at(0x2022F5A8, 12)
assert struct.unpack_from('>I', descriptor)[0] == 0x2022D610
assert descriptor[4] == 7
assert descriptor[5:8] == b'\xff\xff\xff'
assert struct.unpack_from('>I', descriptor, 8)[0] == 0
assert at(0x2037F492, 8) == bytes([0, 9, 1, 10, 3, 6, 4, 5])
assert struct.unpack('>H', at(0x2037C918 + 3 * 2, 2))[0] == 0x18
assert struct.unpack('>H', at(0x2037738C + (3 - 1) * 2, 2))[0] == 0x08
assert struct.unpack('>H', at(0x20377434 + (8 - 1) * 2, 2))[0] == 0x38
assert struct.unpack('>H', at(0x20224B38 + (33 - 1) * 2, 2))[0] == 0x180
assert struct.unpack_from('>I', at(0x2022FE1C + 7 * 4, 4))[0] == 0x205BEB08
assert at(0x2023FFCA, 2) == bytes([0x0B, 0])

aux = []
for i in range(7):
    va = 0x2023FD38 + i * 12
    entry = struct.unpack('>III', at(va, 12))
    assert entry == ((0, 0, 0) if i < 3 else (0x205BEAD4, 0x2023FFCA, 0))
    aux.append({'index': i, 'vma': hex(va), 'file_offset': hex(offset(va)),
                'fields': [hex(v) for v in entry], 'raw': at(va, 12).hex(' ')})

# Decode "Detail" with the original English converter's tables.
upper = at(0x2023BC6F, 60)
lower = at(0x2023BCAB, 34)
glyphs = struct.unpack('>60H', at(0x20222783, 120)) + struct.unpack('>34H', at(0x20222C82, 68))
inverse = {g: chr(c) for c, g in zip(upper + lower, glyphs)}
base, length, text_id = 0x8C958, 0xE5D8, 0x1F5
strings = D4[base:base + length].split(b'\0')
raw = strings[text_id]
label = ''.join(inverse[g] for g in struct.unpack(f'>{len(raw) // 2}H', raw))
assert label == 'Detail'
label_offset = base + sum(len(b) + 1 for b in strings[:text_id])

tables = {
    'image_descriptor': {'vma': '0x2022f5a8', 'file_offset': hex(offset(0x2022F5A8)),
                         'raw': descriptor.hex(' '), 'count': descriptor[4]},
    'image_choice_values': {'vma': '0x2037f492', 'file_offset': hex(offset(0x2037F492)),
                            'raw': at(0x2037F492, 8).hex(' ')},
    'image_auxiliary_entries': aux,
    'detail_resource': {'resource_id': hex(text_id), 'text': label,
                        'pointer_cell': '0x205bead4', 'ilaunch4_file_offset': hex(label_offset),
                        'raw': raw.hex(' ')},
    'arrow_icon': {'vma': '0x2023ffca', 'file_offset': hex(offset(0x2023FFCA)),
                   'raw': at(0x2023FFCA, 2).hex(' '),
                   'note': 'The byte is an icon identifier; camera visual appearance was not observed.'},
}
(HERE / 'lever-data.json').write_text(json.dumps(tables, ensure_ascii=False, indent=2) + '\n')
(HERE / 'lever-evidence-index.json').write_text(json.dumps(excerpt_rows, indent=2) + '\n')

hashes = {n: hashlib.sha256((FIRM / n).read_bytes()).hexdigest() for n in ('ilaunch3', 'ilaunch4')}
assert hashes['ilaunch3'] == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
assert hashes['ilaunch4'] == 'c9271288f8d395296623a3fe5358b2d83dec8730a89ed138a48ff8a2e8f14a5a'
result = {'checked_excerpt_instructions': len(excerpt_rows),
          'checked_image_auxiliary_entries': len(aux), 'source_sha256': hashes,
          'firmware_executed': False, 'firmware_patched': False, 'camera_connected': False,
          'browser_used': False, 'scope': 'lever evidence only'}
(HERE / 'lever-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
