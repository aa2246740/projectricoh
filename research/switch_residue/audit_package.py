#!/usr/bin/env python3
"""Read back the frozen switch-fix package against tested source and official files."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = ROOT / "artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8"
IMAGE_SHA = "efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7"
TABLE_SHA = "44a0ff9e3b584f62dafb76aa90ba05c2bb75c2b74f78f23853345930804e6f05"
BANK_SHA = "9b04ab6b5fe30c2a59d2b88c3219ffca6220791e7f4c5ba1bbf11b4c2278cb38"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    listed = {}
    for line in (PACKAGE / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        path = (PACKAGE / name).resolve()
        assert path.is_relative_to(PACKAGE) and name not in listed
        assert sha(path.read_bytes()) == digest, name
        listed[name] = digest
    assert set(listed) == {str(p.relative_to(PACKAGE)) for p in PACKAGE.rglob("*")
                           if p.is_file() and p.name != "SHA256SUMS"}
    source = ROOT / "firmware/stage2l_switch"
    spec = importlib.util.spec_from_file_location("switch_final_audit", source / "tools/audit_image.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    files, hooks, payload, symbols = audit.read_inputs(source / "build")
    expected = audit.audit(files, hooks, payload, symbols)
    candidate = PACKAGE / "candidate/SD_ROOT"
    recovery = PACKAGE / "recovery-official-1.51/SD_ROOT"
    data_names = {"DEEPISP0.DAT", "DEEPISP1.DAT", "DEEPTBL0.DAT", "DEEPTBL1.DAT",
                  "RECIPE20.DAT", "RECIPE21.DAT"}
    assert {p.name for p in candidate.iterdir()} == set(files) | data_names
    assert {p.name for p in recovery.iterdir()} == set(files)
    for name, official in files.items():
        assert (recovery / name).read_bytes() == official, name
        if name != "ilaunch3":
            assert (candidate / name).read_bytes() == official, name
    for name in data_names:
        digest = TABLE_SHA if name.startswith("DEEPTBL") else BANK_SHA
        assert sha((candidate / name).read_bytes()) == digest, name
    image = (candidate / "ilaunch3").read_bytes()
    assert sha(image) == IMAGE_SHA == expected["candidate_image_sha256"]
    assert len(image) == expected["candidate_image_bytes"]
    checksum = sum(value * (i % 6 + 2) for i, value in enumerate(image[512:])) & 0xffffffff
    assert checksum == struct.unpack_from(">I", image, 0x16c)[0]
    assert image[0x796c:0x796c + len(payload)] == payload
    for hook in hooks["hooks"]:
        offset = int(hook["file_offset"], 16)
        assert image[offset:offset + hook["length"]] == bytes.fromhex(hook["new_bytes"])
    packaged = json.loads((PACKAGE / "evidence/candidate_verification.json").read_text())
    windows = packaged["protected_update_windows"]
    assert len(windows) == packaged["protected_update_windows_count"] == 30
    for window in windows:
        offset, size = int(window["file_offset"], 16), window["length"]
        part = image[offset:offset + size]
        assert part == files["ilaunch3"][offset:offset + size] and sha(part) == window["sha256"]
    gate_spec = importlib.util.spec_from_file_location("switch_packaged_gate", HERE / "package_fix.py")
    gate = importlib.util.module_from_spec(gate_spec)
    gate_spec.loader.exec_module(gate)
    for label, sanitizers, daily in gate.LABELS:
        report = json.loads((PACKAGE / "evidence" / f"{label}.json").read_text())
        gate.validate_report(report, sanitizers=sanitizers, daily=daily, expected_keys=gate.evidence_keys(daily))
        for name, digest in report["sources_sha256"].items():
            assert sha((ROOT / name).read_bytes()) == digest, name
    result = dict(status="PACKAGED_ARTIFACT_READBACK_PASS", image_sha256=sha(image),
                  listed_files_verified=len(listed), candidate_files=35, recovery_files=29,
                  unchanged_official_components=28, protected_update_windows=30,
                  source_and_host_evidence_current=True, external_probe_present=False,
                  camera_executed=False, sd_accessed=False)
    (HERE / "local/package-readback.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
