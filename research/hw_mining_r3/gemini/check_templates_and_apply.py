#!/usr/bin/env python3
"""
Fast extraction of:
1. Default T template in all 6 units and MCR bytes at T+0x25B3..0x25BF.
2. Frontend normal apply function in all 6 units (verifying F+18 -> F+20 skip of F+1C).
3. All references to seth #0xf031 across all 6 units + body (both *3 and *0).
4. All calls to type dispatcher / range writers in all 6 units, checking if any pass type=11 outside MCR apply_wrapper/read_helper.
"""
import json
import re
import struct
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_units import (
    OUT, ZIP_PATH, UNITS, parse_sections_main, parse_sections_boot,
    file_off_to_vma, vma_to_file_off, read_vma, disasm_window, sha256
)


def find_template_copy(data: bytes, sections, t_ptr_vma: int):
    t_hi = (t_ptr_vma >> 16) & 0xFFFF
    t_lo = t_ptr_vma & 0xFFFF
    for s in sections:
        if s["size"] < 40:
            continue
        start = s["file_offset"]
        end = start + s["size"]
        for m in re.finditer(b"\x96\xf0\x40\x00", data[start:end]):
            foff = start + m.start()
            # Check window [foff - 32 : foff + 16]
            win_start = max(start, foff - 32)
            win = data[win_start:min(end, foff + 16)]
            # Find seth r5, #hi and or3 r5, r5, #lo in win
            r5_hi = None
            r5_lo = None
            for i in range(0, len(win) - 3, 2):
                if win[i] == 0xD5 and win[i + 1] == 0xC0:
                    r5_hi = struct.unpack_from(">H", win, i + 2)[0]
                elif win[i] == 0x85 and win[i + 1] == 0xE5 and r5_hi is not None:
                    r5_lo = struct.unpack_from(">H", win, i + 2)[0]
            if r5_hi is not None and r5_lo is not None:
                tmpl_vma = (r5_hi << 16) | r5_lo
                tmpl_foff = vma_to_file_off(sections, tmpl_vma, 0x4000)
                if tmpl_foff is not None:
                    fn_start_foff = foff - 0x20
                    fn_start_vma = file_off_to_vma(sections, fn_start_foff)
                    return {
                        "copy_fn_vma": f"0x{fn_start_vma:08X}",
                        "copy_fn_file_offset": f"0x{fn_start_foff:08X}",
                        "ldi_4000_vma": f"0x{file_off_to_vma(sections, foff):08X}",
                        "template_vma": f"0x{tmpl_vma:08X}",
                        "template_file_offset": f"0x{tmpl_foff:08X}",
                    }
    return None


def find_frontend_normal_apply(data: bytes, sections):
    """
    In jlaunch3, normal frontend apply (2010C474) loads slots from r9 (F=0x20383E98):
    ld r4, @(0, r9)  -> a4 c9 00 00 ( wait: 24 c9 = ld r4, @r9 )
    ld r4, @(4, r9)  -> a4 c9 00 04
    ld r4, @(8, r9)  -> a4 c9 00 08
    ld r4, @(12, r9) -> a4 c9 00 0c
    ld r4, @(16, r9) -> a4 c9 00 10
    ld r4, @(20, r9) -> a4 c9 00 14
    ld r4, @(24, r9) -> a4 c9 00 18
    ld r4, @(32, r9) -> a4 c9 00 20 (skips 0x1c!)
    Let's search for a4 c9 00 18 followed within 48 bytes by a4 c9 00 20!
    """
    hits = []
    for s in sections:
        start = s["file_offset"]
        end = start + s["size"]
        for m in re.finditer(b"\xa4\xc9\x00\x18", data[start:end]):
            foff = start + m.start()
            win = data[foff:min(end, foff + 64)]
            if b"\xa4\xc9\x00\x20" in win:
                vma_18 = file_off_to_vma(sections, foff)
                off_20 = foff + win.index(b"\xa4\xc9\x00\x20")
                vma_20 = file_off_to_vma(sections, off_20)
                # Also extract the function called for F+18 (seth r0, #hi; or3 r0, r0, #lo right before a4 c9 00 18)
                vk_hi = struct.unpack_from(">H", data, foff - 6)[0]
                vk_lo = struct.unpack_from(">H", data, foff - 2)[0]
                vk_vma = (vk_hi << 16) | vk_lo
                vk_foff = vma_to_file_off(sections, vk_vma, 4)
                vk_bytes = data[vk_foff:vk_foff + 4].hex() if vk_foff else None
                hits.append({
                    "ld_f18_vma": f"0x{vma_18:08X}",
                    "ld_f18_file_offset": f"0x{foff:08X}",
                    "ld_f20_vma": f"0x{vma_20:08X}",
                    "ld_f20_file_offset": f"0x{off_20:08X}",
                    "f18_callee_vma": f"0x{vk_vma:08X}",
                    "f18_callee_file_offset": f"0x{vk_foff:08X}" if vk_foff else None,
                    "f18_callee_bytes_hex": vk_bytes,
                })
    return hits


