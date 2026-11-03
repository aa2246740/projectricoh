#!/usr/bin/env python3
"""Recheck official bytes and the unresolved v2 guard, without producing firmware."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
LO, HI = 0x2005276C, 0x20054800
FLAG, MODE = 0x200D6118, 0x20412AB8
REG = r"(?:r(?:1[0-4]|[0-9])|sp|lr|fp)"
LINE = re.compile(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} ?)+)\s+(.+)$")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_builder():
    spec = importlib.util.spec_from_file_location("v1_builder", ROOT / "scripts/build_code_patch.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def output_dir(value):
    path = Path(value).resolve()
    if not (path.is_relative_to(ROOT / "research/stage1a_probe_v2") or path.is_relative_to(Path("/private/tmp"))):
        raise ValueError("Evidence output must be a new v2 research or /tmp directory")
    if path.exists():
        raise ValueError("Refusing to overwrite evidence")
    path.mkdir(parents=True)
    return path


def census(inputs, sections):
    """Bounded constants only. Unknown values stay unknown, including loaded RAM."""
    builds, accesses, calls = [], [], []
    words = 0
    byte_lines = 0
    producers = ((0x203183E8, 0x203184BC), (0x20319C00, 0x20319CD4))
    for file, data, mapping in inputs:
        values = {}
        for line_number, line in enumerate(file.read_text().splitlines(), 1):
            match = LINE.match(line)
            if not match:
                continue
            pc = int(match[1], 16)
            raw = bytes.fromhex(match[2])
            offset = mapping(pc, len(raw))
            if data[offset:offset + len(raw)] != raw:
                raise ValueError(f"Disassembly byte mismatch: {file.name}:{line_number}")
            byte_lines += 1
            words += 1
            parallel = values.copy() if " || " in match[3] else None
            for part_index, part in enumerate(re.split(r" -> | \|\| ", match[3])):
                site = pc + part_index * 2
                op = part.split(" ", 1)[0]
                operands = re.findall(r"\b" + REG + r"\b", part)
                dest = operands[0] if operands else None
                old = parallel if parallel is not None else values.copy()
                def val(reg):
                    item = old.get(reg)
                    return item[0] if item is not None and words - item[1] <= 64 else None
                def put(reg, value):
                    if value is None:
                        values.pop(reg, None)
                    else:
                        value &= 0xFFFFFFFF
                        values[reg] = (value, words)
                        if FLAG <= value < FLAG + 4 or MODE <= value < MODE + 4 or any(a <= value < b for a, b in producers):
                            builds.append({"pc": hex(site), "value": hex(value), "operation": part,
                                           "source": file.name, "line": line_number})
                immediate = re.search(r"#(-?0x[0-9a-f]+|-?\d+)", part)
                k = int(immediate[1], 0) if immediate else None
                if op == "seth":
                    put(dest, k << 16)
                elif op == "ldi":
                    put(dest, k)
                elif op == "ld24":
                    put(dest, int(part.split(",")[1], 16))
                elif op in ("mv", "neg") and len(operands) == 2:
                    v = val(operands[1])
                    put(dest, None if v is None else v if op == "mv" else -v)
                elif op in ("or3", "add3", "and3") and len(operands) == 2:
                    v = val(operands[1])
                    put(dest, None if v is None else {"or3": lambda: v | k, "add3": lambda: v + k, "and3": lambda: v & k}[op]())
                elif op in ("addi", "slli", "srli", "srai") and dest:
                    v = val(dest)
                    if v is None:
                        put(dest, None)
                    elif op == "addi":
                        put(dest, v + k)
                    elif op == "slli":
                        put(dest, v << k)
                    elif op == "srli":
                        put(dest, v >> k)
                    else:
                        put(dest, (v - (1 << 32) if v & 0x80000000 else v) >> k)
                elif op in ("add", "sub", "or", "and") and len(operands) == 2:
                    a, b = val(operands[0]), val(operands[1])
                    put(dest, None if a is None or b is None else {"add": lambda: a + b, "sub": lambda: a - b,
                                                               "or": lambda: a | b, "and": lambda: a & b}[op]())
                elif op.startswith(("ld", "st")) and "@" in part:
                    mem = re.search(rf"@\((-?\d+),({REG})\)|@([+]?{REG})([+]?)", part)
                    if mem:
                        base = mem[2] or mem[3].lstrip("+")
                        width = 1 if op in ("ldb", "ldub", "stb") else 2 if op in ("ldh", "lduh", "sth") else 4
                        disp = int(mem[1]) if mem[1] else width if mem[3].startswith("+") else 0
                        v = val(base)
                        if v is not None:
                            address = (v + disp) & 0xFFFFFFFF
                            if any(address < end and address + width > begin for begin, end in ((FLAG, FLAG + 4), (MODE, MODE + 4))):
                                accesses.append({"pc": hex(site), "address": hex(address), "width": width,
                                                 "kind": "write" if op.startswith("st") else "read", "operation": part,
                                                 "source": file.name, "line": line_number})
                        if op.startswith("ld"):
                            put(dest, None)
                        if mem[3] and (mem[3].startswith("+") or mem[4]):
                            put(base, None if v is None else v + width)
                elif op in ("jl", "bl", "jmp"):
                    target = val(dest) if dest else None
                    if op == "bl":
                        branch = re.search(r"0x([0-9a-f]+)", part)
                        target = int(branch[1], 16) if branch else None
                    if target in (0x20068A68, 0x20068A78, 0x20069424, 0x200693FC, 0x2036D4E8, 0x203183E8, 0x20319C00):
                        calls.append({"pc": hex(site), "target": hex(target), "r4": None if val("r4") is None else hex(val("r4")),
                                      "source": file.name, "line": line_number})
                    if op in ("jl", "bl"):
                        for reg in [f"r{i}" for i in range(8)]:
                            values.pop(reg, None)
                    else:
                        values.clear()
                elif op.startswith("b") or op in ("rte", "trap"):
                    values.clear()
                elif op not in ("cmp", "cmpu", "cmpi", "cmpui", "cmpeq", "nop", "push", "mvtc") and dest:
                    values.pop(dest, None)
    return {"verified_disassembly_lines": byte_lines, "linear_words": words, "constructed_values": builds,
            "resolved_accesses": accesses, "resolved_calls": calls,
            "limitations": ["64-word straight-line constant lifetime; values reset at branches",
                            "Parallel halfwords read the same pre-word register values",
                            "Unknown RAM pointers, calculated addresses, aliases, DMA, interrupts and call reachability are not proven"]}


def run(destination):
    legacy = load_builder()
    files = legacy.drill.load_official(ROOT / "artifacts/firmware/gxr-1.51")
    body, monitor = files["ilaunch3"], files["ilaunch0"]
    sections = legacy.parse_container(body, ROOT / "research/firmware/ilaunch3-sections.csv")
    evidence = ROOT / "research/stage1_codespace/evidence"
    def mapped(va, length):
        return legacy.mapped(va, length, sections)[0]
    inputs = [(evidence / f"body-seg{i:02d}.disasm.txt", body, mapped) for i in range(16)]
    inputs.append((evidence / "monitor.disasm.txt", monitor, lambda va, length: va - 0x27DFFE00))
    scan = census(inputs, sections)
    out = output_dir(destination)
    windows = [
        (0x20068A68, 0x20068A84, "flag-setter-getter"),
        (0x2005C788, 0x2005C818, "startup-flag-inputs"),
        (0x2005C1D8, 0x2005C208, "public-init-before-scan"),
        (0x2005C2F8, 0x2005C314, "public-init-calls-startup"),
        (0x2005CE08, 0x2005CF04, "startup-order"),
        (0x2005CB90, 0x2005CBA8, "startup-mode-4"),
        (0x200693FC, 0x200694A0, "mode-setter-getter"),
        (0x2036E34C, 0x2036E558, "update-gates"),
        (0x20089340, 0x20089354, "auto-update-check-wrapper"),
        (0x2008747C, 0x200874E8, "auto-update-descriptor-load"),
        (0x20087A14, 0x20087A40, "auto-update-check"),
        (0x20087868, 0x200878C8, "auto-update-validator"),
        (0x2036F244, 0x2036F260, "other-update-control-entry"),
        (0x20319C00, 0x20319CD4, "producer-normal"),
        (0x203183E8, 0x203184BC, "producer-alt"),
        (0x200BBC7C, 0x200BBCBC, "formatter-entry"),
    ]
    window_records = []
    for lo, hi, name in windows:
        offset = mapped(lo, hi - lo)
        raw = body[offset:offset + hi - lo]
        (out / f"{name}.disasm.txt").write_text(legacy.disassemble(raw, lo))
        window_records.append({"name": name, "va_start": hex(lo), "va_end": hex(hi), "file_offset": hex(offset),
                               "sha256": sha(raw), "objdump_reextracted_from_official": True})
    caller_words = []
    for caller in json.loads((ROOT / "research/stage1a_probe/update-path-isolation.json").read_text())["callers"]:
        pc = int(caller["call_va"], 0)
        offset = mapped(pc, 4)
        assert body[offset + 2:offset + 4] == bytes.fromhex("1e c0")
        caller_words.append({"word_va": hex(pc), "actual_jl_halfword_va": hex(pc + 2),
                             "raw_word": body[offset:offset + 4].hex(" "), "target": caller["producer_va"]})
    normal = body[mapped(0x20319C00, 212):mapped(0x20319C00, 212) + 212]
    alt = body[mapped(0x203183E8, 212):mapped(0x203183E8, 212) + 212]
    differences = [{"relative_offset": hex(i), "normal": f"{a:02x}", "alt": f"{b:02x}"}
                   for i, (a, b) in enumerate(zip(normal, alt)) if a != b]
    assert [int(x["relative_offset"], 0) for x in differences] == [0x53, 0x67, 0x9B, 0xC7]
    callback_records = []
    va = 0x200C0E60
    while True:
        offset = mapped(va, 40)
        row = body[offset:offset + 40]
        if not row[0]:
            break
        callback_records.append({"table_va": hex(va), "name": row[:32].split(b"\0", 1)[0].decode("ascii"),
                                 "init_target": hex(int.from_bytes(row[32:36], "big"))})
        va += 40
    assert len(callback_records) == 41
    flag_offset, flag_segment = legacy.mapped(FLAG, 4, sections)
    assert flag_segment == 1 and body[flag_offset:flag_offset + 4] == b"\0" * 4
    region_offset = mapped(LO, HI - LO)
    assert region_offset == 0x796C and body[region_offset:region_offset + HI - LO] == b"\xff" * (HI - LO)
    assert len([c for c in scan["resolved_calls"] if c["target"] == hex(0x20319C00)]) == 9
    assert len([c for c in scan["resolved_calls"] if c["target"] == hex(0x203183E8)]) == 4
    scan["be32_entry_pointers"] = {hex(target): {name: [hex(m.start()) for m in re.finditer(re.escape(struct.pack(">I", target)), data)]
                                                     for name, data in (("ilaunch3", body), ("ilaunch0", monitor))}
                                    for target in (FLAG, MODE, 0x203183E8, 0x20319C00)}
    results = {
        "schema": "gxr-stage1a-v2-blocking-audit-v1", "decision": "BLOCKED_R2_NO_PROVEN_GUARD",
        "official_files_verified": 29, "official_sha256": {name: sha(data) for name, data in files.items()},
        "flag": {"va": hex(FLAG), "file_offset": hex(flag_offset), "segment": flag_segment,
                 "image_initial_value": 0, "setter": "0x20068A68", "getter": "0x20068A78",
                 "bit0_set_call": "0x2005C800", "cleared_by_setter": False,
                 "set_before_every_possible_hook_in_update_boot_proven": False,
                 "all_alias_or_dma_writes_excluded": False,
                 "normal_boot_bit0_clear": "image initial value and input-15 conditional support it; every runtime path unproven"},
        "candidate_region": {"va": [hex(LO), hex(HI)], "file_range": ["0x796c", "0x9a00"], "bytes": HI - LO,
                             "official_all_ff": True, "modified": False},
        "common_init_callbacks_before_scan": callback_records,
        "verified_caller_words": caller_words,
        "slot_evaluation": {"preferred_method": "COMPACTION", "selected_slot": None,
                            "producer_ranges": [["0x203183E8", "0x203184BC"], ["0x20319C00", "0x20319CD4"]],
                            "producer_lengths": [212, 212], "byte_differences": differences,
                            "compaction_implemented": False, "dead_code_selected": False,
                            "capacity_and_abi_proof_completed": False},
        "windows": window_records, "census": scan,
        "package": None, "package_ilaunch3_sha256": None, "firmware_changed_bytes": 0,
        "camera_or_sd_accessed": False, "camera_execution_verified": False,
        "audit_script_sha256": sha(Path(__file__).read_bytes()),
    }
    for name, data in files.items():
        assert sha((ROOT / "artifacts/firmware/gxr-1.51" / name).read_bytes()) == sha(data)
    results["official_input_hashes_unchanged_after_audit"] = True
    (out / "guard-audit.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"evidence": str(out), "decision": results["decision"], "verified_disassembly_lines": scan["verified_disassembly_lines"],
                      "flag_resolved_accesses": [a for a in scan["resolved_accesses"] if FLAG <= int(a["address"], 0) < FLAG + 4],
                      "common_init_callbacks": len(callback_records), "firmware_changed_bytes": 0}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
