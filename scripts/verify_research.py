#!/usr/bin/env python3
"""Re-run the GXR research against actual pinned artifacts, without a camera."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/verification"


def execute(name, command, cwd=ROOT, environment=None):
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True, timeout=120)
    (OUT / f"{name}.stdout").write_text(result.stdout)
    (OUT / f"{name}.stderr").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f"{name} failed; inspect {OUT / (name + '.stderr')}")
    return {"name": name, "command": command, "cwd": str(cwd), "exit_code": result.returncode}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inventory = OUT / "firmware-inventory.json"
    scan = OUT / "scan.json"
    trace = OUT / "mysettings-trace.json"
    commands = [
        execute("inventory", [sys.executable, "scripts/inspect_gxr.py", "artifacts/downloads/gxr-151.zip", "--output", str(inventory)]),
        execute("scan", [sys.executable, "research/firmware/scan_gxr_firmware.py", "artifacts/firmware/gxr-1.51", "--output", str(scan)]),
        execute("trace", [sys.executable, "research/firmware/trace_mysettings.py", "artifacts/firmware/gxr-1.51/ilaunch3", "research/firmware/ilaunch3-sections.csv", "--output", str(trace)]),
    ]
    first = json.loads(inventory.read_text())
    assert first["archive_sha256"] == "3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898"
    assert first["firmware_file_count"] == 29
    assert all(row["matches_upstream_reference"] and row["payload_length_matches"] for row in first["files"])
    assert all(row["checksum_verified_by_weighted_rule"] for row in first["files"])
    structural = json.loads(scan.read_text())
    assert structural["file_count"] == 29
    for item in structural["files"]:
        wanted_phase = 2 if item["file"].endswith("0") else 4 if item["file"] == "l06firm5" else 0
        assert item["header"]["weighted_checksum_matching_phases"] == [wanted_phase], item["file"]
        assert next(row for row in first["files"] if row["name"] == item["file"])["weighted_checksum_matching_phases"] == [wanted_phase]
    body = next(item for item in structural["files"] if item["file"] == "ilaunch3")
    assert len(body["sections"]) == 16 and len(body["inter_section_gaps"]) == 15
    assert all(gap["loaded"] is False and gap["unique_bytes"] == [255] for gap in body["inter_section_gaps"])
    assert any(hit["text"] == "/ATA1/MYSET" and hit["file_offset"] == 0xF6870 and hit["virtual_address"] == 0x20141670 for hit in body["setting_string_hits"])
    for image, offset, expected in [
        ("jlaunch3", 0x7A2F8, b"RICOH GR LENS A12 50mm F2.5 MACRO"),
        ("qlaunch3", 0x7A320, b"RICOH GR LENS A12 28mm F2.5"),
    ]:
        binary = (ROOT / "artifacts/firmware/gxr-1.51" / image).read_bytes()
        assert binary[offset:offset + len(expected)] == expected
    candidates = json.loads(trace.read_text())
    uses = [use for api in candidates["file_api_address_materializations"] for use in api["materializations"]]
    assert all(use["seth_file_offset"] % 4 == 0 and use["or3_file_offset"] % 4 == 0 for use in uses)
    assert not (ROOT / "tools/rea/deps/node_modules/playwright-core").exists()
    commands.append(execute("rea-version", ["sh", "scripts/rea", "--version"]))
    assert (OUT / "rea-version.stdout").read_text().strip() == "6.4.0"
    vendor_manifest = ROOT / "tools/rea/package/package.json"
    installed = json.loads((ROOT / "artifacts/rea/install-manifest.json").read_text())
    assert hashlib.sha256(vendor_manifest.read_bytes()).hexdigest() == installed["vendor_package_json_sha256"]
    before, after = OUT / "synthetic-before.bin", OUT / "synthetic-after.bin"
    difference = OUT / "synthetic-difference.json"
    before.write_bytes(b"abcdefghi")
    after.write_bytes(b"abcXefghiZ")
    commands.append(execute("synthetic-diff", [sys.executable, "scripts/diff_settings.py", str(before), str(after), "--output", str(difference)]))
    compared = json.loads(difference.read_text())
    assert compared["changed_byte_count"] == 2
    assert compared["differences"] == [
        {"file_offset": 3, "file_offset_hex": "0x3", "length": 1, "before_first_32_bytes_hex": "64", "after_first_32_bytes_hex": "58"},
        {"file_offset": 9, "file_offset_hex": "0x9", "length": 1, "before_first_32_bytes_hex": "", "after_first_32_bytes_hex": "5a"},
    ]
    environment = dict(os.environ)
    environment["GXR151_OFFICIAL_DIR"] = str(ROOT / "artifacts/firmware/gxr-1.51")
    commands.append(execute("upstream-language-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], ROOT / "sources/gxr-language-patch", environment))
    result = {
        "status": "passed", "commands": commands,
        "verified": ["29 firmware hashes and lengths", "29 per-file checksum phases in both manifests", "16 body sections and 15 unloaded FF gaps", "A12 module identity strings", "My Settings string address mapping", "aligned static address candidates", "REA 6.4.0 without another Playwright", "unchanged vendor package manifest", "synthetic file diff with two expected changes", "upstream language patch tests"],
        "limits": ["No camera operation or firmware execution", "No IFO file captures or color-field schema", "Static address candidates do not prove runtime reachability", "Language patch tests do not verify new recipes"],
    }
    (OUT / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "firmware_files": 29, "static_api_candidates": len(uses), "report": str(OUT / "report.json"), "camera_verified": False}))


if __name__ == "__main__":
    main()
