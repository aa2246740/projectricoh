#!/usr/bin/env python3
"""Write the stage2d phase-1 package. Does not touch a camera or an SD card."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
BUILD = HERE / "build"
PACKAGE = ROOT / "artifacts/stage2d-packages/stage2d-phase1"
STAGE2C = ROOT / "artifacts/stage2c-packages/stage2c-category-gate/candidate/SD_ROOT/ilaunch3"
OFFICIAL_I = "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7"
OFFICIAL_J = "951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673"
STAGE2C_SHA = "11d0e9839fa93f6d23f4e9a92b8fc1b569d32498a911412769cb1babc44d7a0c"
DATS = ("DEEPISP0.DAT", "DEEPISP1.DAT", "RECIPE20.DAT", "RECIPE21.DAT")


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def guard(path):
    text = str(path)
    if "RICOH" in text and "DCX" in text:
        raise SystemExit(f"refusing path {text}")


def runs(old, new):
    found = []
    index = 0
    while index < len(old):
        if old[index] == new[index]:
            index += 1
            continue
        end = index + 1
        while end < len(old) and old[end] != new[end]:
            end += 1
        found.append((index, end))
        index = end
    return found


def classify(start, end, hooks):
    if 0x16C <= start and end <= 0x170:
        return "checksum"
    for hook in hooks:
        hook_at = int(hook["file_offset"], 16)
        if hook_at <= start and end <= hook_at + hook["length"]:
            return hook["id"]
    if 0x976C <= start and end <= 0x9900:
        return "payload-tail-now-ff"
    if 0x796C <= start and end <= 0x9900:
        return "payload"
    return "unexpected"


def main():
    for path in (HERE, BUILD, PACKAGE, STAGE2C, ROOT / "artifacts/firmware/gxr-1.51"):
        guard(path)
    audit = load("stage2d_audit", HERE / "tools/audit_image.py")
    builder = load("stage2d_candidate", HERE / "tools/build_candidate.py")
    routing = load("stage2d_routing", HERE / "tests/test_ui_routing.py")
    audit_log = subprocess.run(
        [sys.executable, "-I", str(HERE / "tests/test_audit_image.py"), "--build", str(BUILD)],
        cwd=ROOT, text=True, capture_output=True)
    (BUILD / "image-audit-tests.txt").write_text(audit_log.stdout + audit_log.stderr)
    if audit_log.returncode != 0:
        raise SystemExit(audit_log.stdout + audit_log.stderr)
    body, report = builder.create_candidate(BUILD)
    image_audit = audit.audit(*audit.read_inputs(BUILD))
    if sha(body) != image_audit["candidate_image_sha256"]:
        raise SystemExit("candidate bytes disagree with the audit")
    (BUILD / "image_audit.json").write_text(json.dumps(image_audit, indent=2) + "\n")
    ui = routing.check(body)
    if not ui["passed"] or len(ui["cases"]) != 25:
        raise SystemExit(f"dispatcher failed: {len(ui['failures'])}")
    (BUILD / "ui_routing.json").write_text(json.dumps(ui, indent=2) + "\n")

    official = (ROOT / "artifacts/firmware/gxr-1.51/ilaunch3").read_bytes()
    jlaunch = (ROOT / "artifacts/firmware/gxr-1.51/jlaunch3").read_bytes()
    previous = STAGE2C.read_bytes()
    if sha(official) != OFFICIAL_I or sha(jlaunch) != OFFICIAL_J or sha(previous) != STAGE2C_SHA:
        raise SystemExit("baseline firmware hash changed")
    if body[0x26F8FC:0x26F900] != b"\xd2\xc0\x20\x5e" or previous[0x26F8FC:0x26F900] != body[0x26F8FC:0x26F900]:
        raise SystemExit("dispatcher bytes changed")
    if body[0x32C634:0x32C660] != official[0x32C634:0x32C660]:
        raise SystemExit("jump table changed")
    if body[0x9900:0x9A00] != b"\xff" * 256:
        raise SystemExit("probe tail is not 0xFF")
    hooks = json.loads((BUILD / "hooks.json").read_text())["hooks"]
    cuts = [0x16C, 0x170, 0x796C, 0x976C, 0x9900]
    for hook in hooks:
        hook_at = int(hook["file_offset"], 16)
        cuts.extend((hook_at, hook_at + hook["length"]))
    regions = []
    for start, end in runs(previous, body):
        points = [start, *[cut for cut in sorted(set(cuts)) if start < cut < end], end]
        for piece_start, piece_end in zip(points, points[1:]):
            kind = classify(piece_start, piece_end, hooks)
            if kind == "unexpected":
                raise SystemExit(f"unexpected diff at {piece_start:#x}..{piece_end:#x}")
            regions.append({"file_offset": hex(piece_start), "end": hex(piece_end),
                            "length": piece_end - piece_start, "kind": kind})
    (BUILD / "diff-vs-stage2c.json").write_text(json.dumps({
        "baseline_sha256": STAGE2C_SHA,
        "candidate_sha256": sha(body),
        "changed_bytes": sum(item["length"] for item in regions),
        "regions": regions,
    }, indent=2) + "\n")

    if PACKAGE.exists():
        raise SystemExit("package already exists")
    files, _, payload, _ = audit.read_inputs(BUILD)
    candidate = dict(files)
    candidate["ilaunch3"] = body
    for name in DATS:
        candidate[name] = (HERE / "examples" / name).read_bytes()
    if len(files) != 29 or len({sha(candidate[name]) for name in DATS}) != 1:
        raise SystemExit("component or DAT inventory mismatch")

    def write_tree(root, blobs):
        root.mkdir(parents=True)
        for name, data in sorted(blobs.items()):
            guard(root / name)
            (root / name).write_bytes(data)
            if (root / name).read_bytes() != data:
                raise SystemExit(f"readback failed for {name}")

    write_tree(PACKAGE / "candidate/SD_ROOT", candidate)
    write_tree(PACKAGE / "recovery-official-1.51/SD_ROOT", files)
    evidence = PACKAGE / "evidence"
    evidence.mkdir()
    names = (
        "payload.bin", "payload.elf", "payload.map", "payload-disasm.txt", "payload-headers.txt",
        "manifest.json", "hooks.json", "verification.json", "abi-tests.json", "abi-results.txt",
        "candidate_verification.json", "host-results.txt", "sanitizers-results.txt",
        "tools-results.txt", "image-audit-tests.txt", "image_audit.json", "ui_routing.json",
        "diff-vs-stage2c.json",
    )
    for name in names:
        (evidence / name).write_bytes((BUILD / name).read_bytes())
    (evidence / "tables_manifest.json").write_bytes(
        (ROOT / "research/stage2d_phase1/tables_manifest.json").read_bytes())
    readme = """# stage2d-phase1

