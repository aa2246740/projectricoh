#!/usr/bin/env python3
"""Regenerate this task's static evidence without building or modifying firmware."""
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct

HERE = Path(__file__).resolve().parent
ns = runpy.run_path(str(HERE / "evidence.py"))
ns["preflight"]()
ROOT, LOCAL = ns["ROOT"], ns["LOCAL"]
data = ns["FW"].read_bytes()
secs = ns["sections"](data)

for label, lo, hi in json.loads((HERE / "ranges.json").read_text()):
    ns["dump"](data, secs, label, int(lo, 0), int(hi, 0))

tables = {
    "state56_table": (0x203764C8, 408),
    "global_table_pointer": (0x2037F800, 4),
    "global_event_table": (0x203761C8, 24),
    "raw_keys": (0x20375F98, 144),
    "button_mapping": (0x20375F14, 132),
    "list_control": (0x2022F71C, 32),
    "state_pointer_map": (0x2037F658, 272),
    "type5_descriptor": (0x2022F5A8, 12),
}
for label, (va, length) in tables.items():
    at = ns["offset"](secs, va, length)
    ns["save"](label + ".json", {"va": hex(va), "file_offset": hex(at),
               "length": length, "raw_hex": data[at:at+length].hex(" ")})

for label, base, out in [("state56_table", 0x203764C8, "state56_decoded"),
                          ("global_event_table", 0x203761C8, "global_events_decoded")]:
    raw = bytes.fromhex(json.loads((LOCAL / (label + ".json")).read_text())["raw_hex"])
    rows = []
    for pos in range(0, len(raw), 12):
        event, first, second = struct.unpack_from(">III", raw, pos)
        rows.append({"va": hex(base+pos), "event": event, "event_hex": hex(event),
                     "first": hex(first), "second": hex(second)})
        if event == 0:
            break
    ns["save"](out + ".json", rows)

routes = {r["event"]: r for r in json.loads((LOCAL / "state56_decoded.json").read_text())}
private_assertions = json.loads((LOCAL / "critical_assertions.json").read_text())
expected_routes = {int(k, 0): tuple(v) for k, v in private_assertions["expected_routes"].items()}
for event, targets in expected_routes.items():
    assert tuple(int(routes[event][key], 16) for key in ("first", "second")) == targets

instructions = {}
for path in LOCAL.glob("*.disasm.txt"):
    if path.name.endswith(".fresh.disasm.txt"):
        continue
    for line in path.read_text().splitlines():
        if not re.search(r" \| [0-9a-f]+:", line):
            continue
        ins = line.split(" | ", 1)[1]
        address, rest = ins.split(":", 1)
        instructions[int(address, 16)] = rest.split("\t")[-1].strip()
checks = {int(k, 0): v for k, v in private_assertions["checks"].items()}
for address, expected in checks.items():
    assert instructions[address].split(" || ")[0] == expected, hex(address)
ns["save"]("findings_checks.json", {
    "verified_state56_routes": len(expected_routes), "verified_key_instructions": len(checks),
    "fn2_native_return_2_reinitializes_state": True,
    "native_return_0_continues_receiving": True,
    "all_physical_key_aliases_proven": False,
    "preview_frame_refresh_proven": False,
    "sleep_and_all_my_entries_proven": False,
})

manifest = json.loads((ROOT / "firmware/stage2l_switch/hooks.json").read_text())
hooks = []
for old in manifest["hooks"]:
    hooks.append({
        "id": old["id"], "va": old["va"], "file_offset": old["file_offset"],
        "length": old["length"], "original_bytes": old["original_bytes"],
        "existing_stage2l_bytes": old["new_bytes"], "status": "existing_hook_to_redesign",
        "native_continuations": old.get("continuations", []),
    })

additional = [
    ("panel_event_gate", 0x202B120C, 4, "new_ui_hook_candidate", ["0x202b1210", "0x202b1344"],
     "Replay ldi r0,1 and nop, then resume 202b1210; consumed panel events go to 202b1344."),
    ("ui_part_reset_observer", 0x201C06F4, 4, "new_exit_hook_candidate", ["0x201c06f8"],
     "Replay push r8 and push lr; all original arguments and flags survive. Observe owned view before reset."),
    ("ui_part_hide_observer", 0x201C092C, 4, "optional_exit_hook_candidate", ["0x201c0930"],
     "Replay push r8 and push r9. Act only on an owned panel and the requested hide operation."),
    ("my_recall_notification", 0x2036B6C0, 4, "lifecycle_candidate_not_closed", ["0x2036b6c4"],
     "Replay the displaced entry word; retain all native behavior. Does not cover every MY entry."),
    ("my_active_import_notification", 0x2011F580, 4, "lifecycle_candidate_not_closed", ["0x2011f584"],
     "Replay the displaced entry word; retain all native behavior. Covers this current-settings import only."),
]
for name, va, length, status, continuations, fallback in additional:
    at = ns["offset"](secs, va, length)
    hooks.append({"id": name, "va": hex(va), "file_offset": hex(at), "length": length,
                  "original_bytes": data[at:at+length].hex(), "status": status,
                  "native_continuations": continuations, "default_path": fallback})
ns["save"]("hook_candidates.json", hooks)
lines = ["# Hook 原字节与续接点", "",
         "仅静态候选，不含可安装的新补丁。original 是官方 ilaunch3；existing 是当前 Stage2l 的替换字。", "",
         "| ID | VMA | 文件偏移 | 长度 | 官方原字节 | 现有 Stage2l 字节 | 状态 | 原厂续接 |",
         "|---|---|---|---:|---|---|---|---|"]
for h in hooks:
    lines.append("| " + " | ".join([h["id"], h["va"], h["file_offset"], str(h["length"]),
                 h["original_bytes"], h.get("existing_stage2l_bytes", "无"), h["status"],
                 ", ".join(h["native_continuations"]) or "数据项"]) + " |")
(LOCAL / "HOOKS.md").write_text("\n".join(lines) + "\n")

for label, lo, hi in [("key_remap", 0x20289A9C, 0x20289C30),
                      ("fn2_hook", 0x202BE23C, 0x202BE260),
                      ("event_hook", 0x202B11FC, 0x202B1224),
                      ("list_stack", 0x201C07E0, 0x201C089C)]:
    ns["fresh"](data, secs, label, lo, hi)

inputs = ["artifacts/firmware/gxr-1.51/ilaunch3", "firmware/stage2l_switch/hooks.json",
          "firmware/stage2l_switch/abi.S", "firmware/stage2l_switch/ui.c",
          "firmware/stage2l_switch/platform.c", "firmware/stage2l_switch/deep_isp.c",
          "research/stage1_ui/ADDRESS_BOOK.md", "research/stage1_ui/text-FINDINGS.md",
          "research/stage1_ui/lever-FINDINGS.md", "research/stage1_data/REPORT.md",
          "research/deep_select_fix/REPORT.md", "research/contrast_curve/REPORT.md",
          "research/card_engine/REPORT.md", "research/stage1b_recovery/NATIVE_GATES_UPDATE_TRACE.md",
          "research/phase0_drill/evidence/gxr-manual-extracted.txt"]
ns["save"]("input_hashes.json", [{"path": p, "sha256": hashlib.sha256((ROOT/p).read_bytes()).hexdigest()}
                               for p in inputs])
ns["verify"](data, secs)
