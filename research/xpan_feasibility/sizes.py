#!/usr/bin/python3 -I -B
"""Read-only: survey pixel dimensions (and DNG crop tags) of captured JPEG/DNG files.
Prints one line per distinct (kind, w, h, crop tags, lens-model) with count and an example."""
import collections
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAGS = {0x100: 'W', 0x101: 'H', 0x102: 'BPS', 0x14A: 'SubIFDs', 0xC61F: 'DefaultCropOrigin',
        0xC620: 'DefaultCropSize', 0xC68D: 'ActiveArea', 0x110: 'Model', 0xFE: 'SubfileType'}
TS = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}

def ifd(f, bo, off):
    f.seek(off)
    n = struct.unpack(bo + 'H', f.read(2))[0]
    out = {}
    for _ in range(n):
        tag, typ, cnt, val = struct.unpack(bo + 'HHI4s', f.read(12))
        size = TS.get(typ, 1) * cnt
        if size <= 4:
            raw = val[:size]
        else:
            pos = f.tell()
            f.seek(struct.unpack(bo + 'I', val)[0])
            raw = f.read(size)
            f.seek(pos)
        if typ == 2:
            v = raw.rstrip(b'\0').decode('latin1').strip()
        elif typ in (3, 4, 8, 9):
            c = {3: 'H', 4: 'I', 8: 'h', 9: 'i'}[typ]
            v = struct.unpack(bo + c * cnt, raw)
        else:
            v = raw.hex()
        out[tag] = v
    return out

def dng(path):
    with open(path, 'rb') as f:
        h = f.read(8)
        bo = '>' if h[:2] == b'MM' else '<'
        i0 = ifd(f, bo, struct.unpack(bo + 'I', h[4:8])[0])
        res = {'model': i0.get(0x110)}
        subs = i0.get(0x14A, ())
        best = None
        for s in subs:
            d = ifd(f, bo, s)
            if best is None or d.get(0x100, (0,))[0] > best.get(0x100, (0,))[0]:
                best = d
        if best is None:
            best = i0
        res['wh'] = (best.get(0x100, (0,))[0], best.get(0x101, (0,))[0])
        for t in (0xC61F, 0xC620, 0xC68D):
            if t in best:
                res[TAGS[t]] = best[t]
            if t in i0:
                res['i0_' + TAGS[t]] = i0[t]
        return res

def jpg(path):
    with open(path, 'rb') as f:
        d = f.read(400000)
    i = 2
    while i < len(d) - 9:
        if d[i] != 0xFF:
            i += 1
            continue
        m = d[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack('>HH', d[i + 5:i + 9])
            return {'wh': (w, h)}
        i += 2 + struct.unpack('>H', d[i + 2:i + 4])[0]
    return {}

groups = collections.OrderedDict()
for root in sys.argv[1:]:
    for p in sorted(Path(root).rglob('*')):
        ext = p.suffix.lower()
        if ext not in ('.dng', '.jpg', '.jpeg') or p.name.startswith('._'):
            continue
        try:
            r = dng(p) if ext == '.dng' else jpg(p)
        except Exception as e:  # noqa
            r = {'err': str(e)[:40]}
        key = (ext, repr(sorted(r.items())))
        g = groups.setdefault(key, [0, p])
        g[0] += 1
for (ext, r), (n, p) in groups.items():
    print(n, ext, r, p)
