#!/usr/bin/env python3
"""
Part 5: Complete disassembly & data extraction for:
1. All remaining ISP types in jlaunch3 (WDR Type 21, RLUT Type 23, EXIP Type 24, AWBIP Type 25,
   INP Type 27, FLT Type 32, GLUT Type 34, GCAL Type 37, Type 38, VK Type 10, SCM Type 14,
   and the radial vignetting/toy-camera block at 0x20384024 / 0x20145998).
2. Complete Scene/Effect Mode table and mode setup continuation (0x2010F400..0x20111000).
3. Body-side (ilaunch3) post-transfer to JPEG hardware pipeline (resizer, format converter,
   JPEG encoder, display LUTs).
4. Other units (klaunch3, nlaunch3, l06firm3, qlaunch3, l08firm3) color tables and ISP blocks.
"""
import json
import struct
import zipfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mine_part1_isp_and_modes import M32RImage

ROOT = Path("/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh")
OUT_DIR = ROOT / "research/hw_mining_r1/gemini"
DISASM_DIR = OUT_DIR / "disasm_windows"
ZIP_PATH = ROOT / "artifacts/downloads/gxr-151.zip"

BASE = 0x2004B000
HDR = 0x200

def vma_to_off(vma: int) -> int:
    return vma - BASE + HDR

def u32(buf: bytes, vma: int) -> int:
    return struct.unpack_from(">I", buf, vma_to_off(vma))[0]

def u16(buf: bytes, vma: int) -> int:
    return struct.unpack_from(">H", buf, vma_to_off(vma))[0]

def find_refs_32(buf: bytes, target_hi: int, target_lo: int, base_vma: int = BASE, hdr: int = HDR):
    hits = []
    for off in range(hdr, len(buf) - 8, 2):
        w = struct.unpack_from(">H", buf, off)[0]
        if (w & 0xF0FF) == 0xD0C0:
            imm16 = struct.unpack_from(">H", buf, off + 2)[0]
            if imm16 == target_hi:
                vma = off - hdr + base_vma
                for off2 in range(off + 4, min(off + 24, len(buf) - 4), 2):
                    imm2 = struct.unpack_from(">H", buf, off2 + 2)[0]
                    if imm2 == target_lo:
                        hits.append(f"0x{vma:08X}")
                        break
    return hits

