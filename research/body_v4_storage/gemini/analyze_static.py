#!/usr/bin/env python3
"""Static analysis helper for body-v4-storage-r1-gemini.

Uses Image from collect.py, address_candidates.json, and section disassemblies to map:
1. Task 8 state table (0x201427B4) and handlers
2. All callers of message buffer 2 producers (0x20109B58..0x2010A5C4, 0x2010AC50)
3. RAW+JPEG capture -> Task 28 -> Task 8 -> Task 28 completion lifecycle
4. Format, USB, Lens Module, SD card hotplug/init paths
5. File handle quota (0x204C8668 / 0x200B92F4) and close/write buffer behavior
"""

from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import HERE, OUT as LOCAL, ROOT, Image

IROM_ASM_DIR = ROOT / "research" / "irom_storage" / "local"
CANDIDATES_JSON = IROM_ASM_DIR / "address_candidates.json"


def find_callers_in_sections(targets: dict[int, str]) -> dict[str, list[dict[str, str]]]:
    """Scan section00..15.asm.txt for seth+(or3|add3|ld|st) or bl calls to target addresses."""
    results: dict[str, list[dict[str, str]]] = {
        f"0x{addr:08X} ({label})": [] for addr, label in targets.items()
    }
    by_addr: dict[int, str] = dict(targets)

    seth_re = re.compile(r"^\s*([0-9a-f]{8}):.*seth\s+(r\d+|fp),#0x([0-9a-f]+)")
    or3_re = re.compile(r"^\s*([0-9a-f]{8}):.*or3\s+(r\d+|fp),(r\d+|fp),#0x([0-9a-f]+)")
    add3_re = re.compile(r"^\s*([0-9a-f]{8}):.*add3\s+(r\d+|fp),(r\d+|fp),#(-?\d+|0x[0-9a-f]+)")
    mem_re = re.compile(r"^\s*([0-9a-f]{8}):.*\b(ld|ldub|lduh|ldb|ldh|st|stb|sth)\s+(r\d+|fp),@\((-?\d+),([r\d]+|fp)\)")
    bl_re = re.compile(r"^\s*([0-9a-f]{8}):.*\bbl\s+0x([0-9a-f]+)")

    for sec_path in sorted(IROM_ASM_DIR.glob("section*.asm.txt")):
        lines = sec_path.read_text(encoding="utf-8", errors="replace").splitlines()
        recent_seth: dict[str, tuple[int, str]] = {}
        for idx, line in enumerate(lines):
            m_seth = seth_re.match(line)
            if m_seth:
                pc_str, reg, imm_str = m_seth.groups()
                recent_seth[reg] = (int(imm_str, 16), pc_str)
            m_or3 = or3_re.match(line)
            if m_or3:
                pc_str, dst_reg, src_reg, lo_str = m_or3.groups()
                if src_reg in recent_seth:
                    hi_val, _ = recent_seth[src_reg]
                    addr = (hi_val << 16) | int(lo_str, 16)
                    if addr in by_addr:
                        label = by_addr[addr]
                        ctx_start = max(0, idx - 3)
                        ctx_end = min(len(lines), idx + 5)
                        snippet = " | ".join(l.strip() for l in lines[ctx_start:ctx_end])
                        results[f"0x{addr:08X} ({label})"].append(
                            {"section": sec_path.name, "pc": f"0x{pc_str.upper()}", "via": f"seth+or3 {src_reg}", "context": snippet}
                        )
            m_add3 = add3_re.match(line)
            if m_add3:
                pc_str, dst_reg, src_reg, imm_str = m_add3.groups()
                if src_reg in recent_seth:
                    hi_val, _ = recent_seth[src_reg]
                    imm_val = int(imm_str, 0)
                    addr = ((hi_val << 16) + imm_val) & 0xFFFFFFFF
                    if addr in by_addr:
                        label = by_addr[addr]
                        ctx_start = max(0, idx - 3)
                        ctx_end = min(len(lines), idx + 5)
                        snippet = " | ".join(l.strip() for l in lines[ctx_start:ctx_end])
                        results[f"0x{addr:08X} ({label})"].append(
                            {"section": sec_path.name, "pc": f"0x{pc_str.upper()}", "via": f"seth+add3 {src_reg}", "context": snippet}
                        )
            m_mem = mem_re.match(line)
            if m_mem:
                pc_str, op, val_reg, disp_str, base_reg = m_mem.groups()
                if base_reg in recent_seth:
                    hi_val, _ = recent_seth[base_reg]
                    disp_val = int(disp_str, 10)
                    addr = ((hi_val << 16) + disp_val) & 0xFFFFFFFF
                    if addr in by_addr:
                        label = by_addr[addr]
                        ctx_start = max(0, idx - 2)
                        ctx_end = min(len(lines), idx + 4)
                        snippet = " | ".join(l.strip() for l in lines[ctx_start:ctx_end])
                        results[f"0x{addr:08X} ({label})"].append(
                            {"section": sec_path.name, "pc": f"0x{pc_str.upper()}", "via": f"seth+{op}", "context": snippet}
                        )
            m_bl = bl_re.match(line)
            if m_bl:
                pc_str, target_str = m_bl.groups()
                addr = int(target_str, 16)
                if addr in by_addr:
                    label = by_addr[addr]
                    ctx_start = max(0, idx - 2)
                    ctx_end = min(len(lines), idx + 3)
                    snippet = " | ".join(l.strip() for l in lines[ctx_start:ctx_end])
                    results[f"0x{addr:08X} ({label})"].append(
                        {"section": sec_path.name, "pc": f"0x{pc_str.upper()}", "via": "bl", "context": snippet}
                    )
    return results


