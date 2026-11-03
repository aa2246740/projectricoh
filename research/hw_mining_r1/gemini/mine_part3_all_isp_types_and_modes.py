#!/usr/bin/env python3
"""
Part 3: Decode the complete ISP module name & RAM mirror pointer table from
0x201055E0..0x20106200 and 0x2037FEFC/0x2037FF00 initialization, plus all 39 ISP
writers (0x20255600..0x20257200) and mode setup functions.
"""
import json
import re
import struct
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mine_part1_isp_and_modes import M32RImage

ROOT = Path("/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh")
ZIP_PATH = ROOT / "artifacts/downloads/gxr-151.zip"
OUT_DIR = ROOT / "research/hw_mining_r1/gemini"


def cstr_any(j3: M32RImage, vma: int, max_len: int = 128) -> str:
    raw = j3.read(vma, max_len)
    end = raw.find(b"\x00")
    if end != -1:
        raw = raw[:end]
    return raw.decode("ascii", errors="replace").replace("\n", "\\n").replace("\r", "\\r")


def main():
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        j3_bytes = zf.read("GXR Update/Firmware rel 1.51/jlaunch3")

    j3 = M32RImage("jlaunch3", j3_bytes, ROOT / "research/tooling_m32r/sections/jlaunch3-sections.csv")

    # 1. Dump all null-terminated strings in 0x20129E00..0x2012B200
    vma = 0x20129E00
    debug_strings = []
    while vma < 0x2012A600:
        s = cstr_any(j3, vma, 128)
        debug_strings.append({"vma": hex(vma), "str": s})
        raw = j3.read(vma, 128)
        end = raw.find(b"\x00")
        vma += (end + 1) if end != -1 else 128

    print("=== Debug Strings in 0x20129E00..0x2012A600 ===")
    for ds in debug_strings:
        if ds["str"]:
            print(f"  {ds['vma']}: {ds['str']}")

    # 2. Find all references to 0x2037FEFC, 0x2037FF00, 0x2037FF04, or 0x2037 in jlaunch3
    print("\n=== References to 0x2037FExx / 0x2037FFxx ===")
    for a in sorted(j3.lines):
        _, _, _, op = j3.lines[a]
        if "2037" in op or "fefc" in op or "ff00" in op or "fef8" in op:
            print(f"  0x{a:08X}: {op}")

    # Let's check what is around the init of 0x2037FEFC (or find where 0x20142AB0 / 0x20143004 / 0x2014322C are stored in a table!)
    print("\n=== Search for pointers 0x20142AB0, 0x20143004, 0x20143118, 0x2014322C in jlaunch3 binary ===")
    for target_ptr in [0x20142AB0, 0x20143004, 0x20143118, 0x2014322C, 0x20142F1C, 0x20142F7C]:
        pat = struct.pack(">I", target_ptr)
        off = 0
        while True:
            idx = j3.data.find(pat, off)
            if idx == -1:
                break
            va = j3.vma_of_offset(idx)
            print(f"  ptr 0x{target_ptr:08X} found at file 0x{idx:06X}, VMA {hex(va) if va else '?'}")
            off = idx + 1

    # Also search instructions loading 0x2014 in jlaunch3
    print("\n=== Instructions referencing 0x2014xxxx ===")
    regs = {}
    prev_a = None
    for a in sorted(j3.lines):
        if prev_a is None or a - prev_a > 4:
            regs.clear()
        prev_a = a
        _, _, _, op = j3.lines[a]
        for part in re.split(r"\s*(?:->|\|\|)\s*", op):
            part = part.strip()
            m = re.match(r"seth (r\d+),#0x2014$", part)
            if m:
                regs[m.group(1)] = 0x20140000
                continue
            m = re.match(r"(or3|add3) (r\d+),(r\d+),#(-?0x[0-9a-f]+|-?\d+)$", part)
            if m and regs.get(m.group(3)) == 0x20140000:
                k = int(m.group(4), 0)
                val = (0x20140000 | (k & 0xFFFF)) if m.group(1) == "or3" else (0x20140000 + k)
                print(f"  0x{a:08X}: {m.group(2)} = 0x{val:08X} ({op})")

    # 3. Disassemble 0x20105500..0x20106200 with full string annotations
    out_lines = []
    for a in sorted(k for k in j3.lines if 0x20105500 <= k < 0x20106200):
        _, _, _, op = j3.lines[a]
        note = ""
        m = re.search(r"#0x(9[ef][0-9a-f]{2}|a[0-5][0-9a-f]{2})\b", op)
        if m:
            sva = 0x20120000 | int(m.group(1), 16)
            note = f' ; str="{cstr_any(j3, sva, 80)}"'
        out_lines.append(f"0x{a:08X}: {op}{note}")
    (OUT_DIR / "disasm_windows/isp_debug_dump_full.txt").write_text("\n".join(out_lines) + "\n")
    print(f"\nWrote isp_debug_dump_full.txt ({len(out_lines)} lines)")


if __name__ == "__main__":
    main()
