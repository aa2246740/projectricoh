#!/usr/bin/env python3
"""
Part 4: Disassemble and decode:
- 0x20113800..0x20114D00 (MCM state, C040/C080 blenders, etc.)
- 0x2011564C..0x20116000 (MCM control word 2 / B&W TE toning / C120)
- 0x2010EA00..0x2010F200 (continuation of 0x2010E544 mode setup)
- 0x2011A600..0x2011B200 (0x2011A62C and surrounding ISP functions)
- All T-table values referenced in mode setup and MCM/LUT/EXIP/WDR
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


def main():
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        j3_bytes = zf.read("GXR Update/Firmware rel 1.51/jlaunch3")

    j3 = M32RImage("jlaunch3", j3_bytes, ROOT / "research/tooling_m32r/sections/jlaunch3-sections.csv")
    t_defaults = json.loads((ROOT / "research/isp_pipeline/parameter_defaults.json").read_text())["bytes"]

    def read_t_bytes(off: int, n: int) -> bytes:
        return bytes(t_defaults.get(f"0x{off + i:04X}", 0) for i in range(n))

    def annotate_window(start_vma: int, end_vma: int) -> str:
        out = []
        for x in sorted(k for k in j3.lines if start_vma <= k < end_vma):
            line, src, no, op = j3.lines[x]
            out.append(f"0x{x:08X} (file 0x{j3.offset(x):06X}): {op}")
        return "\n".join(out)

    dis_dir = OUT_DIR / "disasm_windows"
    windows = {
        "mcm_part1_20113800_20114d00": (0x20113800, 0x20114D00),
        "mcm_part3_2011564c_20116000": (0x2011564C, 0x20116000),
        "mode_setup_cont_2010ea00_2010f400": (0x2010EA00, 0x2010F400),
        "isp_post_2011a400_2011b200": (0x2011A400, 0x2011B200),
    }
    for name, (s, e) in windows.items():
        txt = annotate_window(s, e)
        (dis_dir / f"{name}.txt").write_text(txt + "\n")
        print(f"Wrote {name}.txt ({len(txt.splitlines())} lines)")

    # Dump key T-table regions discovered in mode setup & MCM
    t_regions = [
        ("T+0x0472 (1138, WB offset?)", 1138, 16),
        ("T+0x0FE0 (4064..4112, vividness scale table)", 4064, 48),
        ("T+0x124E (4686..4706, B&W TE toning table 1 & 2)", 4686, 20),
        ("T+0x1262 (4706..4764, MCM mode/WB selector table -> 0x20383E68)", 4706, 58),
        ("T+0x129C (4764..4784, 5-color sector bitmasks)", 4764, 20),
        ("T+0x1400 (5120..5292, default C100, C040, C080 in T)", 5120, 172),
        ("T+0x14AC (5292..5316, default C120 nodes & gains in T)", 5292, 24),
        ("T+0x14FC (5372..5380, MCM blend override in T)", 5372, 8),
        ("T+0x1FF0 (8176..8192, WB thresholds for MCM interpolation)", 8176, 16),
        ("T+0x2410 (9232..9256, LUT26 row selectors per contrast/mode)", 9232, 24),
        ("T+0x2440 (9280..9300, LUT26 control & params)", 9280, 20),
        ("T+0x24F0 (9456..9476, ISP debug dump flags)", 9456, 20),
        ("T+0x3080 (12416..12432, LUT26 extra fields +28/+32)", 12416, 16),
        ("T+0x3092 (12434..12570, EXIP Type 24 params)", 12434, 136),
    ]
    print("\n=== Key T-table Regions ===")
    for label, off, length in t_regions:
        b = read_t_bytes(off, length)
        print(f"{label} (T+0x{off:04X}, {length}B): {b.hex(' ')}")

    # Also dump jump tables / data tables in jlaunch3 around 0x2012B2A0..0x2012BF00
    print("\n=== Data tables in 0x2012B2A0..0x2012BF00 ===")
    for addr, name, count, fmt in [
        (0x2012B2A0, "0x2010D800 switch table", 8, ">8h"),
        (0x2012B2B0, "0x2010DC0C switch table", 9, ">9h"),
        (0x2012B2C2, "0x2010DF60 switch table", 9, ">9h"),
        (0x2012B2D4, "0x2010E83C switch table", 9, ">9h"),
        (0x2012B2E6, "0x2010E918 switch table", 9, ">9h"),
        (0x2012BE40, "0x20115660 switch table", 12, ">12h"),
        (0x2012BE58, "0x20115690 switch table", 9, ">9h"),
    ]:
        vals = struct.unpack(fmt, j3.read(addr, count * 2))
        print(f"  {name} @ {hex(addr)}: {vals}")


if __name__ == "__main__":
    main()
