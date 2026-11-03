#!/usr/bin/env python3
"""List every seth+or3/add3 address build and every raw 32-bit pointer that lands in a VMA range of official ilaunch3.

Works on machine-code bytes, independent of objdump text. A seth is paired with the nearest earlier seth
to the same register within WINDOW words; hits are candidates to confirm in the disassembly.
"""

import argparse
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
WINDOW = 16


def segments(data):
    rows = [struct.unpack_from(">IIIII", data, 32 + 20 * i) for i in range(16)]
    return [{"index": i, "file": s + 0x200, "vma": v, "size": n} for i, (s, v, n, _, _) in enumerate(rows)]


def to_vma(segs, offset):
    return next((s["vma"] + offset - s["file"] for s in segs if s["file"] <= offset < s["file"] + s["size"]), None)


def address_builds(data, segs, lo, hi):
    hits = []
    for seg in segs:
        words = [data[seg["file"] + i:seg["file"] + i + 4] for i in range(0, seg["size"] - 3, 4)]
        for i, w in enumerate(words):
            if w[0] & 0xF0 != 0x80 or w[1] & 0xF0 not in (0xE0, 0xA0):
                continue
            src, imm = w[1] & 0x0F, struct.unpack(">H", w[2:])[0]
            for j in range(i - 1, max(i - WINDOW, -1), -1):
                s = words[j]
                if s[0] == 0xD0 | src and s[1] == 0xC0:
                    top = struct.unpack(">H", s[2:])[0] << 16
                    addr = top | imm if w[1] & 0xF0 == 0xE0 else (top + imm - (0x10000 if imm & 0x8000 else 0)) & 0xFFFFFFFF
                    if lo <= addr < hi:
                        hits.append({"at": f"0x{seg['vma'] + 4 * i:08X}", "seth_at": f"0x{seg['vma'] + 4 * j:08X}",
                                     "op": "or3" if w[1] & 0xF0 == 0xE0 else "add3", "reg": f"r{src}", "target": f"0x{addr:08X}"})
                    break
    return hits


def raw_pointers(data, segs, lo, hi):
    hits = []
    for offset in range(0, len(data) - 3):
        value = struct.unpack_from(">I", data, offset)[0]
        if lo <= value < hi:
            vma = to_vma(segs, offset)
            hits.append({"file_offset": f"0x{offset:X}", "vma": f"0x{vma:08X}" if vma is not None else None,
                         "aligned": offset % 4 == 0, "target": f"0x{value:08X}"})
    return hits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lo", type=lambda x: int(x, 0))
    parser.add_argument("hi", type=lambda x: int(x, 0))
    parser.add_argument("--firmware", type=Path, default=ROOT / "artifacts/firmware/gxr-1.51/ilaunch3")
    args = parser.parse_args()
    data = args.firmware.read_bytes()
    segs = segments(data)
    print(json.dumps({"range": [f"0x{args.lo:08X}", f"0x{args.hi:08X}"],
                      "address_builds": address_builds(data, segs, args.lo, args.hi),
                      "raw_pointers": raw_pointers(data, segs, args.lo, args.hi)}, indent=1))


if __name__ == "__main__":
    main()