def find_f031_refs(data: bytes, sections):
    """Find all seth rX, #0xf031 or raw 32-bit 0xF03180xx in image."""
    seth_hits = []
    for s in sections:
        start = s["file_offset"]
        end = start + s["size"]
        for foff in range(start, end - 3, 2):
            if (data[foff] & 0xF0) == 0xD0 and data[foff + 1] == 0xC0 and data[foff + 2] == 0xF0 and data[foff + 3] == 0x31:
                reg = data[foff] & 0x0F
                vma = file_off_to_vma(sections, foff)
                # Look ahead 16 bytes for or3/add3/ld/st
                context = data[foff:min(end, foff + 24)].hex()
                seth_hits.append({
                    "vma": f"0x{vma:08X}",
                    "file_offset": f"0x{foff:08X}",
                    "reg": reg,
                    "context_hex": context,
                })
    raw_8000_hits = []
    for addr in [0xF0318000, 0xF0318004, 0xF0318008, 0xF031800C]:
        b = struct.pack(">I", addr)
        for m in re.finditer(re.escape(b), data):
            foff = m.start()
            vma = file_off_to_vma(sections, foff)
            raw_8000_hits.append({
                "register": f"0x{addr:08X}",
                "file_offset": f"0x{foff:08X}",
                "vma": f"0x{vma:08X}" if vma else None,
            })
    return {"seth_f031": seth_hits, "raw_f031800x": raw_8000_hits}


def main():
    zf = zipfile.ZipFile(ZIP_PATH, "r")
    detail = json.loads((OUT / "evidence/mcr_cross_unit_detail.json").read_text())

    out_data = {}
    for unit in UNITS:
        main_data = zf.read(f"GXR Update/Firmware rel 1.51/{unit}3")
        sections = parse_sections_main(main_data)
        boot_data = zf.read(f"GXR Update/Firmware rel 1.51/{unit}0")
        boot_sections = parse_sections_boot(boot_data)

        u_info = {
            "f031_main": find_f031_refs(main_data, sections),
            "f031_boot": find_f031_refs(boot_data, boot_sections),
        }

        if detail[unit]["mcr_blocks"]:
            blk = detail[unit]["mcr_blocks"][0]
            t_ptr_vma = int(blk["t_ptr_vma"], 16)
            tmpl = find_template_copy(main_data, sections, t_ptr_vma)
            if tmpl:
                t_vma = int(tmpl["template_vma"], 16)
                mcr_bytes = read_vma(main_data, sections, t_vma + 0x25B3, 13)
                tmpl["mcr_t_25b3_25bf_hex"] = mcr_bytes.hex()
                tmpl["mcr_t_25b3_u8"] = mcr_bytes[0]
                tmpl["mcr_t_25b4_25be_u16"] = list(struct.unpack(">6H", mcr_bytes[1:13]))
                # Also check 0x25B0..0x25C1
                tmpl["mcr_t_25b0_25c1_hex"] = read_vma(main_data, sections, t_vma + 0x25B0, 18).hex()
                # Disassemble template copy function
                cf_vma = int(tmpl["copy_fn_vma"], 16)
                disasm_window(
                    main_data, sections, cf_vma & ~3, (cf_vma + 0x40) & ~3,
                    OUT / f"evidence/disasm/{unit}3_t_template_copy_{cf_vma:08x}"
                )
            u_info["default_t_template"] = tmpl

            apply_hits = find_frontend_normal_apply(main_data, sections)
            u_info["frontend_normal_apply"] = apply_hits
            for ah in apply_hits:
                v18 = int(ah["ld_f18_vma"], 16)
                disasm_window(
                    main_data, sections, (v18 - 0x130) & ~3, (v18 + 0x90) & ~3,
                    OUT / f"evidence/disasm/{unit}3_frontend_apply_{v18:08x}"
                )

        out_data[unit] = u_info

    (OUT / "evidence/templates_and_apply.json").write_text(
        json.dumps(out_data, indent=2) + "\n", encoding="utf-8"
    )
    for u, inf in out_data.items():
        print(f"=== {u} ===")
        print("  default_t_template:", inf.get("default_t_template"))
        print("  frontend_normal_apply:", inf.get("frontend_normal_apply"))
        print("  f031_main seth count:", len(inf["f031_main"]["seth_f031"]), "raw_f031800x:", inf["f031_main"]["raw_f031800x"])
        print("  f031_boot seth count:", len(inf["f031_boot"]["seth_f031"]), "raw_f031800x:", inf["f031_boot"]["raw_f031800x"])


if __name__ == "__main__":
    main()
