#!/usr/bin/env python3
"""
1. Fix T template copy lookup by requiring reference to t_ptr_vma (e.g. 0x200B2C2C in l06firm3).
2. Filter all seth rX, #0xf031 across all units + body to see which low 16-bit offsets are used (specifically 0x8000..0x8FFF).
3. Find all callers of type dispatcher and range writers/readers in all 6 units + body, and check what type IDs (r4) are passed.
4. Check all references to T+0x25B3..0x25BF (offsets 9651..9663) across all 6 units + body.
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
    file_off_to_vma, vma_to_file_off, read_vma, disasm_window,
    find_seth_or3, find_direct_branches
)


def find_true_t_template_copy(data: bytes, sections, t_ptr_vma: int):
    refs = find_seth_or3(data, sections, t_ptr_vma)
    for r in refs:
        foff = int(r["seth_file_offset"], 16)
        win = data[foff:foff + 40]
        if b"\x96\xf0\x40\x00" in win:
            r5_hi, r5_lo = None, None
            for i in range(0, len(win) - 3, 2):
                if win[i] == 0xD5 and win[i + 1] == 0xC0:
                    r5_hi = struct.unpack_from(">H", win, i + 2)[0]
                elif win[i] == 0x85 and win[i + 1] == 0xE5 and r5_hi is not None:
                    r5_lo = struct.unpack_from(">H", win, i + 2)[0]
            if r5_hi is not None and r5_lo is not None:
                tmpl_vma = (r5_hi << 16) | r5_lo
                tmpl_foff = vma_to_file_off(sections, tmpl_vma, 0x4000)
                fn_start_foff = foff - 4
                fn_start_vma = file_off_to_vma(sections, fn_start_foff)
                return {
                    "copy_fn_vma": f"0x{fn_start_vma:08X}",
                    "copy_fn_file_offset": f"0x{fn_start_foff:08X}",
                    "template_vma": f"0x{tmpl_vma:08X}",
                    "template_file_offset": f"0x{tmpl_foff:08X}",
                }
    return None


def analyze_f031_low_offsets(data: bytes, sections):
    """For every seth rX, #0xf031, look ahead 32 bytes for or3/add3/ld/st using rX and check the low 16-bit value."""
    f0318_hits = []
    subblock_counts = {}
    for s in sections:
        start = s["file_offset"]
        end = start + s["size"]
        for foff in range(start, end - 3, 2):
            if (data[foff] & 0xF0) == 0xD0 and data[foff + 1] == 0xC0 and data[foff + 2] == 0xF0 and data[foff + 3] == 0x31:
                reg = data[foff] & 0x0F
                vma = file_off_to_vma(sections, foff)
                found_lo = []
                for foff2 in range(foff + 4, min(foff + 36, end - 3), 2):
                    c0, c1 = data[foff2], data[foff2 + 1]
                    imm = struct.unpack_from(">H", data, foff2 + 2)[0]
                    # or3 rY, rX, #imm (8Y eX) or add3 rY, rX, #imm (8Y aX) or ld/st @(imm, rX) (aY cX / bY 4X etc.)
                    if ((c0 & 0xF0) == 0x80 and (c1 & 0xF0) in (0xE0, 0xA0) and (c1 & 0x0F) == reg) or \
                       ((c0 & 0xF0) in (0xA0, 0xB0) and (c1 & 0x0F) == reg):
                        found_lo.append((foff2, imm))
                        subblk = f"0xF031{imm & 0xF000:04X}"
                        subblock_counts[subblk] = subblock_counts.get(subblk, 0) + 1
                        if 0x8000 <= imm <= 0x8FFF:
                            f0318_hits.append({
                                "seth_vma": f"0x{vma:08X}",
                                "seth_file_offset": f"0x{foff:08X}",
                                "lo_vma": f"0x{file_off_to_vma(sections, foff2):08X}",
                                "mmio_addr": f"0xF031{imm:04X}",
                            })
                        break
    return {"f0318_hits": f0318_hits, "subblock_counts": subblock_counts}


def find_t_offset_accesses(data: bytes, sections, min_off=0x25B3, max_off=0x25BF):
    """Search entire image for any instruction with immediate 0x25B3..0x25BF."""
    hits = []
    for s in sections:
        start = s["file_offset"]
        end = start + s["size"]
        for foff in range(start, end - 3, 2):
            imm = struct.unpack_from(">H", data, foff + 2)[0]
            if min_off <= imm <= max_off:
                op0, op1 = data[foff], data[foff + 1]
                # Check if foff is 4-byte aligned (32-bit instruction)
                vma = file_off_to_vma(sections, foff)
                if vma % 4 == 0:
                    hits.append({
                        "vma": f"0x{vma:08X}",
                        "file_offset": f"0x{foff:08X}",
                        "insn_hex": data[foff:foff + 4].hex(),
                        "imm_hex": f"0x{imm:04X}",
                    })
    return hits


