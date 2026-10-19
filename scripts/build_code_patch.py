#!/usr/bin/env python3
"""Build an experimental, equal-length GXR code patch with an official recovery tree."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / "artifacts/stage1a-probe/packages"
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"
OBJCOPY = ROOT / "research/tooling_m32r_asm/prefix/bin/m32r-elf-objcopy"
_module_spec = importlib.util.spec_from_file_location("gxr_drill", ROOT / "scripts/build_drill.py")
drill = importlib.util.module_from_spec(_module_spec)
_module_spec.loader.exec_module(drill)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(isinstance(value, (int, str)) and not isinstance(value, bool), "Expected an integer or hex string")
    return int(value, 0) if isinstance(value, str) else value


def sha(data):
    return hashlib.sha256(data).hexdigest()


def input_path(value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def asset(record):
    path = input_path(record["path"])
    data = path.read_bytes()
    require(sha(data) == record["sha256"], f"Asset hash mismatch: {path}")
    return path, data


def parse_container(data, csv_path):
    require(len(data) >= 512 and drill.be32(data, 0x164) == len(data) - 512
            and drill.be32(data, 0x168) == len(data), "Container lengths do not match")
    require(drill.checksum_phase(data) == 0, "Only official ilaunch3 checksum phase 0 is accepted")
    rows = []
    for i in range(16):
        src, va, size, bss, bss_size = struct.unpack_from(">5I", data, 0x20 + i * 20)
        require(size > 0 and src + 512 + size <= len(data), "Invalid initialized file range")
        require(va + size <= 1 << 32 and bss + bss_size <= 1 << 32, "Container address overflow")
        rows.append({"index": i, "source": src, "start": src + 512, "end": src + 512 + size,
                     "load": va, "size": size, "bss": bss, "bss_size": bss_size})
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            require(not (a["start"] < b["end"] and b["start"] < a["end"]), "Overlapping file segments")
            require(not (a["load"] < b["load"] + b["size"] and b["load"] < a["load"] + a["size"]), "Overlapping VA segments")
            if a["bss_size"] and b["bss_size"]:
                require(not (a["bss"] < b["bss"] + b["bss_size"] and b["bss"] < a["bss"] + a["bss_size"]), "Overlapping BSS segments")
        for b in rows:
            if b["bss_size"]:
                require(not (a["load"] < b["bss"] + b["bss_size"] and b["bss"] < a["load"] + a["size"]), "Initialized VA overlaps BSS")
    with open(csv_path, newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    require(len(csv_rows) == 16, "CSV must describe exactly 16 segments")
    fields = {"index": "index", "source_payload_offset": "source", "file_offset": "start",
              "load_address": "load", "initialized_size": "size", "bss_address": "bss", "bss_size": "bss_size"}
    for c, r in zip(csv_rows, rows):
        require(all(int(c[k]) == r[v] for k, v in fields.items()), "CSV and official header disagree")
    return rows


def mapped(va, length, segments):
    require(length > 0 and 0 <= va < va + length <= 1 << 32, "Invalid VA range")
    rows = [s for s in segments if s["load"] <= va and va + length <= s["load"] + s["size"]]
    require(len(rows) == 1, "VA must map uniquely inside one initialized segment")
    return rows[0]["start"] + va - rows[0]["load"], rows[0]["index"]


def parse_elf(data, *, inplace=False):
    require(len(data) >= 52 and data[:7] == b"\x7fELF\x01\x02\x01", "ELF32/MSB/version 1 required")
    header = struct.unpack_from(">HHIIIIIHHHHHH", data, 16)
    typ, machine, version, entry, phoff, shoff, flags, ehsize, phsize, phnum, shsize, shnum, shstr = header
    require((typ, machine, version, ehsize, shsize) == (2, 88, 1, 52, 40), "Final ELF32/MSB/M32R executable required")
    require(shnum > 0 and shstr < shnum and shoff >= 52 and shoff + 40 * shnum <= len(data), "Invalid ELF section table")
    require(phnum > 0 and phsize == 32 and phoff >= 52 and phoff + phsize * phnum <= len(data), "Invalid ELF program headers")
    require(flags & ~0xF == 0, "Unsupported ELF machine flags")
    sections = []
    for i in range(shnum):
        fields = struct.unpack_from(">10I", data, shoff + 40 * i)
        name, kind, attrs, va, off, size, link, info, align, entsize = fields
        require(kind != 8 and off + size <= len(data), "NOBITS or out-of-file section rejected")
        require(not attrs & (1 | 0x400), "Writable or TLS section rejected")
        require(kind not in (4, 9), "Remaining ELF relocation section rejected")
        require(align == 0 or align & (align - 1) == 0, "Invalid section alignment")
        sections.append({"index": i, "name_offset": name, "kind": kind, "flags": attrs, "va": va,
                         "offset": off, "size": size, "link": link, "info": info, "align": align, "entsize": entsize})
    strings = sections[shstr]
    require(strings["kind"] == 3, "Section-name string table missing")
    names = data[strings["offset"]:strings["offset"] + strings["size"]]
    def string(table, offset):
        require(offset < len(table) and b"\0" in table[offset:], "Invalid ELF string")
        return table[offset:table.index(0, offset)].decode("ascii")
    for s in sections:
        s["name"] = string(names, s["name_offset"])
    allowed = ({"", ".text.alt", ".text.normal", ".symtab", ".strtab", ".shstrtab"}
               if inplace else {"", ".text", ".rodata", ".symtab", ".strtab", ".shstrtab"})
    require(all(s["name"] in allowed for s in sections), "Unexpected/orphan ELF section")
    require(len({s["name"] for s in sections}) == len(sections), "Duplicate ELF section names")
    allocated = sorted((s for s in sections if s["flags"] & 2), key=lambda s: s["va"])
    if inplace:
        require([(s["name"], s["va"], s["size"], s["kind"], s["flags"]) for s in allocated]
                == [(".text.alt", 0x203183E8, 212, 1, 6), (".text.normal", 0x20319C00, 212, 1, 6)],
                "In-place ELF must contain exactly the two original 212-byte code slots")
    else:
        require(allocated and allocated[0]["name"] == ".text", "Allocated code missing")
        require(all(s["kind"] == 1 and s["size"] > 0 and s["name"] in (".text", ".rodata") for s in allocated), "Unexpected loaded section")
        require(allocated[0]["flags"] == 6 and all(s["flags"] == 2 for s in allocated[1:]), "Code/constant section flags differ")
    start, end = allocated[0]["va"], max(s["va"] + s["size"] for s in allocated)
    require(start % 4 == 0 and start < end <= 1 << 32 and end - start <= 8340, "Invalid ELF payload range")
    payload = bytearray(b"\xff" * (end - start))
    ranges = []
    for s in allocated:
        lo, hi = s["va"], s["va"] + s["size"]
        require(not any(lo < b and a < hi for a, b in ranges), "Overlapping allocated sections")
        ranges.append((lo, hi))
        payload[lo - start:hi - start] = data[s["offset"]:s["offset"] + s["size"]]
    symbols = {}
    symtabs = [s for s in sections if s["kind"] == 2]
    require(len(symtabs) == 1, "One final ELF symbol table required")
    syms = symtabs[0]
    require(syms["entsize"] == 16 and syms["size"] % 16 == 0 and syms["link"] < len(sections), "Invalid symbol table")
    strsec = sections[syms["link"]]
    require(strsec["kind"] == 3, "Symbol-name string table missing")
    strdata = data[strsec["offset"]:strsec["offset"] + strsec["size"]]
    for offset in range(0, syms["size"], 16):
        n, value, size, info, other, index = struct.unpack_from(">IIIBBH", data, syms["offset"] + offset)
        if offset == 0:
            require((n, value, size, info, other, index) == (0, 0, 0, 0, 0, 0), "Invalid null symbol")
            continue
        require(index != 0, "Undefined ELF symbol rejected")
        require(index != 0xFFF2, "COMMON ELF symbol rejected")
        require(index == 0xFFF1 or index < len(sections), "Invalid ELF symbol section")
        if n:
            name = string(strdata, n)
            require(name not in symbols, "Duplicate named ELF symbol")
            symbols[name] = {"value": value, "size": size, "index": index, "type": info & 15}
    loads = []
    for i in range(phnum):
        kind, off, va, pa, fsize, msize, attrs, alignment = struct.unpack_from(">8I", data, phoff + i * 32)
        require(kind == 1 and attrs == 5 and fsize == msize > 0, "Unexpected/writable ELF program segment")
        require(off + fsize <= len(data) and va == pa and va >= start and va + msize <= end, "Program segment is outside payload")
        require(data[off:off + fsize] == bytes(payload[va - start:va - start + fsize]), "Program bytes disagree with sections")
        loads.append((va, va + msize))
    require(all(any(a <= s["va"] and s["va"] + s["size"] <= b for a, b in loads) for s in allocated), "Orphan allocated section")
    if inplace:
        require(loads == [(s["va"], s["va"] + s["size"]) for s in allocated],
                "In-place ELF must load each exact producer slot once")
    return {"entry": entry, "start": start, "end": end, "payload": bytes(payload), "sections": sections,
            "allocated": allocated, "symbols": symbols, "flags": flags}


def sign(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def branch_delta(pc, target, bits, short=False):
    require(0 <= pc <= 0xFFFFFFFF and 0 <= target <= 0xFFFFFFFF and target % 4 == 0, "Branch target must be aligned and 32-bit")
    base = pc & ~3 if short else pc
    require(short or pc % 4 == 0, "Long branch PC must be aligned")
    delta = target - base
    require(delta % 4 == 0 and -(1 << (bits - 1)) * 4 <= delta <= ((1 << (bits - 1)) - 1) * 4,
            f"Branch BL{bits} distance out of range: PC=0x{pc:X}, target=0x{target:X}, delta={delta}")
    return delta // 4


def encode_bl24(pc, target):
    delta = branch_delta(pc, target, 24)
    return bytes([0xFE]) + (delta & 0xFFFFFF).to_bytes(3, "big")


def decode_branch(raw, pc, kind):
    if kind in ("BL24", "BRA24"):
        require(len(raw) >= 4 and raw[0] == {"BL24": 0xFE, "BRA24": 0xFF}[kind], "Wrong long branch opcode")
        target = pc + sign(int.from_bytes(raw[1:4], "big"), 24) * 4
        branch_delta(pc, target, 24)
    elif kind in ("BL8", "BRA8", "BC8", "BNC8"):
        opcode = {"BL8": 0x7E, "BRA8": 0x7F, "BC8": 0x7C, "BNC8": 0x7D}[kind]
        require(len(raw) >= 2 and raw[0] & 0x7F == opcode, "Wrong short branch opcode")
        target = (pc & ~3) + sign(raw[1], 8) * 4
        branch_delta(pc, target, 8, True)
    elif kind == "BNE16":
        require(len(raw) >= 4 and raw[0] & 0xF0 == 0xB0 and raw[1] & 0xF0 == 0x10, "Wrong conditional branch opcode")
        target = pc + sign(int.from_bytes(raw[2:4], "big"), 16) * 4
        branch_delta(pc, target, 16)
    else:
        raise ValueError("Unsupported branch assertion kind")
    return target


def disassemble(raw, va):
    # Temporary files contain firmware data only; subprocess is the known objdump.
    with tempfile.TemporaryDirectory(prefix="gxr-code-patch-") as temp:
        path = Path(temp) / "bytes.bin"
        path.write_bytes(raw)
        cmd = [str(OBJDUMP), "-D", "-b", "binary", "-m", "m32r", "-EB",
               "--disassemble-zeroes", f"--adjust-vma=0x{va:x}", str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return re.sub(r"/[^\n]*bytes\.bin", "<bytes.bin>", result.stdout)


def audit_branches(elf, assertions, disassembly):
    asserted, observed = {}, {}
    for a in assertions:
        pc = number(a["va"])
        require(pc not in asserted, "Duplicate branch assertion")
        target = elf["symbols"][a["target_symbol"]]["value"]
        require(elf["start"] <= pc < elf["end"], "Branch assertion outside payload")
        width = 2 if a["kind"].endswith("8") else 4
        raw = elf["payload"][pc - elf["start"]:pc - elf["start"] + width]
        require(decode_branch(raw, pc, a["kind"]) == target, "Final payload branch target mismatch")
        asserted[pc] = target
    for line in disassembly.splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} ?)+)\s+(.+)$", line)
        if not m:
            continue
        pc = int(m[1], 16)
        for i, part in enumerate(re.split(r" -> | \|\| ", m[3])):
            b = re.search(r"\b(?:bl|bra|bc|bnc|bne|beqz|bnez|beq|bltz|bgez|bgtz|blez|bcl|bncl)\b.*?0x([0-9a-f]+)", part)
            if b:
                observed[pc + 2 * i] = int(b[1], 16)
    require(observed == asserted, "Disassembled branches and assertion list disagree")
    return [{"pc": f"0x{p:08X}", "target": f"0x{v:08X}", "final_bytes_verified": True} for p, v in sorted(asserted.items())]


def build(files, spec, csv_path):
    drill.check_official(files)
    require(spec["mode"] == "experimental", "Candidate is approved for an experiment only")
    original = files["ilaunch3"]
    segments = parse_container(original, csv_path)
    approval_path, approval_bytes = asset(spec["approval"])
    approval = json.loads(approval_bytes)
    require(approval["mode"] == "experimental" and approval["official_ilaunch3_sha256"] == sha(original), "Wrong approval scope")
    require(len(approval["code_ranges"]) == 1, "One audited code range required")
    audit_path, audit_bytes = asset(approval["static_audit"])
    audit = json.loads(audit_bytes)
    require(audit["decision"].startswith("experimental candidate retained") and audit["runtime_verified"] is False,
            "Static audit does not qualify this experiment")
    elf_path, elf_bytes = asset(spec["elf"])
    payload_path, payload = asset(spec["payload"])
    map_path, map_bytes = asset(spec["map"])
    elf = parse_elf(elf_bytes)
    require(payload == elf["payload"], "Payload differs from final ELF loaded sections")
    with tempfile.TemporaryDirectory(prefix="gxr-elf-export-") as temp:
        exported = Path(temp) / "payload.bin"
        subprocess.run([str(OBJCOPY), "-O", "binary", "--gap-fill=0xff", str(elf_path), str(exported)],
                       capture_output=True, check=True)
        require(exported.read_bytes() == payload, "Objcopy export differs from payload")
    name = spec["entry_symbol"]
    require(name in elf["symbols"], "Entry symbol missing")
    entry = elf["symbols"][name]
    require(entry["type"] == 2 and entry["value"] == elf["entry"] == elf["start"] and entry["value"] % 4 == 0,
            "Entry must be an aligned function at the first code byte")
    require(0 < entry["size"] <= elf["allocated"][0]["size"], "Entry function size invalid")
    code = elf["allocated"][0]
    mapping_text = map_bytes.decode("utf-8")
    for s in elf["allocated"]:
        require(re.search(rf"^{re.escape(s['name'])}\s+0x0*{s['va']:x}\s+0x0*{s['size']:x}\b", mapping_text, re.M), "Map section address/size differs from ELF")
    require(re.search(rf"0x0*{entry['value']:x}\s+{re.escape(name)}\s*$", mapping_text, re.M), "Map entry differs from ELF")
    approved = []
    for r in approval["code_ranges"]:
        start, end, off = number(r["va_start"]), number(r["va_end"]), number(r["file_start"])
        mapped_off, segment = mapped(start, end - start, segments)
        require(mapped_off == off and off + end - start == number(r["file_end"]), "Approved VA/file range mapping differs")
        require(sha(original[off:off + end - start]) == r["original_sha256"], "Approved original bytes hash differs")
        approved.append((start, end))
    require(any(a <= elf["start"] and elf["end"] <= b for a, b in approved), "Payload uses unapproved range")
    require([number(approval["code_ranges"][0]["va_start"]), number(approval["code_ranges"][0]["va_end"])] == audit["candidate_va"], "Approval and candidate audit disagree")
    require(approval["code_ranges"][0]["original_sha256"] == audit["original_sha256"], "Approval and audit byte hash disagree")
    offset, segment = mapped(elf["start"], len(payload), segments)
    expected = original[offset:offset + len(payload)]
    require(set(expected) == {255}, "Probe must replace verified FF bytes only")
    require(spec["abi"] == "ricoh-leaf-vararg-tail-r4-stack", "An explicit verified Ricoh ABI entry is required")
    require(elf["end"] == number(approval["code_ranges"][0]["va_end"]), "Probe must touch the end of the candidate so every other byte is checked")
    payload_asm = disassemble(payload[:code["size"]], elf["start"])
    branches = audit_branches(elf, spec["branch_assertions"], payload_asm)
    patches = [{"file": "ilaunch3", "name": "candidate-probe-code-and-constants", "offset": f"0x{offset:X}",
                "expected": expected.hex(), "replacement": payload.hex()}]
    hook_evidence = []
    require(spec["hooks"] and len(spec["hooks"]) == len(approval["hooks"]), "All approved playback hooks are required")
    seen = set()
    for hook in spec["hooks"]:
        pc = number(hook["va"])
        require(pc not in seen, "Duplicate hook")
        seen.add(pc)
        policies = [a for a in approval["hooks"] if number(a["va"]) == pc]
        require(len(policies) == 1, "Hook uses unapproved range")
        policy = policies[0]
        require(hook["kind"] == "JL_NOP_TO_BL24" and policy["instruction_length"] == 4, "Unsupported hook form")
        hook_off, _ = mapped(pc, 4, segments)
        before = bytes.fromhex(policy["expected"])
        require(before == b"\x1e\xc0\xf0\x00" and original[hook_off:hook_off + 4] == before, "Hook original bytes mismatch")
        require(hook_off == number(policy["file_offset"]), "Hook file mapping differs")
        context_va = number(policy["context_va"])
        context = bytes.fromhex(policy["context_expected"])
        context_off, _ = mapped(context_va, len(context), segments)
        require(context_va + len(context) == pc and original[context_off:context_off + len(context)] == context,
                "Hook argument preparation original bytes mismatch")
        # Both contexts encode r0=stock formatter, and r4=the same output buffer.
        require(context[-16:] == bytes.fromhex("d4 c0 20 23 d0 c0 20 0b 84 e4 4b d0 80 e0 bc 7c"), "Hook target/argument preparation is not the reviewed formatter path")
        require(number(policy["original_target"]) == 0x200BBC7C and number(policy["return_va"]) == pc + 4,
                "Original target or return position differs")
        require(original[hook_off + 4:hook_off + 8] == bytes.fromhex(policy["return_expected"]) == bytes.fromhex("4f 08 f0 00"), "Caller vararg-stack cleanup differs")
        target = elf["symbols"][hook["target_symbol"]]["value"]
        replacement = encode_bl24(pc, target)
        require(target == elf["entry"], "Hook must target the approved ABI entry")
        require(decode_branch(replacement, pc, "BL24") == target, "Encoded hook target mismatch")
        asm = disassemble(replacement, pc)
        require(re.search(rf"\bbl 0x{target:x}\b", asm), "Objdump hook target differs")
        patches.append({"file": "ilaunch3", "name": hook["name"], "offset": f"0x{hook_off:X}",
                        "expected": before.hex(), "replacement": replacement.hex()})
        hook_evidence.append({**policy, "target": f"0x{target:08X}", "replacement": replacement.hex(" "),
                              "delta_bytes": target - pc, "disassembly": asm, "preserves_argument_preparation": True,
                              "return_va_verified": True})
    patched, records = drill.apply_patches(original, patches, segments)
    output, phase = drill.finish(original, patched)
    require(phase == 0 and len(output) == len(original), "Checksum phase/length changed")
    require(output[:0x16C] == original[:0x16C] and output[0x170:0x200] == original[0x170:0x200], "Container header changed outside checksum")
    require(parse_container(output, csv_path) == segments, "Patched container layout changed")
    outputs = dict(files)
    outputs["ilaunch3"] = output
    report = [{"file": "ilaunch3", "checksum_phase": phase,
               "checksum_before": f"0x{drill.be32(original, 0x16C):08X}",
               "checksum_after": f"0x{drill.be32(output, 0x16C):08X}",
               "sha256_before": sha(original), "sha256_after": sha(output), "patches": records}]
    manifest = {"schema": "gxr-code-patch-v1", "name": spec["name"], "mode": "experimental",
                "base": "Ricoh GXR + A12 50mm, official 1.51, 29 files",
                "official_archive_sha256": drill.ARCHIVE_SHA256,
                "modified_files": ["ilaunch3"], "edits": report,
                "code": {"elf_sha256": sha(elf_bytes), "payload_sha256": sha(payload), "map_sha256": sha(map_bytes),
                         "entry_symbol": name, "entry_va": f"0x{elf['entry']:08X}", "va_end": f"0x{elf['end']:08X}",
                         "bytes": len(payload), "abi": spec["abi"], "stack_frame_bytes": 0,
                         "memory_owner": "no persistent RAM; caller vararg format word only",
                         "registers_modified": ["r0", "r1", "r2", "r3"], "tail_target": "0x200BBC7C",
                         "disassembly": payload_asm, "branches": branches},
                "hooks": hook_evidence,
                "qualification": {"static_bytes_verified": True, "final_elf_verified": True,
                                  "final_branch_bytes_verified": True, "camera_execution_verified": False,
                                  "runtime_region_persistence_verified": False, "official_recovery_on_camera_verified": False},
                "assets": {"approval": {"path": str(approval_path.relative_to(ROOT)), "sha256": sha(approval_bytes)},
                           "static_audit": {"path": str(audit_path.relative_to(ROOT)), "sha256": sha(audit_bytes)},
                           "elf": {"path": str(elf_path), "sha256": sha(elf_bytes)},
                           "payload": {"path": str(payload_path), "sha256": sha(payload)},
                           "map": {"path": str(map_path), "sha256": sha(map_bytes)}},
                "tool_sha256": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in (OBJDUMP, OBJCOPY, Path(__file__), ROOT / "scripts/build_drill.py")},
                "probe_sha256": {n: sha(d) for n, d in sorted(outputs.items())},
                "recovery_sha256": dict(sorted(drill.OFFICIAL.items())),
                "ilaunch3_replacement_bytes": sum(p["end"] - p["start"] for p in records),
                "ilaunch3_payload_changed_bytes": sum(p["changed_bytes"] for p in records),
                "ilaunch3_total_changed_bytes": sum(a != b for a, b in zip(original, output)),
                "limitations": audit["limitations"]}
    return outputs, report, manifest


def write_package(destination, files, outputs, report, manifest):
    destination = Path(destination).resolve()
    require(destination.is_relative_to(PACKAGES.resolve()) and destination != PACKAGES.resolve(),
            "Output must be a new project artifacts/stage1a-probe/packages directory; SD/Volumes writes forbidden")
    require(not destination.exists(), "Refusing to overwrite an existing package")
    destination.parent.mkdir(parents=True, exist_ok=True)
    probe = destination / "probe" / "SD_ROOT"
    recovery = destination / "recovery-official-1.51" / "SD_ROOT"
    drill.write_tree(probe, outputs)
    drill.write_tree(recovery, files)
    drill.check_written(probe, recovery, files, report)
    for root, hashes in ((probe, manifest["probe_sha256"]), (recovery, manifest["recovery_sha256"])):
        expected = "".join(f"{hashes[n]}  {n}\n" for n in sorted(hashes))
        require((root.parent / "SHA256SUMS").read_text() == expected, "Written checksum inventory differs")
        require(all(sha((root / n).read_bytes()) == hashes[n] for n in hashes), "Written file SHA-256 differs")
    manifest["written_and_reverified"] = True
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    require(json.loads(manifest_path.read_text()) == manifest, "Manifest readback differs")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--firmware", type=Path, default=ROOT / "artifacts/firmware/gxr-1.51")
    parser.add_argument("--sections", type=Path, default=ROOT / "research/firmware/ilaunch3-sections.csv")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        spec_bytes = args.spec.read_bytes()
        spec = json.loads(spec_bytes)
        files = drill.load_official(args.firmware)
        outputs, report, manifest = build(files, spec, args.sections)
        manifest["spec_sha256"] = sha(spec_bytes)
        destination = write_package(args.output, files, outputs, report, manifest) if args.output else None
        print(json.dumps({"name": manifest["name"], "mode": manifest["mode"], "output": str(destination) if destination else None,
                          "ilaunch3_sha256": manifest["probe_sha256"]["ilaunch3"],
                          "payload_bytes": manifest["code"]["bytes"], "changed_bytes": manifest["ilaunch3_total_changed_bytes"],
                          "qualification": manifest["qualification"]}, ensure_ascii=False))
    except (ValueError, KeyError, OSError, UnicodeError, struct.error, subprocess.CalledProcessError) as error:
        parser.exit(2, f"REJECTED: {error}\n")


if __name__ == "__main__":
    main()
