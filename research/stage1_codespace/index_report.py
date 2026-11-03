#!/usr/bin/env python3
"""Map report addresses to official bytes and exact objdump line numbers."""
import csv
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "evidence"


def main():
    addresses = set(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{8})\b", (HERE / "REPORT.md").read_text()))
    sections = json.loads((OUT / "container.json").read_text())["sections"]
    asm_rows = {}
    for file in sorted(OUT.glob("body-seg*.disasm.txt")) + [OUT / "monitor.disasm.txt"]:
        for line_number, text in enumerate(file.read_text().splitlines(), 1):
            m = re.match(r"^\s*([0-9a-f]+):", text)
            if m and int(m[1], 16) in addresses:
                asm_rows[int(m[1], 16)] = (str(file.relative_to(ROOT)), line_number, text.strip())
    rows = []
    for va in sorted(addresses):
        kind, offset, record, image = "unmapped-by-these-two-images", "", "", ""
        if 0x27e00000 <= va < 0x27e8ca28:
            kind, offset, image = "monitor-initialized", hex(0x200 + va - 0x27e00000), "ilaunch0"
        else:
            for s in sections:
                if s["load"] <= va < s["load_end"]:
                    kind, offset, record, image = "body-initialized", hex(s["file_start"] + va - s["load"]), hex(s["record_offset"]), "ilaunch3"
                    break
                if s["bss"] <= va < s["bss_end"]:
                    kind, record, image = "body-BSS-no-file-bytes", hex(s["record_offset"]), "ilaunch3"
                    break
        file, line, text = asm_rows.get(va, ("", "", ""))
        rows.append({"address": f"0x{va:08X}", "image": image, "mapping": kind,
                     "file_offset": offset, "header_record": record, "disassembly": file,
                     "line": line, "raw_disassembly_data_not_execution_proof": text})
    with (OUT / "address-index.tsv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"addresses": len(rows), "mapped_addresses": sum(bool(x["image"]) for x in rows)}))


if __name__ == "__main__":
    main()
