#!/usr/bin/env python3
"""
Part 7: Final verification checks:
1. jlaunch3 0x20114D00..0x20115450 (0x20114DF4 MCM mode/WB table selector and index 0 trigger).
2. ilaunch3 MMIO blocks (0xF030, 0xF036, 0xF037, 0xF038, 0xF021, 0xF023, 0xF034, 0xF035).
3. Cross-unit unique C040 / C080 / C100 rows in qlaunch3, l08firm3, l06firm3, klaunch3, nlaunch3.
"""

import json
import struct
import zipfile
from pathlib import Path
import sys

ROOT = Path("/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh")
OUT_DIR = ROOT / "research/hw_mining_r1/gemini"
ZIP_PATH = ROOT / "artifacts/downloads/gxr-151.zip"

sys.path.insert(0, str(OUT_DIR))
from mine_part1_isp_and_modes import M32RImage

with zipfile.ZipFile(ZIP_PATH, "r") as zf:
    jlaunch3 = zf.read("GXR Update/Firmware rel 1.51/jlaunch3")
    ilaunch3 = zf.read("GXR Update/Firmware rel 1.51/ilaunch3")
    qlaunch3 = zf.read("GXR Update/Firmware rel 1.51/qlaunch3")
    l08firm3 = zf.read("GXR Update/Firmware rel 1.51/l08firm3")
    l06firm3 = zf.read("GXR Update/Firmware rel 1.51/l06firm3")
    klaunch3 = zf.read("GXR Update/Firmware rel 1.51/klaunch3")
    nlaunch3 = zf.read("GXR Update/Firmware rel 1.51/nlaunch3")

j3 = M32RImage("jlaunch3", jlaunch3, ROOT / "research/tooling_m32r/sections/jlaunch3-sections.csv")
i3 = M32RImage("ilaunch3", ilaunch3, ROOT / "research/tooling_m32r/sections/ilaunch3-sections.csv")

def save_disasm(img: M32RImage, start_vma: int, end_vma: int, name: str):
    lines = []
    for x in sorted(k for k in img.lines if start_vma <= k < end_vma):
        line, src, no, op = img.lines[x]
        lines.append(f"0x{x:08X} (file 0x{img.offset(x):06X}): {op}")
    out_file = OUT_DIR / "disasm_windows" / name
    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_file.name} ({len(lines)} lines)")

# 1. jlaunch3 0x20114D00..0x20115450
save_disasm(j3, 0x20114D00, 0x20115450, "mcm_selector_20114d00_20115450.txt")

# 2. ilaunch3 MMIO regions (note: in ilaunch3, base is 0x20010000 per sections.csv, so file offset + 0x20010000 = VMA)
save_disasm(i3, 0x200FF380, 0x200FFF00, "ilaunch3_f036_f037_200ff380_200fff00.txt")
save_disasm(i3, 0x20101300, 0x20102100, "ilaunch3_f030_20101300_20102100.txt")
save_disasm(i3, 0x20104D00, 0x20105300, "ilaunch3_f034_f035_20104d00_20105300.txt")
save_disasm(i3, 0x203DA300, 0x203DB700, "ilaunch3_f021_f023_203da300_203db700.txt")

# 3. Compare C100 and C080 across units
def find_c100_and_c080(data: bytes, name: str):
    pat = struct.pack(">hhhBBB", 306, 601, 117, 128, 0, 128)
    pos = data.find(pat)
    res = {"unit": name, "c100_offset": hex(pos) if pos != -1 else None}
    if pos != -1:
        c100_rows = []
        for r in range(12):
            row = data[pos + r*24 : pos + (r+1)*24]
            m = struct.unpack(">hhhhhhhhh", row[:18])
            o = list(row[18:24])
            c100_rows.append({"row": r, "matrix": list(m), "offsets": o})
        res["c100_rows"] = c100_rows
    id_c080 = b"\x40\x00\x00\x40" * 24
    p80 = data.find(id_c080)
    res["c080_offset"] = hex(p80) if p80 != -1 else None
    if p80 != -1:
        c080_rows = []
        for r in range(28):
            row = data[p80 + r*96 : p80 + (r+1)*96]
            sectors = [list(row[s*4:(s+1)*4]) for s in range(24)]
            c080_rows.append({"row": r, "s0": sectors[0], "s1": sectors[1], "s5": sectors[5], "s10": sectors[10]})
        res["c080_sample"] = c080_rows
    return res

cross_units = {}
for uname, ubytes in [
    ("jlaunch3", jlaunch3),
    ("qlaunch3", qlaunch3),
    ("l08firm3", l08firm3),
    ("l06firm3", l06firm3),
    ("klaunch3", klaunch3),
    ("nlaunch3", nlaunch3),
]:
    cross_units[uname] = find_c100_and_c080(ubytes, uname)

(OUT_DIR / "part7_cross_unit_details.json").write_text(json.dumps(cross_units, indent=2), encoding="utf-8")
print("Saved part7_cross_unit_details.json")
