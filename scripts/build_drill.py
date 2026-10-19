#!/usr/bin/env python3
"""Build a GXR 1.51 update from exact-length ilaunch3 patches, beside an untouched official recovery copy."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
HEADER = 0x200
LENGTH_FIELD = 0x164
CHECKSUM_FIELD = 0x16C
PATCHABLE = {"ilaunch3"}
ARCHIVE_SHA256 = "3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898"
OFFICIAL = {
    "ilaunch0": "b896f40d9f330c4235d99bd6e32963876f9701293530a927672fd6fab7281e65",
    "ilaunch3": "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7",
    "ilaunch4": "c9271288f8d395296623a3fe5358b2d83dec8730a89ed138a48ff8a2e8f14a5a",
    "ilaunch8": "071d207858c5863f72fda37274372ab881d86f6ecd2b1a826ad825f90047e478",
    "jlaunch0": "0606a54c673e6db2b7708598f4ad7f1bebb93ade534087b1d0e28f7aff8e2de9",
    "jlaunch3": "951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673",
    "jlaunch4": "377e980401d98ba303246f00b4633468ef5affa54ffbc22d24659cc4b1c5e8ca",
    "jlaunch8": "92554edf413e0090550f192973d0555ee13770cee0764802be209f491f2c424f",
    "klaunch0": "4b8c1fd4c24cc7112d49290e94f8d9d75523df395aec7c8fff7ad6ac881b0bf6",
    "klaunch3": "491f39a619e7d85eeb28ba5c55494ccaa274872b63b2a98169ee14e8f4757bee",
    "klaunch4": "2dd87ee852b4cea2aff881da9903871a57910da71b27402b1dd29c8dc77fdfe2",
    "klaunch8": "8fc3ff589088b90a8922a200a077aa3f9daed1dbb5d37992c0642c0b63f69f1a",
    "l06firm0": "d7b74b86ec829e90dd4b5c1092abc892b90422fd975942f3d4a6b99ea24e24ef",
    "l06firm3": "6538b919848ee979c3e92ac14a19a29fb8439a1297147c7e0e601afcd135ae8d",
    "l06firm4": "c0aa8256c682a41ad96277eea075e2c58dca5335dc9bc824e09e78fe69ab10d0",
    "l06firm5": "1ddd60028a33aa021169014f07abe263099404522097ad3a267d3fe0387a9c69",
    "l06firm8": "61aae4cfb39ee599eb9647fb72da7b4fd186edcbda298dcb6551fe1fd78d718d",
    "l08firm0": "05cc3f648f84dc1123dc8207a0edbd796a70bec9a01c36fa43199a5959b78e9f",
    "l08firm3": "0a4dff6d3be9b9a9b56dfcbd98a2df59efcb31f7d4eaca6b0c3fbdb1641fde44",
    "l08firm4": "0f787a6fa51893d98bcc778c9e91b2a46ce4fef139828332f418142aa4f36060",
    "l08firm8": "59a75b3ea1cb7dc71d79349e20d49e809eb1678731111678a7b0ef4c8df0db4d",
    "nlaunch0": "480c5b195c983100a80ca3e3128cd2a0686de0f7b482c025ec23db3f8a78f527",
    "nlaunch3": "f96c5b84b8fb442706dd694828f51bea4f5f38ea11a7c6881d050d479df9aabf",
    "nlaunch4": "f2bbc71463d9272adc0da8801bc2997a2c147b0ce33c10aaeac01a506e4c678d",
    "nlaunch8": "52921ca9311de0f093d5dea1531e2c83876f2bf91d7032cf45f60a50328b26be",
    "qlaunch0": "3bbc37c6c12c6fedaa190927cdc0594d059919cffee29309ef211122734c6dc5",
    "qlaunch3": "e487d00b5539aa1e3ca9373829456e00676b37310dc717f0a5bcb5235bac6690",
    "qlaunch4": "eb2533fdb26ee61cc2135c40fa73a2d6f618bd6f1872f594b256ce4b586aa90b",
    "qlaunch8": "9d81ca7c1e33df4cd9f0c5532b22ad55b1c11a492707839705ab4e69f9019e45",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def be32(data, offset):
    return struct.unpack_from(">I", data, offset)[0]


def weighted(payload, phase):
    sums = [sum(payload[residue::6]) for residue in range(6)]
    return sum(total * ((residue + phase) % 6 + 2) for residue, total in enumerate(sums)) & 0xffffffff


def checksum_phase(data):
    phases = [phase for phase in range(6) if weighted(data[HEADER:], phase) == be32(data, CHECKSUM_FIELD)]
    if len(phases) != 1:
        raise ValueError(f"Expected one matching checksum phase, got {phases}")
    return phases[0]


def check_official(files):
    if set(files) != set(OFFICIAL):
        raise ValueError(f"Expected the 29 official file names, got {sorted(files)}")
    wrong = [name for name, data in sorted(files.items()) if digest(data) != OFFICIAL[name]]
    if wrong:
        raise ValueError("Not the official GXR 1.51 files: " + ", ".join(wrong))


def load_official(directory):
    files = {name: (directory / name).read_bytes() for name in OFFICIAL}
    check_official(files)
    return files


def load_segments(path):
    with open(path, newline="") as handle:
        return [
            {"index": int(row["index"]), "start": int(row["file_offset"]),
             "end": int(row["file_offset"]) + int(row["initialized_size"]), "load": int(row["load_address"])}
            for row in csv.DictReader(handle)
        ]


def apply_patches(original, patches, segments):
    patched = bytearray(original)
    records = []
    for patch in patches:
        offset = int(patch["offset"], 16)
        expected = bytes.fromhex(patch["expected"])
        replacement = bytes.fromhex(patch["replacement"])
        end = offset + len(expected)
        if not expected or len(expected) != len(replacement):
            raise ValueError(f"{patch['name']}: replacement must be non-empty and the same length")
        segment = next((s for s in segments if s["start"] <= offset and end <= s["end"]), None)
        if segment is None:
            raise ValueError(f"{patch['name']}: 0x{offset:X} is not inside one loaded segment")
        if any(offset < r["end"] and r["start"] < end for r in records):
            raise ValueError(f"{patch['name']}: overlaps an earlier patch")
        if bytes(patched[offset:end]) != expected:
            raise ValueError(f"{patch['name']}: bytes at 0x{offset:X} differ from the official file")
        patched[offset:end] = replacement
        records.append({
            "name": patch["name"], "offset": f"0x{offset:X}", "start": offset, "end": end,
            "vma": f"0x{segment['load'] + offset - segment['start']:08X}", "segment": segment["index"],
            "expected": expected.hex(" "), "replacement": replacement.hex(" "),
            "changed_bytes": sum(a != b for a, b in zip(expected, replacement)),
        })
    return patched, records


def finish(original, patched):
    phase = checksum_phase(original)
    if be32(patched, LENGTH_FIELD) != len(patched) - HEADER:
        raise ValueError("Payload length field does not match the file")
    struct.pack_into(">I", patched, CHECKSUM_FIELD, weighted(patched[HEADER:], phase))
    if checksum_phase(patched) != phase:
        raise AssertionError("Recomputed checksum does not verify")
    return bytes(patched), phase


def build(files, spec, segments):
    check_official(files)
    outputs = dict(files)
    report = []
    for name in sorted({patch["file"] for patch in spec["patches"]}):
        if name not in PATCHABLE:
            raise ValueError(f"{name} is not patchable in this builder")
        patched, records = apply_patches(files[name], [p for p in spec["patches"] if p["file"] == name], segments)
        outputs[name], phase = finish(files[name], patched)
        report.append({
            "file": name, "checksum_phase": phase,
            "checksum_before": f"0x{be32(files[name], CHECKSUM_FIELD):08X}",
            "checksum_after": f"0x{be32(outputs[name], CHECKSUM_FIELD):08X}",
            "sha256_before": digest(files[name]), "sha256_after": digest(outputs[name]), "patches": records,
        })
    return outputs, report


def allowed_ranges(record):
    return [(p["start"], p["end"]) for p in record["patches"]] + [(CHECKSUM_FIELD, CHECKSUM_FIELD + 4)]


def check_written(drill_root, recovery_root, files, report):
    edited = {record["file"]: record for record in report}
    for root in (drill_root, recovery_root):
        names = sorted(p.name for p in root.iterdir())
        if names != sorted(OFFICIAL):
            raise AssertionError(f"{root} must hold exactly the 29 update files, got {names}")
    check_official({name: (recovery_root / name).read_bytes() for name in OFFICIAL})
    for name in OFFICIAL:
        written = (drill_root / name).read_bytes()
        if name not in edited:
            if written != files[name]:
                raise AssertionError(f"{name} changed but has no patch")
            continue
        record = edited[name]
        if digest(written) != record["sha256_after"] or checksum_phase(written) != record["checksum_phase"]:
            raise AssertionError(f"{name} on disk does not match the built image")
        ranges = allowed_ranges(record)
        stray = [i for i, (a, b) in enumerate(zip(files[name], written)) if a != b and not any(s <= i < e for s, e in ranges)]
        if len(written) != len(files[name]) or stray:
            raise AssertionError(f"{name} differs outside its declared patches: {stray[:8]}")


def write_tree(root, outputs):
    root.mkdir(parents=True)
    for name, data in sorted(outputs.items()):
        (root / name).write_bytes(data)
    sums = "".join(f"{digest(outputs[name])}  {name}\n" for name in sorted(outputs))
    (root.parent / "SHA256SUMS").write_text(sums)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--firmware", type=Path, default=ROOT / "artifacts/firmware/gxr-1.51")
    parser.add_argument("--sections", type=Path, default=ROOT / "research/firmware/ilaunch3-sections.csv")
    parser.add_argument("--output", type=Path, help="New directory to create; omit to only check the spec")
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    files = load_official(args.firmware)
    outputs, report = build(files, spec, load_segments(args.sections))
    manifest = {
        "name": spec["name"], "base": "Ricoh GXR 1.51 official update (29 files)",
        "official_archive_sha256": ARCHIVE_SHA256, "modified_files": [r["file"] for r in report],
        "edits": report, "drill_sha256": {n: digest(d) for n, d in sorted(outputs.items())},
        "recovery_sha256": dict(sorted(OFFICIAL.items())),
    }
    if args.output:
        if args.output.exists():
            raise FileExistsError(f"Refusing to overwrite {args.output}")
        drill_root = args.output / "drill" / "SD_ROOT"
        recovery_root = args.output / "recovery-official-1.51" / "SD_ROOT"
        write_tree(drill_root, outputs)
        write_tree(recovery_root, files)
        check_written(drill_root, recovery_root, files, report)
        manifest["written_and_reverified"] = True
        (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "name": spec["name"], "modified_files": manifest["modified_files"],
        "patches": [{k: p[k] for k in ("name", "offset", "vma", "segment", "changed_bytes")} for r in report for p in r["patches"]],
        "sha256_after": {r["file"]: r["sha256_after"] for r in report},
        "output": str(args.output) if args.output else None,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
