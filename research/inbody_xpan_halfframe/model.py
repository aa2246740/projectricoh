#!/usr/bin/python3 -I -B
"""Read-only static model for research/inbody_xpan_halfframe/REPORT.md.

1. Body image arena: reads the initialised region table words in the
   official ilaunch3 (0x200C0DD0 start, 0x200C0DD4 size) and replays the
   normal capture layout of 0x2016F554 -> 0x2016EED8 with the constants
   that appear as immediates in those functions.  Runtime values that are
   not in the image (R = per-RAW allocation, H = metadata front, M = YCC)
   are parameters; the defaults follow research/grain_raw_feasibility.
2. Per-shot time estimates from the 2026-11-01 field probe bandwidths
   (captures/cpuprobe-field-20261101/RESULTS.md).

Prints JSON to stdout.  Writes nothing."""
import importlib.util
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hp', ROOT / 'research/hidden_processing/analyze.py')
hp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hp)
data = (hp.FIRM / 'ilaunch3').read_bytes()
secs = hp.sections(data)


def word(vma):
    off = hp.mapped(secs, vma, reverse=True)
    return struct.unpack('>I', data[off:off + 4])[0]


def align(n, a=7680):
    return (n + a - 1) // a * a


# ---- 1. region table (initialised data, static) -------------------------
table = {}
for vma in (0x200C0DC0, 0x200C0DC8, 0x200C0DD0, 0x200C0DD8):   # (start, size) pairs
    s, n = word(vma), word(vma + 4)
    table[f'{vma:#010x}'] = {'start': f'{s:#010x}', 'size': n, 'end': f'{s + n:#010x}'}
A = word(0x200C0DD0)
SIZE = word(0x200C0DD4)
END = A + SIZE

# ---- 2. normal layout (0x2016F554 then 0x2016DEB8/0x2016EED8) -----------
W, Hpx = 4288, 2848
cfa = 4304 * 2862 * 12 // 8                  # 18,477,072 B (DNG strip, measured)
R = align(cfa)                               # assumption: 7680-rounded
H = align(18028)                             # 23,040 (P1_P4 report)
M = align(W * Hpx * 2)                       # 24,430,080 (P1_P4 report)
P = {}
P[0x04] = A
P[0x08] = A + 0xA200
P[0x0C] = P[0x08] + 0xC00
P[0x10] = P[0x0C] + 0x400
P[0x14] = P[0x10] + 0x63000
P[0x18] = P[0x1C] = P[0x14] + 0x16800
P[0x20] = P[0x18] + 0x96000
P[0x24] = P[0x20] + 0x96000
P[0x28] = P[0x24] + 0x96000
P[0x30] = P[0x28] + 0x96000
P[0xF8] = END
P[0xF4] = END - align(0x40000)               # 0x2016F93C: 0x2016DAB8(0x40000)
P[0x2C] = P[0x30]                            # 0x2016DEB8
P[0x34] = P[0x30] + 0x96000
P[0x38] = P[0x34] + 0x9600                   # 0x2016EED8
P[0x48] = P[0x38] + 0x9600
P[0x4C] = P[0x48] + 0x96000
P[0x8C] = P[0xAC] = P[0x4C] + 0x96000        # RAW header 1
P[0xB0] = P[0xAC] + 0x18000                  # RAW data 1
P[0xA4] = P[0xB0] + R                        # RAW header 2
P[0xA8] = P[0xA4] + 0x18000                  # RAW data 2
P[0xD4] = P[0xA8] + R


def layout(double):
    q = dict(P)
    q[0xD8] = q[0xD4] + H                    # YCC 1 (after metadata front)
    if double:                               # byte 0x2057AC8E == 2
        q[0xDC] = q[0xD8] + M
        q[0xE0] = q[0xDC] + H
    else:
        q[0xDC] = q[0xD4]
        q[0xE0] = q[0xD8]
    q[0xEC] = q[0xE0] + M                    # output-slot pool start
    q[0xF0] = END - 1                        # pool end (inclusive)
    return q


out = {'region_table': table, 'arena': {'start': f'{A:#010x}', 'size': SIZE, 'end': f'{END:#010x}'},
       'assumed': {'R_raw_alloc': R, 'H_meta_front': H, 'M_ycc': M}}
for name, dbl in (('single_ycc', False), ('double_ycc', True)):
    q = layout(dbl)
    tail = END - q[0xEC]
    out[name] = {
        'fields': {f'P+{k:#04x}': f'{v:#010x}' for k, v in sorted(q.items())},
        'pool_tail_bytes': tail,
        'pool_tail_MB': round(tail / 1e6, 2),
    }

# ---- 3. carve-out candidate ---------------------------------------------
HALF = 2144 * 2848 * 2                       # 12,212,224 B
CARVE = 0xC00000                             # 12 MiB, keeps 0x4000 alignment
out['half_frame'] = {'half_bytes': HALF, 'carve_bytes': CARVE,
                     'carve_range': [f'{END - CARVE:#010x}', f'{END:#010x}'],
                     'patched_size_word': f'{SIZE - CARVE:#010x}',
                     'pool_tail_after_carve_MB': {
                         'single_ycc': round((END - CARVE - layout(False)[0xEC]) / 1e6, 2),
                         'double_ycc': round((END - CARVE - layout(True)[0xEC]) / 1e6, 2)}}

# ---- 4. time estimates (field probe, cached-window rates) -----------------
R32, W32 = 75.3e6, 76.1e6                    # B/s
CPY = 4 / 54e-9                              # 4 B per 54 ns pair = 74 MB/s
stride = W * 2


def t_fill(rows):
    return rows * stride / W32


def est(lo, factor=3.0):
    return {'cached_rate_s': round(lo, 3), 'slow_bound_s': round(lo * factor, 3)}


xpan_h = 1584                                 # 4288x1584 = 2.707:1 (0.05 % from 65:24)
out['times'] = {
    'xpan_bars_from_3x2': est(t_fill(Hpx - xpan_h)),
    'xpan_bars_from_16x9': est(t_fill(2416 - xpan_h)),
    'half_shot1_copy_plus_sum': est(HALF / CPY * 1.25),
    'half_shot2_verify_plus_two_copies': est(HALF / R32 + 2 * HALF / CPY),
    'note': 'slow_bound = 3x, covers an uncached arena alias until the probe measures it',
}
out['xpan_geometry'] = {
    '3x2_band': {'rows': xpan_h, 'top_row': (Hpx - xpan_h) // 2, 'byte_offset': (Hpx - xpan_h) // 2 * stride},
    '16x9_band': {'rows': xpan_h, 'top_row': (2416 - xpan_h) // 2, 'byte_offset': (2416 - xpan_h) // 2 * stride},
    'exact_65x24': {'w': 4160, 'h': 1536, 'col_offset_bytes': 64 * 2},
}
print(json.dumps(out, indent=1))
