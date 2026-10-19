#!/usr/bin/env python3
"""Strict in-place M32R producer rewrite, reusing the existing code-patch gates."""
import argparse
import sys
sys.dont_write_bytecode = True
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
tempfile.tempdir = str(HERE)
_spec = importlib.util.spec_from_file_location("legacy_code_patch", ROOT / "scripts/build_code_patch.py")
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)
require, number, sha = legacy.require, legacy.number, legacy.sha
SLOTS = ((".text.alt", 0x203183E8, 0x2CD5E8, "producer_alt"),
         (".text.normal", 0x20319C00, 0x2CEE00, "producer_normal"))
KINDS = {"bl": "BL24", "bra": "BRA24", "bc": "BC8", "bnc": "BNC8",
         "blez": "BLEZ16", "beqz": "BEQZ16", "bnez": "BNEZ16"}
LINE = re.compile(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} ?)+)\s+(.+)$")


def observed_branches(assembly):
    result = []
    for line in assembly.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        pc, raw = int(m[1], 16), bytes.fromhex(m[2])
        for index, instruction in enumerate(re.split(r" -> | \|\| ", m[3])):
            if instruction.startswith("jmp"):
                require(instruction == "jmp lr", "Only the saved-lr indirect return is permitted")
            match = re.match(r"(bl|bra|bc|bnc|blez|beqz|bnez)\b.*?0x([0-9a-f]+)", instruction)
            if match:
                site = pc + index * 2
                width = 4 if raw[0] & 0x80 else 2
                kind = KINDS[match[1]]
                if kind in ("BRA24", "BL24") and width == 2:
                    kind = kind.replace("24", "8")
                result.append({"va": f"0x{site:08X}", "kind": kind,
                               "target": f"0x{int(match[2], 16):08X}",
                               "opcode": raw[index * 2:index * 2 + (2 if width == 4 and kind.endswith('16') else 1)].hex()})
    return result


def encode_branch(assertion):
    pc, target, kind = number(assertion["va"]), number(assertion["target"]), assertion["kind"]
    if kind in ("BL24", "BRA24"):
        disp = legacy.branch_delta(pc, target, 24)
        return bytes([0xFE if kind == "BL24" else 0xFF]) + (disp & 0xFFFFFF).to_bytes(3, "big")
    if kind in ("BL8", "BRA8", "BC8", "BNC8"):
        disp = legacy.branch_delta(pc, target, 8, True)
        return bytes([{"BL8": 0x7E, "BRA8": 0x7F, "BC8": 0x7C, "BNC8": 0x7D}[kind], disp & 255])
    require(kind in ("BEQZ16", "BNEZ16", "BLEZ16"), "Unsupported rewrite branch")
    opcode = bytes.fromhex(assertion["opcode"])
    require(len(opcode) == 2 and opcode[0] == 0xB0 and opcode[1] & 0xF0 ==
            {"BEQZ16": 0x80, "BNEZ16": 0x90, "BLEZ16": 0xC0}[kind], "Conditional branch opcode differs")
    disp = legacy.branch_delta(pc, target, 16)
    return opcode + (disp & 0xFFFF).to_bytes(2, "big")


def code_disassembly(elf):
    symbols = elf["symbols"]
    windows = ((0x203183E8, symbols["alt_code_end"]["value"]),
               (0x20319C00, symbols["normal_code_end"]["value"]))
    result = []
    for (name, start, _, _), (lo, hi) in zip(SLOTS, windows):
        require(lo == start and lo < hi <= start + 212 and hi % 4 == 0, "Code extent outside producer slot")
        result.append(legacy.disassemble(elf["payload"][lo - elf["start"]:hi - elf["start"]], lo))
    return windows, "\n".join(result)


def audit_branches(elf, assertions, assembly):
    observed = observed_branches(assembly)
    require(len({number(a["va"]) for a in assertions}) == len(assertions), "Duplicate branch assertion")
    require(observed == assertions, "Objdump branches and specification disagree")
    windows, _ = code_disassembly(elf)
    code_words = {pc for lo, hi in windows for pc in range(lo, hi, 4)}
    external = {0x20062750, 0x200BBC7C, 0x203189B4}
    result = []
    for assertion in assertions:
        pc, target = number(assertion["va"]), number(assertion["target"])
        require(target in code_words | external, "Branch lands in data, padding or outside reviewed code")
        require(not 0x2005276C <= target < 0x20054800, "Branch into candidate region")
        raw = encode_branch(assertion)
        at = pc - elf["start"]
        require(elf["payload"][at:at + len(raw)] == raw, "Independent encoded branch bytes differ")
        # An independent signed decode catches linker-wrapped targets too.
        disp = int.from_bytes(raw[1:] if len(raw) == 2 or assertion["kind"].endswith("24") else raw[2:], "big")
        bits = 8 if len(raw) == 2 else 24 if assertion["kind"].endswith("24") else 16
        decoded = ((pc & ~3) if bits == 8 else pc) + legacy.sign(disp, bits) * 4
        require(decoded == target, "Independent decoded branch target differs")
        result.append({**assertion, "bytes": raw.hex(" "), "independently_encoded_and_decoded": True})
    return result


