#!/usr/bin/env python3
"""Inspect the known GXR 1.51 MYSET record envelope, without editing the record."""

import argparse
import hashlib
import json
from pathlib import Path
import struct


RECORD_BYTES = 1024
PAYLOAD_FIRST = 0x100
PAYLOAD_END = 0x220


def inspect(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != RECORD_BYTES:
        raise ValueError("Select one regular 1024-byte capture from the camera; do not use firmware or a photograph")
    record = path.read_bytes()
    stored = struct.unpack_from(">I", record, 0x50)[0]
    calculated = sum(record[index] * ((index & 0x0F) + 1) for index in range(PAYLOAD_FIRST, PAYLOAD_END)) & 0xFFFFFFFF
    declared_payload = struct.unpack_from(">I", record, 0x20)[0]
    return {
        "input": str(path), "input_sha256": hashlib.sha256(record).hexdigest(), "read_only": True,
        "record_bytes": len(record), "reference_firmware_version": "1.51",
        "payload_file_offset": hex(PAYLOAD_FIRST), "payload_bytes": PAYLOAD_END - PAYLOAD_FIRST,
        "declared_payload_bytes": declared_payload,
        "declared_payload_matches": declared_payload == PAYLOAD_END - PAYLOAD_FIRST,
        "stored_checksum": hex(stored), "calculated_checksum": hex(calculated),
        "checksum_matches": stored == calculated,
        "payload_sha256": hashlib.sha256(record[PAYLOAD_FIRST:PAYLOAD_END]).hexdigest(),
        "evidence": "research/a12_50_firmware/REPORT.md, VMA 0x2011D700 and save/load callers",
        "limits": [
            "This verifies only the envelope and payload checksum observed in GXR 1.51 code.",
            "Camera loadability, device identity, remaining header fields and color-field meanings are unverified.",
            "A matching checksum is not permission or proof that the record can be written back to a camera.",
            "The input is never changed; this tool cannot construct or repair a record.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None and args.output.resolve() == args.record.resolve():
        raise ValueError("Output must not be the captured input")
    result = inspect(args.record)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
        print(json.dumps({"checksum_matches": result["checksum_matches"], "declared_payload_matches": result["declared_payload_matches"], "output": str(args.output)}))
    else:
        print(encoded, end="")
    if not result["checksum_matches"] or not result["declared_payload_matches"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