def main() -> None:
    img = Image()

    # 1. Decode Task 8 state table at 0x201427B4 (11 events x 3 states)
    state_table_base = 0x201427B4
    state_table = []
    for event in range(11):
        row = []
        for state in range(3):
            ptr = struct.unpack(">I", img.raw(state_table_base + 12 * event + 4 * state, 4))[0]
            row.append(f"0x{ptr:08X}")
        state_table.append({"event": event, "handlers": row})

    # 2. Decode 0x1F0A sub-handler jump table at 0x20141428 (9 entries, u16 offset from 0x20111B7C)
    sub_1f0a = []
    for i in range(9):
        off16 = struct.unpack(">H", img.raw(0x20141428 + 2 * i, 2))[0]
        target = 0x20111B7C + off16
        sub_1f0a.append({"op_code_msg16": i + 1, "offset": off16, "target": f"0x{target:08X}"})

    # 3. Find all callers of message buffer 2 producers and key storage functions/variables
    targets = {
        0x20109B58: "submit_1F02_card_state",
        0x20109BB4: "submit_1F03_var1",
        0x20109C44: "submit_1F03_jpeg_main",
        0x20109CDC: "submit_1F03_raw_dng",
        0x20109D88: "submit_1F03_var4",
        0x20109E18: "submit_1F03_8400_a",
        0x20109EB8: "submit_1F03_8400_b",
        0x20109F4C: "submit_1F03_var7",
        0x2010A010: "submit_1F04_mode7",
        0x2010A090: "submit_1F04_mode6",
        0x2010A110: "submit_1F04_mode1",
        0x2010A194: "submit_1F04_mode2_4",
        0x2010A248: "submit_1F08_read",
        0x2010A2CC: "submit_1F09_stream",
        0x2010A340: "submit_1F0A_file_op",
        0x2010A3C4: "submit_1F0B_format",
        0x2010A420: "submit_1F12_fw_copy",
        0x2010A4A0: "abort_1F03_if_match",
        0x2010A50C: "abort_1F08_if_match",
        0x2010A56C: "abort_1F09",
        0x2010A588: "submit_1F11_shutdown",
        0x2010AC50: "send_to_queue_2",
        0x2010D0F4: "set_bit0_41EA_abort",
        0x2010D100: "clear_bit0_41EA",
        0x2010D11C: "pause_task8_bit3_41EA",
        0x2010D138: "resume_task8_bit3_41EA",
        0x2010AD00: "get_20142790_busy",
        0x2015505C: "inc_201BC19C_inflight",
        0x20155068: "get_201BC19C_inflight",
        0x20155074: "dec_201BC19C_inflight",
        0x20156310: "exposure_finish_check",
        0x204F0CC4: "var_queue2_id",
        0x204F41E8: "var_task8_state",
        0x204F41EA: "var_task8_flags",
        0x201BC19C: "var_photo_inflight_count",
        0x201BC560: "var_raw_jpeg_pair_step",
        0x204C8668: "var_fs_open_count_hi",
        0x200B92F4: "var_fs_open_count_lo",
    }
    callers = find_callers_in_sections(targets)

    # Also check address_candidates.json for any missed references
    cands = json.loads(CANDIDATES_JSON.read_text(encoding="utf-8"))
    cand_hits: dict[str, list[dict[str, object]]] = {}
    for c in cands:
        t = c.get("target")
        if t in targets:
            key = f"0x{t:08X} ({targets[t]})"
            cand_hits.setdefault(key, []).append(
                {k: (f"0x{v:08X}" if isinstance(v, int) else v) for k, v in c.items()}
            )

    summary = {
        "task8_state_table_0x201427B4": state_table,
        "event7_1F0A_jump_table_0x20141428": sub_1f0a,
        "callers": callers,
        "candidate_hits": cand_hits,
    }
    out_path = LOCAL / "static_xrefs.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    for k, v in callers.items():
        ch = len(cand_hits.get(k, []))
        print(f"{k}: {len(v)} asm hits, {ch} cand hits")


if __name__ == "__main__":
    main()
