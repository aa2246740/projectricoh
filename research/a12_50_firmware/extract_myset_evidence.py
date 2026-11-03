#!/usr/bin/env python3
"""Extract and assert the My Settings facts used by REPORT.md.

The input is GNU M32R disassembly produced by disassemble_regions.py.  This
script never changes a firmware image; it fails if an expected instruction at
an exact virtual address changes.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


LINE = re.compile(r"^([0-9a-f]{8}):\s+(?:[0-9a-f]{2}\s+){2,4}\s*(.*)$")


EXPECTED = {
    # Inclusive checksum loop: process base[index], increment index, continue
    # while end >= index.  Save/load both call it with 0x100 and 0x21f.
    "checksum_load": (0x2011D708, "ldub r2,@r2"),
    "checksum_increment": (0x2011D718, "add3 r1,r5,#1"),
    "checksum_bound": (0x2011D720, "cmp r6,r5 -> bnc 0x2011d704"),
    "save_slot_zero_reject": (0x2011D790, "beqz fp,0x2011da90"),
    "save_slot_upper_bound": (0x2011D794, "cmpui fp,#7"),
    "save_buffer": (0x2011D8D8, "add3 r4,sp,#100"),
    "save_zero_length": (0x2011D8E0, "ldi r6,#1024"),
    "existing_header_read_length": (0x2011D9F0, "ldi r6,#256"),
    "payload_size_header": (0x2011DAC0, "ldi r0,#288"),
    "payload_size_store": (0x2011DAC4, "st r0,@(32,r1)"),
    "save_checksum_start": (0x2011E2CC, "ldi r5,#256"),
    "save_checksum_end": (0x2011E2D0, "ldi r6,#543"),
    "save_checksum_store": (0x2011E2F4, "st r0,@(80,r1)"),
    "save_write_length": (0x2011E2EC, "ldi r6,#1024"),
    "save_write_call": (0x2011E300, "mv r4,r11 -> jl r0"),
    "save_write_exact_check": (0x2011E318, "ldi r0,#1024"),
    "load_slot_zero_reject": (0x2011E394, "beqz r10,0x2011e434"),
    "load_slot_upper_bound": (0x2011E398, "cmpui r10,#7"),
    "load_buffer": (0x2011E450, "add3 r5,sp,#80"),
    "load_read_length": (0x2011E448, "ldi r6,#1024"),
    "load_read_exact_check": (0x2011E460, "ldi r1,#1024"),
    "load_checksum_start": (0x2011E478, "ldi r5,#256"),
    "load_checksum_end": (0x2011E488, "ldi r6,#543"),
    "load_checksum_compare": (0x2011E494, "beq r2,r0,0x2011e4b0"),
    "enumeration_increment": (0x201200F0, "addi r9,#1"),
    "enumeration_upper_bound": (0x201200F8, "cmpi r9,#7"),
}


def parse(path: Path) -> dict[int, dict[str, object]]:
    result: dict[int, dict[str, object]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = LINE.match(line)
        if match:
            result[int(match.group(1), 16)] = {
                "line": line_number,
                "instruction": match.group(2).strip(),
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("disassembly", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    instructions = parse(args.disassembly)
    checks: dict[str, dict[str, object]] = {}
    for name, (address, fragment) in EXPECTED.items():
        actual = instructions.get(address)
        if actual is None or fragment not in str(actual["instruction"]):
            raise SystemExit(
                f"{name}: expected {fragment!r} at 0x{address:08X}, got {actual!r}"
            )
        checks[name] = {
            "virtual_address": f"0x{address:08X}",
            "disassembly_line": actual["line"],
            "instruction": actual["instruction"],
        }

    report = {
        "input": str(args.disassembly),
        "read_only": True,
        "asserted_instruction_count": len(checks),
        "confirmed": {
            "valid_slots": [1, 2, 3, 4, 5, 6],
            "record_bytes": 1024,
            "payload_offset": 256,
            "payload_bytes": 288,
            "checksum_offset": 80,
            "checksum_first_offset": 256,
            "checksum_last_offset_inclusive": 543,
            "save_stack_buffer": "sp+100",
            "load_stack_buffer": "sp+80",
        },
        "checks": checks,
        "limits": [
            "Instruction assertions establish constants and data flow at these addresses only.",
            "They do not assign user-interface meaning to individual payload fields.",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