def build(files, spec, csv_path):
    legacy.drill.check_official(files)
    require(spec["schema"] == "gxr-function-rewrite-spec-v3" and
            spec["patch_kind"] == "inplace-function-rewrite" and spec["mode"] == "experimental",
            "Explicit experimental in-place rewrite specification required")
    require(spec["name"].startswith("stage1a-probe-v3-") and
            re.fullmatch(r"stage1a-probe-v3-[a-z0-9-]+", spec["name"]), "Invalid v3 package name")
    require(spec["update_mode_guard"] is False, "Sentinel v3 has no mode/update guard")
    original = files["ilaunch3"]
    segments = legacy.parse_container(original, csv_path)
    require(original[0x796C:0x9A00] == b"\xff" * 8340, "Official candidate region differs")
    _, approval_bytes = legacy.asset(spec["approval"])
    approval = json.loads(approval_bytes)
    require(approval["patch_kind"] == spec["patch_kind"] and approval["mode"] == "experimental"
            and approval["official_ilaunch3_sha256"] == sha(original), "Approval scope differs")
    require(approval["update_mode_guard"] is False, "Approval contradicts v3 scope")
    require(spec["ranges"] == approval["ranges"] and len(spec["ranges"]) == 2, "Only the two approved producer slots may change")
    elf_path, elf_bytes = legacy.asset(spec["elf"])
    _, payload = legacy.asset(spec["payload"])
    _, map_bytes = legacy.asset(spec["map"])
    for record in spec["sources"].values():
        legacy.asset(record)
    elf = legacy.parse_elf(elf_bytes, inplace=True)
    require(elf["entry"] == elf["symbols"]["producer_normal"]["value"] == 0x20319C00, "Normal entry moved")
    require(elf["symbols"]["producer_alt"]["value"] == 0x203183E8, "Alternate entry moved")
    require(payload == elf["payload"], "Objcopy payload differs from loaded ELF sections")
    with tempfile.TemporaryDirectory(prefix="gxr-v3-export-", dir=HERE) as temp:
        path = Path(temp) / "rewrite.bin"
        subprocess.run([str(legacy.OBJCOPY), "-O", "binary", "--gap-fill=0xff", str(elf_path), str(path)],
                       check=True, capture_output=True)
        require(path.read_bytes() == payload, "Fresh objcopy export differs")
    mapping = map_bytes.decode()
    for section in elf["allocated"]:
        require(re.search(rf"^{re.escape(section['name'])}\s+0x0*{section['va']:x}\s+0x0*{section['size']:x}\b", mapping, re.M),
                "Map section address/size differs")
    for section, (_, va, _, name) in zip(elf["allocated"], SLOTS):
        symbol = elf["symbols"][name]
        require(symbol["type"] == 2 and symbol["index"] == section["index"] and
                symbol["value"] == va and 0 < symbol["size"] <= 212, "Public entry is not an in-slot function")
        require(re.search(rf"0x0*{va:x}\s+{name}\s*$", mapping, re.M), "Map public entry differs")
    _, assembly = code_disassembly(elf)
    branches = audit_branches(elf, spec["branch_assertions"], assembly)
    patches = []
    for (name, va, offset, entry), policy, section in zip(SLOTS, spec["ranges"], elf["allocated"]):
        require((policy["section"], number(policy["va_start"]), number(policy["va_end"]),
                 number(policy["file_start"]), number(policy["file_end"]), policy["entry_symbol"])
                == (name, va, va + 212, offset, offset + 212, entry), "Producer rewrite range moved")
        require(legacy.mapped(va, 212, segments) == (offset, 9), "Producer mapping differs")
        expected = original[offset:offset + 212]
        require(bytes.fromhex(policy["original_bytes"]) == expected and policy["original_sha256"] == sha(expected),
                "Exact original producer bytes differ")
        replacement = payload[va - elf["start"]:va - elf["start"] + 212]
        patches.append({"name": entry, "file": "ilaunch3", "offset": hex(offset),
                        "expected": expected.hex(), "replacement": replacement.hex()})
    strings = {name: elf["symbols"][name]["value"] for name in ("probe_ok_string", "probe_ng_string")}
    for name, text in (("probe_ok_string", b"OK %d\0"), ("probe_ng_string", b"NG %d\0")):
        va = strings[name]
        require(any(start <= va and va + len(text) <= start + 212 for _, start, _, _ in SLOTS), "String outside producer slots")
        require(payload[va - elf["start"]:va - elf["start"] + 6] == text, "Probe format bytes differ")
    require(strings["probe_ng_string"] == strings["probe_ok_string"] + 6, "Probe format selection stride differs")
    patched, records = legacy.drill.apply_patches(original, patches, segments)
    output, phase = legacy.drill.finish(original, patched)
    require(phase == 0 and len(output) == len(original), "Checksum phase or file length changed")
    require(output[0x796C:0x9A00] == original[0x796C:0x9A00], "Candidate region was patched")
    require(output[:0x16C] == original[:0x16C] and output[0x170:0x200] == original[0x170:0x200], "Header changed outside checksum")
    require(legacy.parse_container(output, csv_path) == segments, "Container segment table changed")
    allowed = [(offset, offset + 212) for _, _, offset, _ in SLOTS] + [(0x16C, 0x170)]
    require(all(a == b or any(lo <= i < hi for lo, hi in allowed) for i, (a, b) in enumerate(zip(original, output))),
            "Change outside two functions and header checksum")
    outputs = dict(files, ilaunch3=output)
    report = [{"file": "ilaunch3", "checksum_phase": phase, "checksum_before": hex(legacy.drill.be32(original, 0x16C)),
               "checksum_after": hex(legacy.drill.be32(output, 0x16C)), "sha256_before": sha(original),
               "sha256_after": sha(output), "patches": records}]
    symbols = elf["symbols"]
    producer_bytes = (symbols["producer_alt_end"]["value"] - 0x203183E8 +
                      symbols["producer_normal_end"]["value"] - 0x20319C00 +
                      symbols["producer_display"]["size"])
    probe_windows = [(symbols["probe_entry"]["value"], symbols["alt_code_end"]["value"]),
                     (symbols["probe_loop"]["value"], symbols["normal_code_end"]["value"])]
    probe_bytes = sum(hi - lo for lo, hi in probe_windows)
    offsets = [0, 1, 0x1000, 0x1051, 0x2000, 0x2084, 0x2090, 0x2093]
    table = symbols["probe_sentinel_addresses"]["value"]
    table_end = symbols["probe_sentinel_addresses_end"]["value"]
    require(table % 4 == 0 and table_end - table == 32, "Sentinel table size or alignment differs")
    require(payload[table - elf["start"]:table_end - elf["start"]] ==
            b"".join((0x2005276C + offset).to_bytes(4, "big") for offset in offsets),
            "Exact sentinel addresses differ")
    manifest = {"schema": "gxr-inplace-function-rewrite-package-v3", "name": spec["name"], "mode": "experimental",
        "patch_kind": spec["patch_kind"], "modified_files": ["ilaunch3"], "update_mode_guard": False,
        "official_archive_sha256": legacy.drill.ARCHIVE_SHA256, "edits": report,
        "code": {"producer_bytes": producer_bytes, "freed_bytes": 424 - producer_bytes,
                 "probe_va": [[hex(lo), hex(hi)] for lo, hi in probe_windows], "probe_bytes": probe_bytes,
                 "sentinel_table_va": [hex(table), hex(table_end)], "sentinel_table_bytes": 32,
                 "sentinel_offsets": [hex(offset) for offset in offsets], "maximum_candidate_byte_reads": 8,
                 "clean_result": "OK 8", "bad_result": "NG <first non-FF sentinel index 0..7>",
                 "strings": {name: hex(va) for name, va in strings.items()}, "string_bytes": 12,
                 "remaining_padding_bytes": 424 - producer_bytes - probe_bytes - 12 - 32,
                 "producer_frame_bytes": 16, "maximum_with_varargs_bytes": 24, "probe_stack_bytes": 0,
                 "probe_registers_modified": ["r0", "r1", "r2", "r3"], "probe_condition_bit_modified": False,
                 "branches": branches, "disassembly": assembly},
        "candidate_region": {"va": ["0x2005276C", "0x20054800"], "bytes": 8340, "sentinel_offsets": [hex(offset) for offset in offsets],
                             "maximum_reads_per_valid_invocation": 8,
                             "byte_identical_official_ff": True, "instruction_fetches": 0},
        "qualification": {"final_elf_verified": True, "final_branch_bytes_verified": True,
                          "exhaustive_equivalence_verified": False, "camera_execution_verified": False,
                          "runtime_region_persistence_verified": False, "official_recovery_after_v3_verified": False},
        "probe_sha256": {n: sha(d) for n, d in sorted(outputs.items())},
        "recovery_sha256": dict(sorted(legacy.drill.OFFICIAL.items())),
        "ilaunch3_replacement_bytes": 424,
        "ilaunch3_payload_changed_bytes": sum(r["changed_bytes"] for r in records),
        "ilaunch3_total_changed_bytes": sum(a != b for a, b in zip(original, output)),
        "assets": {key: spec[key] for key in ("approval", "elf", "payload", "map", "sources")},
        "tool_sha256": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in
                        (Path(__file__), ROOT / "scripts/build_code_patch.py", ROOT / "scripts/build_drill.py", legacy.OBJDUMP, legacy.OBJCOPY)},
        "limitations": ["Host subset interpretation and callee models; no camera execution",
                        "Eight sampled bytes do not prove all 8340 bytes, an atomic snapshot or lifetime RAM ownership",
                        "Instruction counts bound CPU work; camera cycles, DMA/cache waits and deadlines remain unmeasured",
                        "Recovery still requires a bootable camera and normal updater"]}
    if "expected_ilaunch3_sha256" in spec:
        require(spec["expected_ilaunch3_sha256"] == sha(output) and
                spec["expected_changed_bytes"] == manifest["ilaunch3_total_changed_bytes"],
                "Expected final artifact hash or changed-byte count differs")
    return outputs, report, manifest


