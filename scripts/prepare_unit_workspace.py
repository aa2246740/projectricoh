#!/usr/bin/env python3
"""Verify the owner's GXR 1.51 ZIP and prepare local-only adaptation inputs.

This does not download, patch, disassemble, flash, or build firmware. Hashes
come from this project's existing build_drill.py, without importing that code.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import struct
import zipfile


ROOT = Path(__file__).resolve().parents[1]
UNITS = {"50mm": "jlaunch", "28mm": "qlaunch", "mount": "l08firm",
         "p10": "klaunch", "s10": "nlaunch", "a16": "l06firm"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def reference():
    assignments = {}
    for node in ast.parse((ROOT / "scripts/build_drill.py").read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"OFFICIAL", "ARCHIVE_SHA256"}:
                    assignments[target.id] = ast.literal_eval(node.value)
    return assignments["ARCHIVE_SHA256"], assignments["OFFICIAL"]


def sections(data):
    result = []
    for index in range(16):
        source, load, size, bss, bss_size = struct.unpack_from(">5I", data, 0x20 + 20 * index)
        if not any((source, load, size, bss, bss_size)):
            break
        start = 0x200 + source
        if not size or start + size > len(data):
            raise ValueError("section outside the pinned main image")
        result.append(dict(index=index, file_offset=start, load_address=load,
                           initialized_size=size, bss_address=bss, bss_size=bss_size))
    if not result:
        raise ValueError("main image has no initialized sections")
    return result


def prepare(archive, unit, output, extract):
    output = output.resolve()
    relative = output.relative_to(ROOT)
    if "local" not in relative.parts:
        raise ValueError("output must be inside a repository local/ directory")
    archive_hash, expected = reference()
    raw_archive = archive.read_bytes()
    if digest(raw_archive) != archive_hash:
        raise ValueError("archive does not match the project's pinned GXR 1.51 ZIP")
    files = {}
    with zipfile.ZipFile(archive) as source:
        for name, known_hash in sorted(expected.items()):
            members = [m for m in source.infolist() if not m.is_dir() and Path(m.filename).name == name]
            if len(members) != 1 or members[0].file_size > 32 * 1024 * 1024:
                raise ValueError("missing, duplicate, or oversized official member: " + name)
            data = source.read(members[0])
            if digest(data) != known_hash:
                raise ValueError("official member hash mismatch: " + name)
            files[name] = data
    prefix = UNITS[unit]
    result = dict(schema="gxr-unit-workspace/1", unit=unit, prefix=prefix,
                  supported_by_current_engine=unit in {"50mm", "28mm", "mount"},
                  archive_sha256=archive_hash,
                  hash_limit="Project-pinned hashes, not a Ricoh signature or hardware compatibility proof.",
                  files=[dict(name=name, bytes=len(data), sha256=digest(data)) for name, data in files.items()],
                  main_sections={name: sections(files[name]) for name in ("ilaunch3", prefix + "3")},
                  extracted=bool(extract),
                  warning="All files and this inventory remain local. P10/S10/A16 require a new port.")
    serialized = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    destinations = {output / "inventory.json": serialized}
    if extract:
        destinations.update({output / "official" / name: data for name, data in files.items()})
    # Check every existing destination before writing any new file.
    for path, data in destinations.items():
        if not path.resolve().is_relative_to(output):
            raise ValueError("destination escapes the local output directory")
        if path.exists() and (path.is_symlink() or not path.is_file() or path.read_bytes() != data):
            raise ValueError("refusing to overwrite a different local file: " + str(path.relative_to(ROOT)))
    for path, data in destinations.items():
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                handle.write(data)
    return dict(unit=unit, prefix=prefix, official_members_verified=len(files),
                main_section_counts={name: len(rows) for name, rows in result["main_sections"].items()},
                extracted=bool(extract), inventory=str((output / "inventory.json").relative_to(ROOT)),
                current_engine_support=result["supported_by_current_engine"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--unit", required=True, choices=UNITS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extract", action="store_true", help="also copy the 29 verified members into output/official/")
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.unit, args.output, args.extract), ensure_ascii=False))
