#!/usr/bin/env python3
"""Assemble in /tmp, retain immutable build assets and the Round 2 specification."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / "research/tooling_m32r_asm/prefix/bin"
spec = importlib.util.spec_from_file_location("rewrite_builder", ROOT / "scripts/build_function_rewrite.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def record(path):
    return {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "sha256": builder.sha(path.read_bytes())}


def assemble(destination, spec_path):
    destination, spec_path = destination.resolve(), spec_path.resolve()
    for path in (destination, spec_path):
        builder.require(path.is_relative_to(HERE) or path.is_relative_to(Path("/private/tmp")),
                        "Build output must stay in v2 firmware or /tmp")
    builder.require(not destination.exists(), "Refusing to overwrite an existing build directory")
    if spec_path.exists():
        builder.require(spec_path == HERE / "spec.json" and
                        json.loads(spec_path.read_text()).get("status") == "BLOCKED_R2_NO_PROVEN_GUARD",
                        "Only the explicitly superseded blocked specification may be replaced")
    files = builder.legacy.drill.load_official(ROOT / "artifacts/firmware/gxr-1.51")
    body = files["ilaunch3"]
    logs = []
    with tempfile.TemporaryDirectory(prefix="gxr-stage1a-v2-asm-", dir="/tmp") as temp:
        work = Path(temp)
        commands = [
            [str(TOOLS / "m32r-elf-as"), "-m32r", "-EB", str(HERE / "rewrite.S"), "-o", str(work / "rewrite.o")],
            [str(TOOLS / "m32r-elf-ld"), "--no-undefined", "-T", str(HERE / "rewrite.ld"),
             "-Map=" + str(work / "rewrite.map"), "-o", str(work / "rewrite.elf"), str(work / "rewrite.o")],
            [str(TOOLS / "m32r-elf-objcopy"), "-O", "binary", "--gap-fill=0xff", str(work / "rewrite.elf"), str(work / "rewrite.bin")],
            [str(builder.legacy.OBJDUMP), "-d", "-h", "-t", "-r", str(work / "rewrite.elf")],
        ]
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            logs.append({"command": [arg.replace(temp, "<scratch>") for arg in command],
                         "returncode": result.returncode, "stdout": result.stdout.replace(temp, "<scratch>"),
                         "stderr": result.stderr.replace(temp, "<scratch>")})
        elf = builder.legacy.parse_elf((work / "rewrite.elf").read_bytes(), inplace=True)
        _, assembly = builder.code_disassembly(elf)
        assertions = builder.observed_branches(assembly)
        builder.audit_branches(elf, assertions, assembly)
        destination.mkdir(parents=True)
        for name in ("rewrite.o", "rewrite.elf", "rewrite.bin"):
            (destination / name).write_bytes((work / name).read_bytes())
        (destination / "rewrite.map").write_text((work / "rewrite.map").read_text().replace(temp, "<scratch>"))
        (destination / "rewrite.disasm.txt").write_text(logs[-1]["stdout"])
        (destination / "code.disasm.txt").write_text(assembly)
    ranges = []
    for section, va, offset, entry in builder.SLOTS:
        original = body[offset:offset + 212]
        ranges.append({"section": section, "entry_symbol": entry, "va_start": hex(va), "va_end": hex(va + 212),
                       "file_start": hex(offset), "file_end": hex(offset + 212), "original_bytes": original.hex(" "),
                       "original_sha256": builder.sha(original)})
    audit = json.loads((ROOT / "research/stage1a_probe_v2/evidence/guard-audit.json").read_text())
    callers = audit["verified_caller_words"]
    segments = builder.legacy.parse_container(body, ROOT / "research/firmware/ilaunch3-sections.csv")
    for caller in callers:
        va = int(caller["word_va"], 0)
        offset = builder.legacy.mapped(va, 4, segments)[0]
        builder.require(body[offset:offset + 4] == bytes.fromhex(caller["raw_word"]), "Official caller bytes differ")
    builder.require(sum(int(c["target"], 0) == 0x20319C00 for c in callers) == 9 and len(callers) == 13,
                    "Expected all 9+4 original callers")
    approval_path = destination / "approval.json"
    write(approval_path, {"schema": "gxr-inplace-rewrite-approval-v2", "mode": "experimental",
        "patch_kind": "inplace-function-rewrite", "update_mode_guard": False,
        "authorization": "Round 2 task authorizes only the two 212-byte producer rewrites. R2 mode/update guard is explicitly dropped. No camera/SD/Volumes operation.",
        "official_ilaunch3_sha256": builder.sha(body), "ranges": ranges,
        "caller_words_preserved": callers, "slot_method": "COMPACTION"})
    sources = {p.name: record(p) for p in (HERE / "rewrite.S", HERE / "rewrite.ld", Path(__file__))}
    write(destination / "build-evidence.json", {"commands": logs, "sources": sources,
          "tools": {Path(command[0]).name: record(Path(command[0])) for command in commands},
          "scratch_policy": "Assembler/object/link scratch under /tmp; deliverables copied after validation"})
    specification = {"schema": "gxr-function-rewrite-spec-v2", "name": "stage1a-probe-v2-compact",
        "status": "EXPERIMENTAL_CANDIDATE_HOST_ACCEPTANCE_REQUIRED", "mode": "experimental",
        "patch_kind": "inplace-function-rewrite", "slot_method": "COMPACTION", "update_mode_guard": False,
        "dropped_requirement": "R2 removed by orchestrator in Round 2; no mode/update guard",
        "ranges": ranges, "approval": record(approval_path), "sources": sources,
        "elf": record(destination / "rewrite.elf"), "payload": record(destination / "rewrite.bin"),
        "map": record(destination / "rewrite.map"), "branch_assertions": assertions,
        "candidate_region": ["0x2005276C", "0x20054800"], "candidate_region_bytes": 8340,
        "candidate_region_must_remain_official_ff": True,
        "official_ilaunch3_sha256": builder.sha(body),
        "package": "artifacts/stage1a-probe/packages/stage1a-probe-v2-compact",
        "equivalence_evidence": "research/stage1a_probe_v2/evidence/equivalence.json",
        "camera_execution_verified": False}
    outputs, _, manifest = builder.build(files, specification, ROOT / "research/firmware/ilaunch3-sections.csv")
    # A scratch image is useful for replay. It is not a second package directory.
    with tempfile.TemporaryDirectory(prefix="gxr-v2-build-check-", dir="/tmp") as scratch:
        (Path(scratch) / "ilaunch3").write_bytes(outputs["ilaunch3"])
    specification["expected_ilaunch3_sha256"] = manifest["probe_sha256"]["ilaunch3"]
    specification["expected_changed_bytes"] = manifest["ilaunch3_total_changed_bytes"]
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    write(spec_path, specification)
    print(json.dumps({"spec": str(spec_path), "ilaunch3_sha256": specification["expected_ilaunch3_sha256"],
                      "changed_bytes": specification["expected_changed_bytes"], "branches": len(assertions),
                      "freed_bytes": manifest["code"]["freed_bytes"], "probe_va": manifest["code"]["probe_va"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "build")
    parser.add_argument("--spec-output", type=Path, default=HERE / "spec.json")
    args = parser.parse_args()
    assemble(args.output, args.spec_output)
