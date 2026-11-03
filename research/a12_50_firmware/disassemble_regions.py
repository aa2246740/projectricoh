#!/usr/bin/env python3
"""Disassemble selected GXR M32R regions with section-aware VMAs."""

from __future__ import annotations

import argparse
import hashlib
import struct
import subprocess
from pathlib import Path


HEADER_SIZE = 0x200
RECORD_END = 0x160
REGIONS = (
    ("ilaunch3", 0x2011D700, 0x20120A00, "ilaunch3-myset.disasm.txt"),
    ("jlaunch3", 0x20187000, 0x2019B000, "jlaunch3-jpeg-dng-paths.disasm.txt"),
    ("jlaunch3", 0x2021D700, 0x2021E700, "jlaunch3-raw-recording.disasm.txt"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sections(path: Path) -> list[dict[str, int]]:
    data = path.read_bytes()
    result = []
    for index, offset in enumerate(range(0x20, RECORD_END, 20)):
        source, load, size, bss, bss_size = struct.unpack_from(">IIIII", data, offset)
        if not any((source, load, size, bss, bss_size)):
            break
        file_offset = HEADER_SIZE + source
        result.append(
            {
                "index": index,
                "file_offset": file_offset,
                "load_address": load,
                "initialized_size": size,
            }
        )
    return result


def containing_section(entries: list[dict[str, int]], start: int, end: int) -> dict[str, int]:
    for entry in entries:
        load = entry["load_address"]
        if load <= start < end <= load + entry["initialized_size"]:
            return entry
    raise ValueError(f"region 0x{start:X}..0x{end:X} does not fit one initialized section")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("firmware_dir", type=Path)
    parser.add_argument("objdump", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    version = subprocess.run(
        [str(args.objdump), "--version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    manifest = [f"objdump: {version}", f"objdump_sha256: {sha256(args.objdump)}"]

    for filename, start, end, output_name in REGIONS:
        firmware = args.firmware_dir / filename
        entry = containing_section(sections(firmware), start, end)
        adjustment = entry["load_address"] - entry["file_offset"]
        command = [
            str(args.objdump),
            "-D",
            "-b",
            "binary",
            "-m",
            "m32r",
            "-EB",
            f"--adjust-vma=0x{adjustment:X}",
            f"--start-address=0x{start:X}",
            f"--stop-address=0x{end:X}",
            str(firmware),
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        output = args.output_dir / output_name
        output.write_text(completed.stdout, encoding="utf-8")
        manifest.extend(
            [
                "",
                f"output: {output.name}",
                f"firmware: {filename}",
                f"firmware_sha256: {sha256(firmware)}",
                f"section_index: {entry['index']}",
                f"section_file_offset: 0x{entry['file_offset']:X}",
                f"section_load_address: 0x{entry['load_address']:X}",
                f"adjust_vma: 0x{adjustment:X}",
                f"region: 0x{start:X}..0x{end:X}",
                "command: " + " ".join(command),
            ]
        )
        print(f"wrote {output}")

    (args.output_dir / "disassembly-manifest.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