def qualify(manifest, evidence):
    path, data = legacy.asset(evidence)
    result = json.loads(data)
    require(result["schema"] == "gxr-stage1a-v3-producer-equivalence-v1" and result["passed"] == 17048
            and result["primary_cases"] == 7128 and result["changing_iso_cases"] == 1728
            and result["byte_value_cases"] == 8192 and result["divergences"] == 0,
            "Full required sentinel equivalence matrix has not passed")
    require(result["rewritten_ilaunch3_sha256"] == manifest["probe_sha256"]["ilaunch3"] and
            result["official_ilaunch3_sha256"] == legacy.drill.OFFICIAL["ilaunch3"], "Emulated artifact identity differs")
    require(result["interpreter_sha256"] == sha((ROOT / "research/stage1a_probe_v3/replay_equivalence.py").read_bytes()) and
            result["base_interpreter_sha256"] == sha((ROOT / "research/stage1a_probe_v2/replay_guard.py").read_bytes()),
            "Emulator sources changed since evidence")
    require(result["candidate_instruction_fetches"] == result["candidate_writes"] == 0 and result["maximum_sentinel_reads"] == 8
            and result["sentinel_offsets"] == [0, 1, 4096, 4177, 8192, 8324, 8336, 8339],
            "Candidate fetch/write/sentinel proof differs")
    manifest["qualification"]["exhaustive_equivalence_verified"] = True
    manifest["equivalence"] = {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                               "sha256": sha(data), "cases": result["passed"], "divergences": 0,
                               "callee_abstraction": result["callee_abstraction"]}