def find_type11_dispatcher_calls(data: bytes, sections, disp_vma: int):
    """
    Find all references to disp_vma (type dispatcher, 20255600 in jlaunch3)
    and range writers/readers (at disp_vma + 0x140, +0x250, +0x364, +0x478),
    and inspect the r4 value loaded nearby!
    """
    targets = {
        "dispatcher": disp_vma,
        "range_write_1": disp_vma + 0x140,
        "range_write_2": disp_vma + 0x250,
        "range_write_3": disp_vma + 0x364,
        "range_read": disp_vma + 0x478,
    }
    out = {}
    for name, tvma in targets.items():
        refs = find_seth_or3(data, sections, tvma)
        brs = find_direct_branches(data, sections, tvma)
        type11_callers = []
        all_r4_values = []
        for r in refs:
            foff = int(r["seth_file_offset"], 16)
            win = data[max(0, foff - 16):foff + 24]
            # Look for ldi r4, #imm8 (64 XX) or ldi r4, #imm16 (94 f0 XX XX)
            r4_vals = []
            for i in range(0, len(win) - 1, 2):
                if win[i] == 0x64:
                    r4_vals.append(win[i + 1])
                elif i + 3 < len(win) and win[i] == 0x94 and win[i + 1] == 0xF0:
                    r4_vals.append(struct.unpack_from(">h", win, i + 2)[0])
            all_r4_values.append({"seth_vma": r["seth_vma"], "r4_candidates": r4_vals})
            if 11 in r4_vals:
                type11_callers.append({
                    "seth_vma": r["seth_vma"],
                    "seth_file_offset": r["seth_file_offset"],
                    "r4_candidates": r4_vals,
                })
        out[name] = {
            "target_vma": f"0x{tvma:08X}",
            "seth_ref_count": len(refs),
            "branch_ref_count": len(brs),
            "type11_callers": type11_callers,
        }
    return out


def main():
    zf = zipfile.ZipFile(ZIP_PATH, "r")
    detail = json.loads((OUT / "evidence/mcr_cross_unit_detail.json").read_text())
    prev = json.loads((OUT / "evidence/templates_and_apply.json").read_text())

    results = {}
    for unit in UNITS:
        main_data = zf.read(f"GXR Update/Firmware rel 1.51/{unit}3")
        sections = parse_sections_main(main_data)
        boot_data = zf.read(f"GXR Update/Firmware rel 1.51/{unit}0")
        boot_sections = parse_sections_boot(boot_data)

        u_res = {
            "f031_analysis_main": analyze_f031_low_offsets(main_data, sections),
            "f031_analysis_boot": analyze_f031_low_offsets(boot_data, boot_sections),
            "t_25b3_25bf_insn_hits": find_t_offset_accesses(main_data, sections),
        }

        if detail[unit]["mcr_blocks"]:
            blk = detail[unit]["mcr_blocks"][0]
            t_ptr_vma = int(blk["t_ptr_vma"], 16)
            disp_vma = int(blk["dispatcher_vma"], 16)

            tmpl = find_true_t_template_copy(main_data, sections, t_ptr_vma)
            if tmpl:
                t_vma = int(tmpl["template_vma"], 16)
                mcr_bytes = read_vma(main_data, sections, t_vma + 0x25B3, 13)
                tmpl["mcr_t_25b3_25bf_hex"] = mcr_bytes.hex()
                tmpl["mcr_t_25b3_u8"] = mcr_bytes[0]
                tmpl["mcr_t_25b4_25be_u16"] = list(struct.unpack(">6H", mcr_bytes[1:13]))
                tmpl["mcr_t_25b0_25c1_hex"] = read_vma(main_data, sections, t_vma + 0x25B0, 18).hex()
                cf_vma = int(tmpl["copy_fn_vma"], 16)
                disasm_window(
                    main_data, sections, cf_vma & ~3, (cf_vma + 0x40) & ~3,
                    OUT / f"evidence/disasm/{unit}3_t_template_copy_{cf_vma:08x}"
                )
            u_res["default_t_template"] = tmpl
            u_res["dispatcher_analysis"] = find_type11_dispatcher_calls(main_data, sections, disp_vma)

        results[unit] = u_res

    (OUT / "evidence/l06_and_f0318_analysis.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    for u, r in results.items():
        print(f"=== {u} ===")
        print("  default_t_template:", r.get("default_t_template"))
        print("  f0318_hits_main:", r["f031_analysis_main"]["f0318_hits"])
        print("  f031_subblocks_main:", r["f031_analysis_main"]["subblock_counts"])
        print("  t_25b3_25bf_insn_hits count:", len(r["t_25b3_25bf_insn_hits"]), [x["vma"] for x in r["t_25b3_25bf_insn_hits"]])
        if "dispatcher_analysis" in r:
            for k, v in r["dispatcher_analysis"].items():
                print(f"  {k}: refs={v['seth_ref_count']} type11_callers={v['type11_callers']}")


if __name__ == "__main__":
    main()
