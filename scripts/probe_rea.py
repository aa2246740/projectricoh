#!/usr/bin/env python3
"""Capture actual project-local REA behavior without using browsers or a device."""

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/rea"


def run(name, arguments):
    command = ["sh", str(ROOT / "scripts/rea"), *arguments]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=45)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.stdout").write_text(result.stdout)
    (OUT / f"{name}.stderr").write_text(result.stderr)
    record = {"command": command, "exit_code": result.returncode,
              "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
              "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest()}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = None
    if name == "providers" and isinstance(data, dict):
        record["native_providers"] = [
            {"provider": candidate.get("provider"), "availability": candidate.get("availability", {}).get("status"),
             "availability_code": candidate.get("availability", {}).get("code")}
            for candidate in data.get("analysis_provider_candidates", [])
        ]
    if name in ["raw-format", "native-admission", "firmware-regions"]:
        record["result_excerpt"] = result.stdout[-1600:]
    if name == "artifact" and isinstance(data, dict):
        record["result_keys"] = list(data)
    return record


def main():
    firmware = str(ROOT / "artifacts/firmware/gxr-1.51/ilaunch3")
    tests = [
        ("version", ["--version"]),
        ("providers", ["providers", "--json"]),
        ("artifact", ["inspect-artifact", str(ROOT / "artifacts/downloads/gxr-151.zip"), "--json"]),
        ("raw-format", ["inspect", firmware, "--target-format", "raw-binary", "--provider", "ghidra", "--json"]),
        ("native-admission", ["inspect", firmware, "--provider", "ghidra", "--json"]),
        ("firmware-regions", ["inspect-firmware-regions", firmware, "--json"]),
    ]
    records = [run(name, arguments) for name, arguments in tests]
    (OUT / "probes.json").write_text(json.dumps(records, indent=2) + "\n")
    print(json.dumps([{"probe": name, "exit_code": record["exit_code"], "evidence": f"artifacts/rea/{name}.stdout"} for (name, _), record in zip(tests, records)]))


if __name__ == "__main__":
    main()
