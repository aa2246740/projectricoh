#!/usr/bin/env python3
"""Refine syntactic candidates; absence of a match is not dead-code proof."""
import bisect
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "evidence"


def main():
    container = json.loads((OUT / "container.json").read_text())
    ranges = container["uniform_runs"]
    refs = json.loads((OUT / "address-candidates.json").read_text())
    inputs = {n: (ROOT / "artifacts/firmware/gxr-1.51" / n).read_bytes() for n in ("ilaunch3", "ilaunch0")}
    literal_targets = set()
    for data in inputs.values():
        for offset in range(0x200, len(data) - 3):
            if data[offset] in (0x20, 0x05):
                literal_targets.add(struct.unpack_from(">I", data, offset)[0])
    targets = sorted(set(x["target"] for x in refs if x["kind"] != "direct-branch-linear-disassembly") | literal_targets)
    lines = (OUT / "body-seg01.disasm.txt").read_text().splitlines()
    rows = []
    for n, text in enumerate(lines, 1):
        m = re.match(r"^([0-9a-f]+):\s+((?:[0-9a-f]{2} ?)+)\s+(.+)$", text)
        if m and int(m[1], 16) < 0x200c0d00:
            rows.append((int(m[1], 16), n, m[3]))
    results = []
    for i, row in enumerate(rows):
        if "push" not in row[2] or i == 0 or "jmp lr" not in rows[i - 1][2]:
            continue
        for j in range(i + 1, min(i + 550, len(rows))):
            if "jmp lr" not in rows[j][2]:
                continue
            start, end = row[0], rows[j][0] + 4
            if end - start < 128:
                break
            idx = bisect.bisect_left(targets, start)
            if idx < len(targets) and targets[idx] < end:
                break
            incoming = [x for x in refs if start <= x["target"] < end and not start <= x["site"] < end]
            if incoming:
                break
            branches = [int(x, 16) for r in rows[i:j+1] for x in re.findall(
                r"\b(?:bra|bc|bnc|beqz|bnez|bltz|bgez|beq|bne)\s+(?:[^, ]+,)*0x([0-9a-f]+)", r[2])]
            if any(not start <= x < end for x in branches):
                break
            sec = container["sections"][1]
            results.append({"start": start, "end": end, "span": end - start,
                            "file_start": sec["file_start"] + start - sec["load"], "segment": 1,
                            "start_line": row[1], "end_line": rows[j][1],
                            "first": row[2], "last": rows[j][2], "inbound_syntactic": 0,
                            "byte_pattern_hits": 0, "evidence": "bounded negative sweep; reachable status unknown"})
            break
    results.sort(key=lambda x: -x["span"])
    (OUT / "orphan-functions.json").write_text(json.dumps(results, indent=2) + "\n")
    summary = []
    for candidate in json.loads((OUT / "uniform-xrefs.json").read_text()):
        filtered = [x for x in candidate["instruction_refs"] if not any(r["load"] <= x["site"] < r["load_end"] for r in ranges)]
        # Retain raw totals so no caller can silently turn filtering into proof.
        summary.append({**{k: v for k, v in candidate.items() if k not in ("instruction_refs", "literal_refs")},
                        "raw_instruction_match_count": len(candidate["instruction_refs"]),
                        "outside_uniform_instruction_matches": filtered,
                        "be32_untyped_count": len(candidate["literal_refs"]),
                        "aligned_be32_untyped_count": sum(x["aligned4"] for x in candidate["literal_refs"]),
                        "be32_examples": candidate["literal_refs"][:6]})
    (OUT / "candidate-assessment.json").write_text(json.dumps(summary, indent=2) + "\n")
    windows = {
        "loader-body-bootstrap": (0x2004b89c, 0x2004baf8),
        "loader-body-main": (0x20088358, 0x200885a4),
        "loader-monitor": (0x27e36980, 0x27e36bd0),
        "checksum-validation": (0x20087ca4, 0x20087d10),
        "header-field-names": (0x2008b524, 0x2008b67c),
        "bss-and-initialized-clear": (0x20055040, 0x200550a4),
        "debug-stack": (0x204020e0, 0x20402184),
        "heap": (0x2005bf00, 0x2005c108),
        "heap-wrappers": (0x200bbd98, 0x200bbf4c),
        "heap-native-caller": (0x20062850, 0x20062888),
        "file-io-buffer-init": (0x200873cc, 0x20087480),
        "recipe-hook-entry": (0x20289fe0, 0x2028a150),
    }
    windows.update({f"orphan-{x['start']:08x}": (x["start"], x["end"]) for x in results[:5]})
    indexes = []
    for file in sorted(OUT.glob("body-seg*.disasm.txt")) + [OUT / "monitor.disasm.txt"]:
        text = file.read_text().splitlines()
        for name, (start, end) in windows.items():
            selected = []
            for n, line in enumerate(text, 1):
                m = re.match(r"^\s*([0-9a-f]+):", line)
                if m and start <= int(m[1], 16) < end:
                    selected.append((n, int(m[1], 16), line.strip()))
            if selected:
                (OUT / (name + ".txt")).write_text("\n".join(x[2] for x in selected) + "\n")
                indexes.append({"name": name, "start": start, "end": end,
                                "disassembly": str(file.relative_to(ROOT)),
                                "original_start_line": selected[0][0], "original_end_line": selected[-1][0],
                                "snippet": f"research/stage1_codespace/evidence/{name}.txt"})
    (OUT / "windows.json").write_text(json.dumps(indexes, indent=2) + "\n")
    print(json.dumps({"orphan_shaped_functions": len(results), "windows": len(indexes)}))


if __name__ == "__main__":
    main()
