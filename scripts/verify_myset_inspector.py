#!/usr/bin/env python3
"""Check the inspector with literal synthetic values; these are not camera records."""

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/a12-50/synthetic-myset"


def run(name, record, wanted_exit, wanted_checksum):
    path = OUT / (name + ".bin")
    path.write_bytes(record)
    original = hashlib.sha256(path.read_bytes()).hexdigest()
    result = subprocess.run([sys.executable, str(ROOT / "scripts/inspect_myset.py"), str(path)], capture_output=True, text=True, timeout=10)
    assert result.returncode == wanted_exit, result.stderr
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original
    data = json.loads(result.stdout)
    assert data["checksum_matches"] is wanted_checksum
    (OUT / (name + ".json")).write_text(result.stdout)
    return {"case": name, "exit_code": result.returncode, "checksum_matches": data["checksum_matches"], "input_unchanged": True}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sample = bytearray(1024)
    struct.pack_into(">I", sample, 0x20, 288)
    # First byte has weight 1, last byte has weight 16. Literal expected sum is 17.
    sample[0x100], sample[0x21F] = 1, 1
    struct.pack_into(">I", sample, 0x50, 17)
    checks = [run("synthetic-envelope", sample, 0, True)]
    corrupted = bytearray(sample)
    corrupted[0x21F] = 2
    checks.append(run("synthetic-payload-mutation", corrupted, 1, False))
    wrong_length = bytearray(sample)
    struct.pack_into(">I", wrong_length, 0x20, 287)
    checks.append(run("synthetic-header-length", wrong_length, 1, True))
    evidence = {"status": "passed", "synthetic_only": True, "camera_samples_tested": 0, "literal_checksum": 17, "checks": checks}
    (OUT / "verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()