def write_package(destination, files, outputs, report, manifest):
    require(Path(destination).resolve() == (ROOT / "artifacts/stage1a-probe/packages/stage1a-probe-v3-sentinel").resolve(),
            "Only the assigned new v3 package directory may be written")
    require(manifest["qualification"]["exhaustive_equivalence_verified"], "Equivalence evidence required before packaging")
    require(Path(destination).name == manifest["name"], "Package directory name differs from specification")
    return legacy.write_package(destination, files, outputs, report, manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--firmware", type=Path, default=ROOT / "artifacts/firmware/gxr-1.51")
    parser.add_argument("--sections", type=Path, default=ROOT / "research/firmware/ilaunch3-sections.csv")
    parser.add_argument("--equivalence", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        spec_bytes = args.spec.read_bytes()
        spec = json.loads(spec_bytes)
        files = legacy.drill.load_official(args.firmware)
        outputs, report, manifest = build(files, spec, args.sections)
        manifest["spec_sha256"] = sha(spec_bytes)
        if args.equivalence:
            qualify(manifest, {"path": str(args.equivalence.resolve()), "sha256": sha(args.equivalence.read_bytes())})
        if args.output:
            write_package(args.output, files, outputs, report, manifest)
        print(json.dumps({"ilaunch3_sha256": manifest["probe_sha256"]["ilaunch3"],
                          "changed_bytes": manifest["ilaunch3_total_changed_bytes"], "code": {k: v for k, v in manifest["code"].items() if k not in ("branches", "disassembly")},
                          "branches": len(manifest["code"]["branches"]), "output": str(args.output) if args.output else None}))
    except (ValueError, KeyError, OSError, struct.error, subprocess.CalledProcessError) as error:
        parser.exit(2, f"REJECTED: {error}\n")


if __name__ == "__main__":
    main()
