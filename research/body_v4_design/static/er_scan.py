#!/usr/bin/python3 -I -B
"""v4 design r2, read-only static scan for the proposed extension region (ER)
at the top of the body image arena.

Input: official ilaunch3 (da1980e9...) and the repository disassembly.
Output: JSON on stdout.  Writes nothing.

What it reports (linear candidates, not interprocedural proofs):
  1. constants (seth/or3, ld24, raw section words) that point into
     the arena top 16 MiB, in the 0x8 window or the 0x2 window;
  2. constants equal to the arena size / end / 0x88000000;
  3. every load/store whose resolved address is in the region table
     0x200C0DC0..0x200C0DDF (to find runtime writers of the size word);
  4. 0x2-window constants above the OSD end 0x208BC000 (alias evidence);
  5. arena-start readers that subtract a constant from start+size
     (end-relative users) and the constant used.
"""
import hashlib
import importlib.util
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    'hp', ROOT / 'research/hidden_processing/analyze.py')
hp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hp)

data = (hp.FIRM / 'ilaunch3').read_bytes()
secs = hp.sections(data)

A, SIZE = 0x808BC000, 0x076C0000
END = A + SIZE                      # 0x87F7C000
TOP16 = (END - 0x01000000, END)     # arena top 16 MiB, 0x8 window
TOP16_2 = (TOP16[0] - 0x60000000, TOP16[1] - 0x60000000)
TABLE = (0x200C0DC0, 0x200C0DE0)
OSD_END_2 = 0x208BC000


def hexs(v):
    return f'{v:#010x}'


def in_rng(v, r):
    return r[0] <= v < r[1]


out = {
    'input_sha256': hashlib.sha256(data).hexdigest(),
    'arena': {'start': hexs(A), 'size': hexs(SIZE), 'end': hexs(END)},
    'constants_in_top16_8window': [],
    'constants_in_top16_2window': [],
    'constants_size_or_end': [],
    'table_accesses': {'loads': {}, 'stores': []},
    'two_window_above_osd': {},
    'eight_window_any': {},
    'raw_words': {'top16_8window': [], 'top16_2window': [], 'size_or_end': []},
    'end_relative_sites': [],
}

special = {SIZE, END, END & 0x0FFFFFFF, 0x88000000, 0x08000000, 0x076C0000 - 0x00C00000}

# 1-4: resolved constants and memory operands from the shared indexer
for va, val, kind, path, no, op in hp.refs('ilaunch3'):
    rec = {'pc': hexs(va), 'value': hexs(val), 'kind': kind, 'op': op}
    if in_rng(val, TOP16):
        out['constants_in_top16_8window'].append(rec)
    if in_rng(val, TOP16_2):
        out['constants_in_top16_2window'].append(rec)
    if val in special:
        out['constants_size_or_end'].append(rec)
    if in_rng(val, TABLE) and kind != 'constant':
        if kind.startswith('st'):
            out['table_accesses']['stores'].append(rec)
        else:
            k = hexs(val)
            out['table_accesses']['loads'][k] = out['table_accesses']['loads'].get(k, 0) + 1
    if OSD_END_2 <= val < 0x28000000 and kind == 'constant':
        k = hexs(val & 0xFFF00000)
        out['two_window_above_osd'][k] = out['two_window_above_osd'].get(k, 0) + 1
    if 0x80000000 <= val < 0x88000000 and kind == 'constant':
        k = hexs(val & 0xFFF00000)
        out['eight_window_any'][k] = out['eight_window_any'].get(k, 0) + 1

# ld24 immediates (24-bit) equal to size-related values are covered by 'special'
for va, ins, path, no, line in hp.lines('ilaunch3'):
    m = re.search(r'ld24 r\d+,0x([0-9a-f]+)', ins)
    if m and int(m.group(1), 16) in special:
        out['constants_size_or_end'].append({'pc': hexs(va), 'value': '0x' + m.group(1), 'kind': 'ld24', 'op': ins})

# raw big-endian words in every loaded section (data pointers, literal tables)
for s, v, n in secs:
    blob = data[s:s + n]
    for i in range(0, len(blob) - 3, 4):
        w = struct.unpack_from('>I', blob, i)[0]
        rec = {'vma': hexs(v + i), 'value': hexs(w)}
        if in_rng(w, TOP16):
            out['raw_words']['top16_8window'].append(rec)
        elif in_rng(w, TOP16_2):
            out['raw_words']['top16_2window'].append(rec)
        elif w in (SIZE, END, 0x88000000):
            out['raw_words']['size_or_end'].append(rec)

# 5: end-relative users: start read, size read, add, then a constant subtracted
lines = list(hp.lines('ilaunch3'))
for i, (va, ins, path, no, line) in enumerate(lines):
    if '#0xdd4' not in ins or 'or3' not in ins:
        continue
    win = lines[i:i + 12]
    txt = ' ; '.join(w[1] for w in win)
    if 'add ' not in txt:
        continue
    consts = []
    for w in win:
        m = re.search(r'ld24 r\d+,0x([0-9a-f]+)', w[1])
        if m:
            consts.append(int(m.group(1), 16))
    if 'sub ' in txt and consts:
        out['end_relative_sites'].append({'pc': hexs(va), 'constants': [hexs(c) for c in consts],
                                          'window': txt[:400]})

for k in ('constants_in_top16_8window', 'constants_in_top16_2window', 'constants_size_or_end'):
    out[k + '_count'] = len(out[k])
out['table_accesses']['store_count'] = len(out['table_accesses']['stores'])
print(json.dumps(out, indent=1))
