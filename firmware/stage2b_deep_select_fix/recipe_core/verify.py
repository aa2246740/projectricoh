#!/usr/bin/env python3

import hashlib
import json
import pathlib
import sys
import zlib


EXPECTED_GOLDEN_PREFIX = bytes.fromhex(
    "4758525243503031010700034100ff000000000000000000000000000000000000"
    "000000000000000000000000112233445566778899aabbcc000000"
)
EXPECTED_GOLDEN_CRC = 0x2FF80AB5


def require(condition: bool, label: str, checks: list[str]) -> None:
    if not condition:
        raise AssertionError(label)
    checks.append(label)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stored_crc(record: bytes) -> int:
    return int.from_bytes(record[60:64], "big")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} ARTIFACT_DIRECTORY", file=sys.stderr)
        return 2

    artifact_directory = pathlib.Path(sys.argv[1])
    golden_path = artifact_directory / "golden.bin"
    host_path = artifact_directory / "host-files" / "slot-16.rcp"
    results_path = artifact_directory / "test-results.txt"
    checks: list[str] = []

    golden = golden_path.read_bytes()
    require(len(golden) == 64, "golden record is 64 bytes", checks)
    require(
        golden[:60] == EXPECTED_GOLDEN_PREFIX,
        "golden first 60 bytes match the fixed vector",
        checks,
    )
    require(
        zlib.crc32(golden[:60]) == EXPECTED_GOLDEN_CRC,
        "Python zlib matches the fixed CRC32 value 0x2ff80ab5",
        checks,
    )
    require(
        stored_crc(golden) == EXPECTED_GOLDEN_CRC,
        "golden stores the CRC32 in big-endian order",
        checks,
    )

    host_record = host_path.read_bytes()
    require(len(host_record) == 64, "host file record is 64 bytes", checks)
    require(host_record[:8] == b"GXRRCP01", "host file has recipe magic", checks)
    require(host_record[8] == 1, "host file has format version 1", checks)
    require(host_record[9] == 16, "host file embeds slot 16", checks)
    require(host_record[10] == 0, "host file flags are zero", checks)
    require(host_record[11] == 16, "host file name length is 16", checks)
    expected_name = bytes((0x61 + index * 17) & 0xFF for index in range(16))
    require(host_record[12:28] == expected_name, "host file name bytes round-trip", checks)
    require(host_record[28:44] == bytes(16), "host unused name bytes are zero", checks)
    expected_colors = bytes((0x61 + index * 3) & 0xFF for index in range(13))
    require(host_record[44:57] == expected_colors, "host colors round-trip", checks)
    require(host_record[57:60] == bytes(3), "host reserved bytes are zero", checks)
    require(
        stored_crc(host_record) == zlib.crc32(host_record[:60]),
        "Python zlib validates the host file CRC32",
        checks,
    )

    test_results = results_path.read_text(encoding="utf-8")
    require(
        "host: PASS recipe_core checks=" in test_results,
        "strict host test run passed",
        checks,
    )
    require(
        "asan-ubsan: PASS recipe_core checks=" in test_results,
        "ASan and UBSan test run passed",
        checks,
    )
    require(
        "freestanding: no undefined symbols" in test_results,
        "freestanding object has no undefined symbols",
        checks,
    )

    report = {
        "status": "pass",
        "checks": checks,
        "golden": {
            "path": str(golden_path),
            "sha256": sha256(golden),
            "crc32": f"{stored_crc(golden):08x}",
        },
        "host_file": {
            "path": str(host_path),
            "sha256": sha256(host_record),
            "crc32": f"{stored_crc(host_record):08x}",
        },
    }
    report_path = artifact_directory / "verification.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"PASS verification checks={len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
