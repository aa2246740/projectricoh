#!/usr/bin/env python3
"""Assemble the reviewed leaf probe and generate hash-bound experiment inputs."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "build"
TOOLS = ROOT / "research/tooling_m32r_asm/prefix/bin"
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes())}


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    audit_path = ROOT / "research/stage1a_probe/evidence/static-audit.json"
    audit = json.loads(audit_path.read_text())
    assert audit["decision"].startswith("experimental candidate retained")
    assert audit["constructed_candidate_values"] == audit["resolved_candidate_accesses"] == 0
    assert audit["branch_matches"] == 8 and audit["be32_matches"] == 28
    original = (ROOT / "artifacts/firmware/gxr-1.51/ilaunch3").read_bytes()
    assert sha(original) == audit["inputs"]["ilaunch3"]
    commands = [
        [str(TOOLS / "m32r-elf-as"), "-m32r", "-EB", str(HERE / "probe.S"), "-o", str(OUT / "probe.o")],
        [str(TOOLS / "m32r-elf-ld"), "--no-undefined", "-T", str(HERE / "probe.ld"),
         "-Map=" + str(OUT / "probe.map"), "-o", str(OUT / "probe.elf"), str(OUT / "probe.o")],
        [str(TOOLS / "m32r-elf-objcopy"), "-O", "binary", "--gap-fill=0xff", str(OUT / "probe.elf"), str(OUT / "probe.bin")],
        [str(OBJDUMP), "-d", "-h", "-t", "-r", str(OUT / "probe.elf")],
    ]
    logs = []
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logs.append({"command": cmd, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
    (OUT / "probe.disasm.txt").write_text(logs[-1]["stdout"])
    payload = (OUT / "probe.bin").read_bytes()
    assert len(payload) == 80 and payload[-12:] == b"OK %d\0NG %d\0"
    write(OUT / "build-evidence.json", {"commands": logs,
          "inputs": {p.name: record(p) for p in (HERE / "probe.S", HERE / "probe.ld")},
          "tools": {Path(cmd[0]).name: record(Path(cmd[0])) for cmd in commands}})
    segments = [struct.unpack_from(">5I", original, 0x20 + 20 * i) for i in range(16)]
    def offset(va):
        src, load, size, _, _ = next(s for s in segments if s[1] <= va < s[1] + s[2])
        return src + 512 + va - load
    hooks = []
    for pc, context_va in ((0x20319C7C, 0x20319C5C), (0x20318464, 0x20318444)):
        off = offset(pc)
        hooks.append({"va": f"0x{pc:08X}", "file_offset": f"0x{off:X}", "instruction_length": 4,
                      "expected": original[off:off + 4].hex(" "), "original_target": "0x200BBC7C",
                      "return_va": f"0x{pc + 4:08X}", "return_expected": original[off + 4:off + 8].hex(" "),
                      "context_va": f"0x{context_va:08X}",
                      "context_expected": original[offset(context_va):off].hex(" "),
                      "arguments": {"r4": "0x20234BD0 output buffer", "r5..r7": "unchanged",
                                    "stack+0": "original ISO %d format", "stack+4": "ISO integer"}})
    approval_path = HERE / "approval.json"
    write(approval_path, {"schema": "gxr-code-experiment-approval-v1", "mode": "experimental",
          "authorization": "User requested stage 1a probe in this exact candidate and these two playback formatter paths; no SD/card operation authorized",
          "official_ilaunch3_sha256": sha(original), "static_audit": record(audit_path),
          "code_ranges": [{"va_start": "0x2005276C", "va_end": "0x20054800", "file_start": "0x796C",
                           "file_end": "0x9A00", "original_sha256": sha(original[0x796C:0x9A00])}],
          "hooks": hooks})
    spec_path = HERE / "spec.json"
    write(spec_path, {"schema": "gxr-code-patch-spec-v1", "name": "stage1a-probe-ok-ng",
          "mode": "experimental", "approval": record(approval_path),
          "elf": record(OUT / "probe.elf"), "payload": record(OUT / "probe.bin"), "map": record(OUT / "probe.map"),
          "entry_symbol": "probe_entry", "abi": "ricoh-leaf-vararg-tail-r4-stack",
          "branch_assertions": [
              {"va": "0x200547C8", "kind": "BNE16", "target_symbol": "probe_ng"},
              {"va": "0x200547CE", "kind": "BC8", "target_symbol": "probe_loop"},
              {"va": "0x200547D8", "kind": "BRA8", "target_symbol": "probe_format"}],
          "hooks": [{"name": "playback-ISO-normal", "va": "0x20319C7C", "kind": "JL_NOP_TO_BL24", "target_symbol": "probe_entry"},
                    {"name": "playback-ISO-alternate", "va": "0x20318464", "kind": "JL_NOP_TO_BL24", "target_symbol": "probe_entry"}]})
    print(json.dumps({"payload_bytes": len(payload), "payload_sha256": sha(payload), "spec": str(spec_path.relative_to(ROOT))}))


if __name__ == "__main__":
    main()
