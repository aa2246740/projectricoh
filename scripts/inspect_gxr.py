#!/usr/bin/env python3
"""Inventory a GXR update without executing or changing its firmware."""

import argparse
import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def expected_hashes(source):
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "OFFICIAL_SHA256" for t in node.targets):
                return ast.literal_eval(node.value)
    raise ValueError("Upstream OFFICIAL_SHA256 is missing")


def inspect(archive_path, reference, extract_dir):
    expected = expected_hashes(reference)
    rows = []
    with zipfile.ZipFile(archive_path) as archive:
        for name, known_hash in sorted(expected.items()):
            candidates = [x for x in archive.infolist() if not x.is_dir() and Path(x.filename).name == name]
            if len(candidates) != 1:
                raise ValueError(f"Expected exactly one {name}, got {len(candidates)}")
            member = candidates[0]
            if member.file_size > 32 * 1024 * 1024:
                raise ValueError(f"Unexpected firmware size: {name}")
            data = archive.read(member)
            actual_hash = digest(data)
            if actual_hash != known_hash:
                raise ValueError(f"SHA-256 mismatch for {name}: {actual_hash}")
            if len(data) < 0x200:
                raise ValueError(f"Header is too short: {name}")
            payload = data[0x200:]
            length = struct.unpack_from(">I", data, 0x164)[0]
            checksum = struct.unpack_from(">I", data, 0x16c)[0]
            residue_sums = [sum(payload[residue::6]) for residue in range(6)]
            calculated = [
                sum(total * ((residue + phase) % 6 + 2) for residue, total in enumerate(residue_sums)) & 0xffffffff
                for phase in range(6)
            ]
            phases = [phase for phase, value in enumerate(calculated) if value == checksum]
            if not phases:
                raise ValueError(f"No weighted checksum phase matches {name}")
            counts = Counter(payload)
            entropy = -sum((n / len(payload)) * math.log2(n / len(payload)) for n in counts.values()) if payload else 0
            runs = [
                {"offset": hex(m.start() + 0x200), "length": m.end() - m.start(), "byte": "00" if m.group()[0] == 0 else "ff"}
                for m in re.finditer(rb"\x00{256,}|\xff{256,}", payload)
            ]
            runs.sort(key=lambda x: x["length"], reverse=True)
            rows.append({
                "name": name, "zip_member": member.filename, "bytes": len(data),
                "sha256": actual_hash, "matches_upstream_reference": True,
                "header_ascii": data[:0x40].decode("ascii", errors="replace").rstrip("\x00"),
                "payload_bytes": len(payload), "declared_payload_bytes": length,
                "payload_length_matches": len(payload) == length,
                "stored_checksum": hex(checksum),
                "weighted_checksum_matching_phases": phases,
                "checksum_verified_by_weighted_rule": True,
                "checksum_rule_scope": "Observed on the pinned 29-file GXR 1.51 sample; phases are 0, 2 or 4. Other firmware revisions require new verification.",
                "payload_entropy_bits_per_byte": round(entropy, 4),
                "largest_repeated_byte_runs": runs[:8],
                "padding_warning": "Repeated bytes alone do not prove free code space or free RAM.",
            })
        # Verify all members before writing any extracted binary.
        if extract_dir:
            extract_dir.mkdir(parents=True, exist_ok=True)
            for row in rows:
                destination = extract_dir / row["name"]
                data = archive.read(row["zip_member"])
                if destination.exists() and digest(destination.read_bytes()) != row["sha256"]:
                    raise ValueError(f"Refusing to overwrite a different binary: {destination}")
                if not destination.exists():
                    destination.write_bytes(data)
    return {
        "official_download_url": "https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/exe/gxr-151.zip",
        "archive_sha256": digest(archive_path.read_bytes()),
        "reference_source": str(reference), "reference_sha256": digest(reference.read_bytes()),
        "verification_limit": "Hashes are compared to the pinned community repository, not a Ricoh signature.",
        "firmware_file_count": len(rows), "files": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--reference", type=Path, default=Path("sources/gxr-language-patch/gxr_firmware_modifier.py"))
    parser.add_argument("--extract", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.archive, args.reference, args.extract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "file_count": result["firmware_file_count"], "archive_sha256": result["archive_sha256"],
        "all_hashes_match": all(row["matches_upstream_reference"] for row in result["files"]),
        "all_payload_lengths_match": all(row["payload_length_matches"] for row in result["files"]),
        "all_weighted_checksums_match": all(row["checksum_verified_by_weighted_rule"] for row in result["files"]),
        "checksum_phase_file_counts": dict(Counter(str(phase) for row in result["files"] for phase in row["weighted_checksum_matching_phases"])),
        "report": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
