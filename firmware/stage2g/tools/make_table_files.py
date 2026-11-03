#!/usr/bin/env python3
"""Build DEEPTBL0.DAT and DEEPTBL1.DAT for stage 2g. One command, no firmware rebuild.

Two sets are written, each as two identical files:
  new       01/02/05/06 as stage 2e, 03 = GR IV HC candidate, 07/08 = 2e probes
  equal-2e  every entry equal to the stage 2e compiled tables (03 = row 20)

Outputs (all gitignored): firmware/stage2g/examples/tables/<set>/ and, with
--package, artifacts/stage2g-packages/stage2g/local/tables-<set>/. The tracked
manifest research/stage2g/tables_manifest.json holds SHA-256 values only.

  python3 -I firmware/stage2g/tools/make_table_files.py --package
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
RESEARCH = ROOT / "research/stage2g"
PACKAGE_LOCAL = ROOT / "artifacts/stage2g-packages/stage2g/local"


def load():
    import importlib.util
    spec = importlib.util.spec_from_file_location("stage2g_sources", HERE / "tools/deep_sources.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


src = load()


def ignored(path):
    result = subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=ROOT)
    return result.returncode == 0


def guard(path):
    text = str(path)
    if "RICOH" in text and "DCX" in text or text.startswith("/Volumes/RICOH"):
        raise SystemExit(f"refusing path {text}")


def baseline_hashes():
    manifest = json.loads(src.BASELINE_2E.read_text())
    table = manifest["table_sha256"]
    return {name: tuple(table[f"{name}.{label}"] for label in src.ROW_LABELS) for name in src.PROFILE_NAMES}


def build_sets(args):
    _, surface = src.surface_bank()
    image = src.jlaunch()
    built = {}
    for table_set in src.SETS:
        rows = src.profiles(table_set, image, args.fit, args.gr4, args.measurements)
        built[table_set] = (rows, src.table_file(rows, surface))
    # Policy for this version: equal-2e reproduces every 2e row; new differs only in 03.
    expected = baseline_hashes()
    for table_set, (rows, _) in built.items():
        for name, triple in zip(src.PROFILE_NAMES, rows):
            same = tuple(src.sha(blob) for blob in triple) == expected[name]
            want_same = not (table_set == "new" and name == "03 HC BW")
            if same != want_same and not args.no_baseline_check:
                raise SystemExit(f"{table_set}: {name} {'differs from' if want_same else 'equals'} stage 2e")
    new_rows, equal_rows = built["new"][0], built["equal-2e"][0]
    if any(a != b for i, (a, b) in enumerate(zip(new_rows, equal_rows)) if i != 2) or new_rows[2][2] != equal_rows[2][2]:
        raise SystemExit("new and equal-2e differ outside the 03 tone")
    return surface, built


def write_set(directory, blob):
    guard(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name in src.TABLE_NAMES:
        (directory / name).write_bytes(blob)
        if (directory / name).read_bytes() != blob:
            raise SystemExit(f"readback failed for {directory / name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fit", type=Path, default=src.FIT)
    parser.add_argument("--gr4", type=Path, default=src.GR4)
    parser.add_argument("--measurements", type=Path, default=src.MEASUREMENTS)
    parser.add_argument("--package", action="store_true", help="also write the package local/ table sets")
    parser.add_argument("--no-baseline-check", action="store_true",
                        help="allow 01/02/05..08 to drift from stage 2e (future colour work)")
    args = parser.parse_args()
    surface, built = build_sets(args)
    outputs = [HERE / "examples/tables"]
    if args.package:
        outputs.append(PACKAGE_LOCAL)
    for root in outputs:
        for table_set, (_, blob) in built.items():
            directory = root / (f"tables-{table_set}" if root == PACKAGE_LOCAL else table_set)
            if not ignored(directory / src.TABLE_NAMES[0]):
                raise SystemExit(f"{directory} is not gitignored; refusing to write Ricoh-derived bytes")
            write_set(directory, blob)
    if args.package:
        sums = "".join(
            f"{src.sha(path.read_bytes())}  {path.relative_to(PACKAGE_LOCAL)}\n"
            for path in sorted(PACKAGE_LOCAL.rglob("*.DAT")))
        (PACKAGE_LOCAL / "SHA256SUMS").write_text(sums)
        checked = subprocess.run(["shasum", "-a", "256", "-c", "SHA256SUMS"], cwd=PACKAGE_LOCAL,
                                 text=True, capture_output=True)
        if checked.returncode != 0:
            raise SystemExit(checked.stdout + checked.stderr)

    report = {"schema": "stage2g-table-files-v1", "format": {
        "magic": "GXDT", "version": src.VERSION, "entries": len(src.DEEP_SLOTS),
        "header_bytes": src.HEADER_BYTES, "entry_bytes": src.ENTRY_BYTES,
        "file_bytes": src.FILE_BYTES, "ram_alloc_bytes": src.ALLOC_BYTES,
        "row_offsets_in_entry": dict(zip(src.ROW_LABELS, src.ROW_OFFSETS)),
        "header_crc": f"{src.HEADER_CRC:#010x} = CRC32 of bytes 0..11",
        "file_crc": "CRC32 of bytes 16..end at +12, big endian, 0 is invalid",
        "type23": "header flags bit 0 and entry byte +1 reserved; v1 requires 0"},
        "sources_sha256": {str(path.relative_to(ROOT)): src.sha(path.read_bytes()) for path in
                           (src.CURVES, args.fit.resolve(), args.gr4.resolve(), args.measurements.resolve(),
                            src.FIT_ROW, src.BASELINE_2E)},
        "jlaunch3_sha256": src.JLAUNCH_SHA, "sets": {}}
    for table_set, (rows, blob) in built.items():
        entries = {}
        for index, (slot, name) in enumerate(zip(src.DEEP_SLOTS, src.PROFILE_NAMES)):
            start = src.HEADER_BYTES + index * src.ENTRY_BYTES
            entries[name] = {
                "slot": slot,
                "entry_sha256": src.sha(blob[start:start + src.ENTRY_BYTES]),
                "recipe_struct_sha256": src.sha(src.recipe_struct(surface, slot)),
                **{f"{label}_sha256": src.sha(row) for label, row in zip(src.ROW_LABELS, rows[index])},
            }
        report["sets"][table_set] = {"file_sha256": src.sha(blob), "file_bytes": len(blob), "entries": entries}
    RESEARCH.mkdir(parents=True, exist_ok=True)
    (RESEARCH / "tables_manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    for table_set, info in report["sets"].items():
        print(f"{table_set}: DEEPTBL0.DAT = DEEPTBL1.DAT  {info['file_sha256']}  ({info['file_bytes']} B)")
        for name, item in info["entries"].items():
            print(f"  slot {item['slot']} {name:<9} entry {item['entry_sha256']}")
    if args.package:
        print(f"package tables: {PACKAGE_LOCAL.relative_to(ROOT)} (gitignored)")


if __name__ == "__main__":
    main()