def main():
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        j_buf = zf.read("GXR Update/Firmware rel 1.51/jlaunch3")
        q_buf = zf.read("GXR Update/Firmware rel 1.51/qlaunch3")
        l08_buf = zf.read("GXR Update/Firmware rel 1.51/l08firm3")
        k_buf = zf.read("GXR Update/Firmware rel 1.51/klaunch3")
        n_buf = zf.read("GXR Update/Firmware rel 1.51/nlaunch3")
        l06_buf = zf.read("GXR Update/Firmware rel 1.51/l06firm3")
        i_buf = zf.read("GXR Update/Firmware rel 1.51/ilaunch3")

    j3 = M32RImage("jlaunch3", j_buf, ROOT / "research/tooling_m32r/sections/jlaunch3-sections.csv")
    t_defaults = json.loads((ROOT / "research/isp_pipeline/parameter_defaults.json").read_text())["bytes"]

    def read_t_bytes(off: int, n: int) -> bytes:
        return bytes(t_defaults.get(f"0x{off + i:04X}", 0) for i in range(n))

    def annotate_window(start_vma: int, end_vma: int) -> str:
        out = []
        for x in sorted(k for k in j3.lines if start_vma <= k < end_vma):
            line, src, no, op = j3.lines[x]
            out.append(f"0x{x:08X} (file 0x{j3.offset(x):06X}): {op}")
        return "\n".join(out)

    windows = {
        "isp_front_and_setup_2010bc00_2010d400": (0x2010BC00, 0x2010D400),
        "mode_setup_end_2010f400_20111000": (0x2010F400, 0x20111000),
        "flt_and_misc_20116000_20118000": (0x20116000, 0x20118000),
        "inp_rlut_wdr_20118800_2011a400": (0x20118800, 0x2011A400),
        "post_cont_2011b200_2011c600": (0x2011B200, 0x2011C600),
    }
    for name, (s, e) in windows.items():
        txt = annotate_window(s, e)
        (DISASM_DIR / f"{name}.txt").write_text(txt + "\n")
        print(f"Wrote {name}.txt ({len(txt.splitlines())} lines)")

    summary = {}
    summary["refs_20384024"] = find_refs_32(j_buf, 0x2038, 0x4024)
    summary["refs_2038400C"] = find_refs_32(j_buf, 0x2038, 0x400C)
    summary["refs_20384030"] = find_refs_32(j_buf, 0x2038, 0x4030)
    summary["refs_20145998"] = find_refs_32(j_buf, 0x2014, 0x5998)
    summary["refs_20143698"] = find_refs_32(j_buf, 0x2014, 0x3698)
    print("Refs to 0x20384024:", summary["refs_20384024"])
    print("Refs to 0x2038400C:", summary["refs_2038400C"])
    print("Refs to 0x20384030:", summary["refs_20384030"])

    print(f"T+6900..6932 (around 6906/6907): {read_t_bytes(6900, 32).hex(' ')}")
    print(f"T+9488..9520 (around 9496..9506 FLT params): {read_t_bytes(9488, 32).hex(' ')}")

    print("\n=== B&W TE Toning Tables in T & ROM ===")
    for name, off_t in [
        ("T+4656 (0x1230)", 4656),
        ("T+4666 (0x123A)", 4666),
        ("T+4676 (0x1244)", 4676),
        ("T+4686 (0x124E)", 4686),
        ("T+4696 (0x1258)", 4696),
    ]:
        tb = read_t_bytes(off_t, 10)
        words = [struct.unpack_from(">H", tb, 2*i)[0] for i in range(5)]
        print(f"  {name}: {[f'0x{w:04x}' for w in words]}")
    rom_te = [u16(j_buf, 0x2012D0B4 + 2*i) for i in range(10)]
    print(f"  ROM 0x2012D0B4..0x2012D0C8: {[f'0x{w:04x}' for w in rom_te]}")

    print("\n=== 5-Color Sector Adjustment Tables in T (T+3840..4656) ===")
    for wb_grp, base_t in [(0, 3840), (1, 4032), (2, 4240), (3, 4448)]:
        raw = read_t_bytes(base_t, 48)
        print(f"  WB grp {wb_grp} (T+{base_t} / 0x{base_t:04X}): {raw[:24].hex(' ')} | {raw[24:48].hex(' ')}")

    print("\n=== ROM 0x2012BE40..0x2012C0F4 ===")
    for addr in range(0x2012BE40, 0x2012C0F4, 32):
        chunk = j_buf[vma_to_off(addr):vma_to_off(addr+32)]
        print(f"  0x{addr:08X}: {chunk.hex(' ')}")

    print("\n=== Multi-Unit Comparison (klaunch3, nlaunch3, l06firm3, qlaunch3, l08firm3) ===")
    unit_info = {}
    for name, buf in [
        ("jlaunch3 (A12 50mm)", j_buf),
        ("qlaunch3 (A12 28mm)", q_buf),
        ("l08firm3 (MOUNT A12)", l08_buf),
        ("l06firm3 (A16 24-85mm)", l06_buf),
        ("klaunch3 (P10 28-300mm)", k_buf),
        ("nlaunch3 (S10 24-72mm)", n_buf),
    ]:
        strs = {}
        for s in [b"CAMREG", b"WDR", b"RLUT", b"EXIP", b"AWBIP", b"MCM", b"FLT", b"GLUT", b"GCAL", b"SCM"]:
            idx = buf.find(s + b"\x00")
            if idx != -1:
                strs[s.decode()] = f"file 0x{idx:06X}"
        f034c = []
        for off in range(0, len(buf) - 4, 2):
            if buf[off:off+4] in (b"\xd5\xc0\xf0\x34", b"\xd0\xc0\xf0\x34"):
                f034c.append(f"0x{off:06X}")
        c100_hits = []
        idx = 0
        while True:
            idx = buf.find(b"\x01\x32\x02\x59\x00\x75", idx)
            if idx == -1:
                break
            c100_hits.append(f"0x{idx:06X}")
            idx += 1
        unit_info[name] = {
            "size": len(buf),
            "isp_strings": strs,
            "f034_seth_count": len(f034c),
            "c100_y_row_offsets": c100_hits[:10],
        }
        print(f"  {name}: size={len(buf)}, strings={strs}, f034_seth={len(f034c)}, c100_hits={c100_hits[:6]}")

    print("\n=== Body (ilaunch3) Hardware MMIO Survey ===")
    mmio_hi_counts = {}
    for off in range(HDR, len(i_buf) - 4, 2):
        w = struct.unpack_from(">H", i_buf, off)[0]
        if (w & 0xF0FF) == 0xD0C0:
            imm16 = struct.unpack_from(">H", i_buf, off + 2)[0]
            if (imm16 & 0xF000) in (0xF000, 0xFF00):
                mmio_hi_counts[f"0x{imm16:04X}"] = mmio_hi_counts.get(f"0x{imm16:04X}", 0) + 1
    print("  ilaunch3 MMIO upper-16-bit pages:", dict(sorted(mmio_hi_counts.items())))

    j_mmio_hi = {}
    for off in range(HDR, len(j_buf) - 4, 2):
        w = struct.unpack_from(">H", j_buf, off)[0]
        if (w & 0xF0FF) == 0xD0C0:
            imm16 = struct.unpack_from(">H", j_buf, off + 2)[0]
            if (imm16 & 0xF000) in (0xF000, 0xFF00):
                j_mmio_hi[f"0x{imm16:04X}"] = j_mmio_hi.get(f"0x{imm16:04X}", 0) + 1
    print("  jlaunch3 MMIO upper-16-bit pages:", dict(sorted(j_mmio_hi.items())))

    summary["unit_info"] = unit_info
    summary["ilaunch3_mmio_pages"] = mmio_hi_counts
    summary["jlaunch3_mmio_pages"] = j_mmio_hi
    (OUT_DIR / "part5_summary.json").write_text(json.dumps(summary, indent=2))
    print("Saved part5_summary.json")

if __name__ == "__main__":
    main()
