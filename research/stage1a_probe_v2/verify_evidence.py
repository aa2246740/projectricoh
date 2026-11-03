#!/usr/bin/env python3
"""Verify the blocked handoff and prove that its diagnostic checks reject mutations."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(destination):
    path = destination.resolve()
    if not (path.is_relative_to(HERE) or path.is_relative_to(Path("/private/tmp"))):
        raise ValueError("Output must be under v2 research or /tmp")
    if path.exists():
        raise ValueError("Refusing to overwrite verification evidence")
    audit_module = load("audit_v2", HERE / "audit_guard.py")
    replay_module = load("replay_v2", HERE / "replay_guard.py")
    builder = audit_module.load_builder()
    files = builder.drill.load_official(ROOT / "artifacts/firmware/gxr-1.51")
    original = files["ilaunch3"]
    segments = builder.parse_container(original, ROOT / "research/firmware/ilaunch3-sections.csv")
    audit = json.loads((HERE / "evidence/guard-audit.json").read_text())
    replay = json.loads((HERE / "guard-replay.json").read_text())
    design = json.loads((ROOT / "firmware/stage1a_probe_v2/spec.json").read_text())
    checks, rejections = [], []
    def check(label, condition):
        if not condition:
            raise AssertionError(label)
        checks.append(label)
    def reject(label, action, errors=(ValueError, AssertionError)):
        try:
            action()
        except errors as error:
            rejections.append({"case": label, "rejection": type(error).__name__, "message": str(error)})
        else:
            raise AssertionError(f"Mutation or unsafe output accepted: {label}")
    check("official_29_sha256s", audit["official_sha256"] == {n: sha(b) for n, b in files.items()})
    check("audit_source_identity", audit["audit_script_sha256"] == sha((HERE / "audit_guard.py").read_bytes()))
    check("replay_source_identity", replay["interpreter_sha256"] == sha((HERE / "replay_guard.py").read_bytes()))
    check("blocked_design", design["status"] == audit["decision"] == "BLOCKED_R2_NO_PROVEN_GUARD")
    check("no_firmware_artifact", all(design[k] is None for k in ("patch_kind", "selected_slot", "elf", "payload", "package", "package_ilaunch3_sha256")))
    check("zero_changed_bytes", audit["firmware_changed_bytes"] == design["firmware_changed_bytes"] == 0)
    check("candidate_all_8340_ff", original[0x796C:0x9A00] == b"\xff" * 8340)
    check("official_header_checksum_phase0", builder.drill.checksum_phase(original) == 0)
    check("flag_initialization", audit["flag"]["file_offset"] == "0x8b318" and original[0x8B318:0x8B31C] == b"\0" * 4)
    check("disassembly_scope", audit["census"]["verified_disassembly_lines"] == 1140226)
    check("all_13_caller_words", len(audit["verified_caller_words"]) == 13)
    check("all_41_public_init_callbacks", len(audit["common_init_callbacks_before_scan"]) == 41)
    for window in audit["windows"]:
        lo, hi = int(window["va_start"], 0), int(window["va_end"], 0)
        offset, _ = builder.mapped(lo, hi - lo, segments)
        check("original_window_" + window["name"], sha(original[offset:offset + hi - lo]) == window["sha256"])
    actual = replay_module.verify(original)
    check("replay_matches_retained_evidence", all(actual[k] == replay[k] for k in actual))
    check("40_setter_and_32_decision_cases", actual["passed"] == 72 and len(actual["setter_cases"]) == 40 and len(actual["decision_cases"]) == 32)
    check("eight_synthetic_control_predicate_cases", actual["bit0_only_control_predicate_counterexamples"] == 8)
    check("no_new_code_emulation_claim", actual["v2_firmware_emulated"] is False)
    damaged = dict(files)
    changed = bytearray(damaged["jlaunch3"])
    changed[0x200] ^= 1
    damaged["jlaunch3"] = bytes(changed)
    reject("non_ilaunch3_official_input_changed", lambda: builder.drill.check_official(damaged))
    missing = dict(files)
    missing.pop("ilaunch3")
    reject("only_28_official_inputs", lambda: builder.drill.check_official(missing))
    mutated = bytearray(original)
    offset, _ = builder.mapped(0x20068A72, 2, segments)
    mutated[offset:offset + 2] = bytes.fromhex("01 c4")
    reject("flag_setter_OR_changed_to_AND", lambda: replay_module.verify(bytes(mutated)))
    mutated = bytearray(original)
    offset, _ = builder.mapped(0x2036E4D0, 4, segments)
    mutated[offset + 1] = 0xA0
    reject("update_decision_BGEZ_changed_to_BLTZ", lambda: replay_module.verify(bytes(mutated)))
    reject("existing_evidence_directory", lambda: audit_module.output_dir(HERE / "evidence"))
    reject("official_input_directory_as_output", lambda: audit_module.output_dir(ROOT / "artifacts/firmware/gxr-1.51"))
    with tempfile.TemporaryDirectory(prefix="ricoh-v2-output-rejection-", dir="/tmp") as scratch:
        marker = Path(scratch) / "marker"
        marker.write_bytes(b"keep")
        reject("existing_scratch_directory", lambda: audit_module.output_dir(scratch))
        check("existing_output_unchanged", marker.read_bytes() == b"keep")
    existing = ROOT / "artifacts/stage1a-probe/packages/stage1a-probe-ok-ng"
    manifest = json.loads((existing / "manifest.json").read_text())
    for tree, hashes in (("probe", manifest["probe_sha256"]), ("recovery-official-1.51", manifest["recovery_sha256"])):
        directory = existing / tree / "SD_ROOT"
        check("existing_" + tree + "_file_inventory", {p.name for p in directory.iterdir()} == set(files))
        check("existing_" + tree + "_hashes", all(sha((directory / n).read_bytes()) == hashes[n] for n in files))
    check("existing_recovery_still_official", manifest["recovery_sha256"] == builder.drill.OFFICIAL)
    check("official_hashes_still_unchanged", all(sha((ROOT / "artifacts/firmware/gxr-1.51" / n).read_bytes()) == sha(b) for n, b in files.items()))
    result = {
        "schema": "gxr-stage1a-v2-blocked-handoff-verification-v1",
        "decision": audit["decision"], "positive_checks": len(checks), "rejection_checks": len(rejections),
        "failed": 0, "checks": checks, "rejections": rejections,
        "official_files": 29, "verified_disassembly_lines": 1140226, "fresh_windows": len(audit["windows"]),
        "official_instruction_replay_cases": 72, "new_probe_or_producer_emulated": False,
        "selected_slot": None, "package": None, "package_ilaunch3_sha256": None,
        "firmware_changed_bytes": 0, "existing_package_and_official_recovery_verified": True,
        "camera_or_sd_accessed": False, "hardware_acceptance": "NOT_RUN",
        "assets": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in (
            HERE / "audit_guard.py", HERE / "replay_guard.py", HERE / "evidence/guard-audit.json", HERE / "guard-replay.json",
            ROOT / "firmware/stage1a_probe_v2/spec.json", HERE / "REPORT.md", HERE / "FLASH_AND_CHECK.md", Path(__file__))},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"decision": result["decision"], "positive_checks": len(checks), "rejection_checks": len(rejections), "failed": 0, "output": str(path)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
