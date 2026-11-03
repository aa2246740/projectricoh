#!/usr/bin/python3 -I -B
"""Read-only: decode the body OSD draw-type dispatch (ilaunch3 0x201EB968).
type t in [21, 100]: halfword table 0x20224638[t-21], target = 0x201EB9B0 + h.
Each target stub loads a callee with seth/or3; print type -> callee.
Also count, per callee, how many OSD node descriptors are registered by
0x2030F074-style callers is out of scope (see REPORT). stdout only."""
import importlib.util
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hp', ROOT / 'research/hidden_processing/analyze.py')
hp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hp)

data = (hp.FIRM / 'ilaunch3').read_bytes()
secs = hp.sections(data)


def rd(vma, n):
    off = hp.mapped(secs, vma, reverse=True)
    return data[off:off + n]


TABLE, BASE = 0x20224638, 0x201EB9B0
for t in range(21, 101):
    h = struct.unpack('>h', rd(TABLE + 2 * (t - 21), 2))[0]
    tgt = BASE + h
    code = rd(tgt, 32)
    hi = lo = None
    for i in range(0, 32, 4):
        w = code[i:i + 4]
        if w[0] == 0xD0 and w[1] == 0xC0:        # seth r0,#imm
            hi = struct.unpack('>H', w[2:4])[0]
        if w[0] == 0x80 and w[1] == 0xE0:        # or3 r0,r0,#imm
            lo = struct.unpack('>H', w[2:4])[0]
            break
    callee = (hi << 16 | lo) if hi is not None and lo is not None else None
    print(f'type {t:3d}  stub {tgt:#010x}  callee {callee:#010x}' if callee else f'type {t:3d}  stub {tgt:#010x}  callee ?')
