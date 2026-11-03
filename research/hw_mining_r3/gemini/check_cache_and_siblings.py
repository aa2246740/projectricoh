#!/usr/bin/env python3
"""Check:
1. jlaunch3 0x20242900..0x20242B00 (read helpers for V/W) and 0x20060000..0x20060400 (startup / cache control)
2. Callers of 0x20250FD4, 0x20251508, 0x202520A0, 0x2025267C, 0x20252AA8 (both 0xFA and 0xFB bl, and seth/or3 or function tables)
3. ilaunch3 references to 0x2035AEFC (where descriptor 0xF0318000 is located in ilaunch3)
"""
import json
import re
import struct
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_units import (
    OUT, ZIP_PATH, parse_sections_main, vma_to_file_off, file_off_to_vma, read_vma, disasm_window
)


def find_callers(data: bytes, secs, target_vma: int):
    hits = []
    hi16 = (target_vma >> 16) & 0xFFFF
    lo16 = target_vma & 0xFFFF
    for s in secs:
        s_vma = s["vma"]
        s_foff = s["file_offset"]
        s_bytes = data[s_foff:s_foff + s["size"]]
        # 1. bl24 (0xFA / 0xFB)
        for m in re.finditer(b"[\xfa\xfb]", s_bytes):
            off = m.start()
            if off % 4 != 0 or off + 4 > len(s_bytes):
                continue
            w = struct.unpack(">I", s_bytes[off:off+4])[0]
            if (w >> 24) in (0xFA, 0xFB):
                disp24 = w & 0x00FFFFFF
                if disp24 & 0x00800000:
                    disp24 -= 0x01000000
                pc = s_vma + off
                if pc + (disp24 << 2) == target_vma:
                    hits.append({"type": "bl24", "vma": hex(pc)})
        # 2. 32-bit pointer in data/table
        pat_ptr = struct.pack(">I", target_vma)
        for m in re.finditer(re.escape(pat_ptr), s_bytes):
            off = m.start()
            if off % 4 == 0:
                hits.append({"type": "ptr32", "vma": hex(s_vma + off)})
        # 3. seth rX, hi16 followed within 16 bytes by or3/add3 lo16
        pat_seth = re.compile(b"[\xd0-\xdf]\xc0" + re.escape(struct.pack(">H", hi16)), re.DOTALL)
        for m in pat_seth.finditer(s_bytes):
            off = m.start()
            if off % 2 != 0:
                continue
            window = s_bytes[off:off + 20]
            if struct.pack(">H", lo16) in window[4:]:
                hits.append({"type": "seth_or3", "vma": hex(s_vma + off)})
    return hits


def main():
    report = {}
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        j_data = zf.read("GXR Update/Firmware rel 1.51/jlaunch3")
        j_secs = parse_sections_main(j_data)

        # Disassemble 0x20242900..0x20242B00 (V/W helpers) and 0x20060000..0x20060400 (startup/cache)
        disasm_window(j_data, j_secs, 0x20242900, 0x20242B00, OUT / "evidence/disasm/jlaunch3_rpc8_helpers_20242900_20242b00")
        disasm_window(j_data, j_secs, 0x20060000, 0x20060400, OUT / "evidence/disasm/jlaunch3_entry_cache_20060000_20060400")

        targets = {
            "sub_20250fd4": 0x20250FD4,
            "sub_20251508": 0x20251508,
            "sub_202520a0": 0x202520A0,
            "sub_2025267c": 0x2025267C,
            "sub_20252aa8": 0x20252AA8,
        }
        callers = {}
        for name, tvma in targets.items():
            callers[name] = find_callers(j_data, j_secs, tvma)
        report["jlaunch3_pipeline_callers"] = callers

        # Also check ilaunch3 around 0x2035AEFC (MCR descriptor in body firmware)
        i_data = zf.read("GXR Update/Firmware rel 1.51/ilaunch3")
        i_secs = parse_sections_main(i_data)
        # Descriptor for type 11 is at index 11 * 12 = +0x84 from table base -> table base = 0x2035AEFC - 0x84 = 0x2035AE78
        i_table_base = 0x2035AEFC - 11 * 12
        report["ilaunch3_desc_table_base"] = hex(i_table_base)
        report["ilaunch3_desc_table_refs"] = find_callers(i_data, i_secs, i_table_base)
        # Also search for ld24 / seth to 0xF0318003 in ilaunch3
        i_f031_all = []
        for s in i_secs:
            s_vma = s["vma"]
            s_foff = s["file_offset"]
            s_bytes = i_data[s_foff:s_foff + s["size"]]
            for m in re.finditer(b"\xf0\x31", s_bytes):
                off = m.start()
                if off % 2 == 0:
                    i_f031_all.append({"vma": hex(s_vma + off - 2), "bytes": s_bytes[max(0, off-2):off+14].hex()})
        report["ilaunch3_f031_halfword_hits"] = i_f031_all

    (OUT / "evidence" / "cache_and_callers.json").write_text(json.dumps(report, indent=2))
    print("Pipeline callers:", json.dumps(report["jlaunch3_pipeline_callers"], indent=2))
    print("ilaunch3 desc table refs:", report["ilaunch3_desc_table_refs"])
    print("ilaunch3 f031 hits:", len(report["ilaunch3_f031_halfword_hits"]))


if __name__ == "__main__":
    main()