Host-verified candidate. The camera has not been flashed.

Four rows: 01 Posi, 02 Nega, 03 HC BW, 04 Std. Slots 5..16 are empty.
The ADJ count byte is 0x04. Category 0 and 4 still apply; every other category conflicts.

candidate/SD_ROOT has the 29 firmware files plus DEEPISP0.DAT, DEEPISP1.DAT, RECIPE20.DAT and RECIPE21.DAT.
recovery-official-1.51/SD_ROOT has the 29 official 1.51 files.
jlaunch3 is byte-identical to official.

Check the tree with `shasum -a 256 -c SHA256SUMS` from this directory.
"""
    (PACKAGE / "README.md").write_text(readme)
    manifest = {
        "schema": "stage2d-phase1-v1",
        "package": "stage2d-phase1",
        "status": "HOST_VERIFIED_CAMERA_NOT_RUN",
        "camera_executed": False,
        "sd_accessed": False,
        "candidate_ilaunch3_sha256": sha(body),
        "official_ilaunch3_sha256": sha(official),
        "official_jlaunch3_sha256": sha(jlaunch),
        "stage2c_ilaunch3_sha256": sha(previous),
        "stage2c_ilaunch3_unchanged": sha(previous) == STAGE2C_SHA,
        "official_inputs_unchanged": True,
        "jlaunch3_byte_identical_to_official": candidate["jlaunch3"] == jlaunch,
        "other_components_equal_official": 28,
        "recovery_files_equal_official": 29,
        "checksum": image_audit["checksum"],
        "checksum_phase": 0,
        "payload": {
            "bytes": len(payload),
            "sha256": sha(payload),
            "base": "0x2005276c",
            "end": "0x2005456c",
            "probe_tail": "0x20054700..0x20054800",
            "probe_tail_is_ff": True,
            "free_bytes_before_probe": 0x20054700 - 0x2005456C,
        },
        "dat_sha256": {name: sha(candidate[name]) for name in DATS},
        "names": ["01 Posi", "02 Nega", "03 HC BW", "04 Std"],
        "adj_count": 4,
        "deep_slots": [1, 2, 3],
        "diff_vs_stage2c": regions,
        "tests": {
            "host_cases": 84,
            "sanitizer_cases": 84,
            "abi_model_cases": 36,
            "tool_cases": 17,
            "image_audit_cases": audit_log.stdout.count("ok"),
            "dispatcher_cases": len(ui["cases"]),
            "dispatcher_passed": True,
            "protected_update_windows": report["protected_update_windows_count"],
        },
    }
    verification = json.loads((BUILD / "verification.json").read_text())
    audit_cases = int(re.search(r"Ran (\d+) tests", audit_log.stdout + audit_log.stderr)[1])
    manifest["tests"] = {
        "host_cases": verification["host"][0]["cases"],
        "sanitizer_cases": verification["host"][1]["cases"],
        "abi_model_cases": verification["abi_model_cases"],
        "tool_cases": verification["tool_cases"],
        "image_audit_cases": audit_cases,
        "dispatcher_cases": len(ui["cases"]),
        "dispatcher_passed": True,
        "protected_update_windows": report["protected_update_windows_count"],
    }
    manifest["files_sha256"] = {
        str(path.relative_to(PACKAGE)): sha(path.read_bytes())
        for path in sorted(PACKAGE.rglob("*")) if path.is_file()
    }
    (PACKAGE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    sums = "".join(
        f"{sha(path.read_bytes())}  {path.relative_to(PACKAGE)}\n"
        for path in sorted(PACKAGE.rglob("*")) if path.is_file() and path.name != "SHA256SUMS")
    (PACKAGE / "SHA256SUMS").write_text(sums)
    checked = subprocess.run(["shasum", "-a", "256", "-c", "SHA256SUMS"], cwd=PACKAGE, text=True, capture_output=True)
    if checked.returncode != 0:
        raise SystemExit(checked.stdout + checked.stderr)
    (HERE / "hooks.json").write_bytes((BUILD / "hooks.json").read_bytes())
    print(json.dumps({
        "candidate": sha(body),
        "checksum": image_audit["checksum"],
        "payload_bytes": len(payload),
        "regions": [(item["kind"], item["length"]) for item in regions],
        "dispatcher": len(ui["cases"]),
        "windows": report["protected_update_windows_count"],
        "shasum": "ok",
    }))


if __name__ == "__main__":
    main()
