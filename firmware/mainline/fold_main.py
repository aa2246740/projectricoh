#!/usr/bin/env python3
"""Fold selected L2N sites from real DAT Section 3 tables into rebuilt r6 step-1 MAIN."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess
import sys

NAMES = ["p1a", "p1b", "p2a", "p2b", "z1a", "z1b", "z2", "z3", "z4", "z5", "z7", "z6", "r1a", "r1b"]
TIERS = {
    "A": ("p1a", "p1b", "p2a", "p2b"),
    "B": ("p1a", "p1b", "p2a", "p2b", "r1a", "r1b", "z6"),
}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_path(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def default_private_root():
    """The main checkout of the repository holding this script, or None outside Git."""
    try:
        common = subprocess.run(["git", "-C", str(Path(__file__).resolve().parent), "rev-parse",
                                 "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return str(Path(common).parent) if common else None


def workspace_guard_config(private):
    """Optional volume guard: GXR_WORKSPACE_GUARD="<mount point>=<volume UUID>", or
    <private root>/local/workspace_guard.json {"mount": ..., "volume_uuid": ...}. Unset: no check."""
    raw = os.environ.get("GXR_WORKSPACE_GUARD", "")
    if raw:
        mount, sep, uuid = raw.rpartition("=")
        if not sep or not mount or not uuid:
            raise SystemExit("GXR_WORKSPACE_GUARD must be <mount point>=<volume UUID>")
        return mount, uuid
    path = Path(private) / "local" / "workspace_guard.json"
    if path.is_file():
        data = json.loads(path.read_text())
        return data["mount"], data["volume_uuid"]
    return None


def assert_workspace(private):
    """Refuse to build unless the configured volume is mounted, APFS and writable. Returns the mode."""
    config = workspace_guard_config(private)
    if config is None:
        return "unconfigured"
    mount, uuid = config
    info = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", mount]))
    if str(info.get("VolumeUUID", "")).upper() != uuid.upper() or info.get("FilesystemType") != "apfs":
        raise SystemExit("refusing to build: " + mount + " is not the configured project volume")
    if not info.get("WritableVolume"):
        raise SystemExit("refusing to build: " + mount + " is not writable")
    return "checked"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def extract_dat_table(dat_path, expected_count, elf_loader_cls):
    raw = Path(dat_path).read_bytes()
    elf_path = Path(dat_path).parent / "engine.elf"
    if not elf_path.is_file():
        raise SystemExit("missing sibling engine.elf for " + str(dat_path))
    elf = elf_loader_cls(elf_path)
    base = elf.symbols["l2n_patches"]
    xoff, xsize = struct.unpack_from(">II", raw, 132 + 12 * 2)
    if not (xoff <= base and base + expected_count * 72 <= xoff + xsize):
        raise SystemExit(f"l2n_patches outside section 3 (.xdata) in {dat_path}")
    gen = struct.unpack_from(">I", raw, 28)[0]
    rows = []
    for i in range(expected_count):
        pos = base + i * 72
        addr, size, group, mask, pad = struct.unpack_from(">IBBBB", raw, pos)
        if not (0 < size <= 32 and pad == 0 and group in (1, 2, 3)):
            raise SystemExit(f"invalid record {i} in {dat_path}")
        if raw[pos + 8 + size:pos + 40] != bytes(32 - size) or raw[pos + 40 + size:pos + 72] != bytes(32 - size):
            raise SystemExit(f"nonzero padding in record {i} of {dat_path}")
        rows.append({
            "name": NAMES[i],
            "address": addr,
            "size": size,
            "group": group,
            "mask": mask,
            "old": raw[pos + 8:pos + 8 + size],
            "new": raw[pos + 40:pos + 40 + size],
            "dat_offset": pos,
        })
    return gen, sha256_bytes(raw), rows


def real_section_offset(image, va, size):
    matches = [
        (s.index, s.source + 0x200 + va - s.base)
        for s in image.sections
        if s.size and s.base <= va and va + size <= s.base + s.size
    ]
    if len(matches) != 1:
        raise SystemExit(f"expected unique section match for {hex(va)}..{hex(va + size)}, got {matches}")
    sec_idx, off = matches[0]
    if off != va - 0x2004ae00:
        raise SystemExit(f"formula mismatch at {hex(va)}: section offset {hex(off)} != {hex(va - 0x2004ae00)}")
    return sec_idx, off


def classify_delta(before, after, windows):
    counts = {}
    unknown = []
    for pos, (a, b) in enumerate(zip(before, after)):
        if a == b:
            continue
        hits = [name for lo, hi, name in windows if lo <= pos < hi]
        if len(hits) != 1:
            unknown.append(pos)
            key = "UNKNOWN"
        else:
            key = hits[0]
        counts[key] = counts.get(key, 0) + 1
    if unknown:
        raise SystemExit(f"unclassified byte delta ({len(unknown)} bytes), first={hex(unknown[0])}")
    return sum(counts.values()), counts


def main():
    parser = argparse.ArgumentParser(description="Fold selected L2N sites into r6 step-1 MAIN")
    parser.add_argument("--tier", choices=sorted(TIERS), required=True)
    parser.add_argument("--base-main", type=Path, required=True, help="Rebuilt r6 step-1 ilaunch3")
    parser.add_argument("--official-main", type=Path, required=True)
    parser.add_argument("--r5-main", type=Path, required=True)
    parser.add_argument("--dat-235", type=Path, required=True)
    parser.add_argument("--dat-239", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Empty or nonexistent output directory")
    parser.add_argument("--private-root", type=Path)
    args = parser.parse_args()

    if not sys.flags.isolated or not sys.dont_write_bytecode:
        raise SystemExit("run with python3 -I -B")
    chosen = args.private_root or os.environ.get("GXR_PRIVATE_ROOT") or default_private_root()
    if not chosen:
        raise SystemExit("set GXR_PRIVATE_ROOT or pass --private-root (no Git checkout found)")
    private = Path(chosen).resolve()
    print(json.dumps({"workspace_guard": assert_workspace(private)}), flush=True)
    if not (private / "tools/loadgate.py").is_file():
        raise SystemExit("invalid GXR_PRIVATE_ROOT: " + str(private))

    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit("output directory must be empty or nonexistent: " + str(out))

    loader_mod = load_module(private / "tools/native_harness_c/image_loader.py", "fold_image_loader")
    img_mod = load_module(private / "firmware/image_v310/build.py", "fold_image_v310")

    official = loader_mod.Image(args.official_main)
    r5 = loader_mod.Image(args.r5_main)
    r6 = loader_mod.Image(args.base_main)
    for label, img in (("official", official), ("r5", r5), ("r6_step1", r6)):
        if len(img.raw) != 3993340:
            raise SystemExit(f"{label} length {len(img.raw)} != 3993340")
    if not (official.raw[32:352] == r5.raw[32:352] == r6.raw[32:352]):
        raise SystemExit("16 section headers differ between official/r5/r6")

    gen235, sha235, rows235 = extract_dat_table(args.dat_235, 10, loader_mod.Elf)
    gen239, sha239, rows239 = extract_dat_table(args.dat_239, 14, loader_mod.Elf)
    if gen235 != 235 or gen239 != 239:
        raise SystemExit(f"unexpected generations: {gen235}, {gen239}")
    strip = lambda r: {k: v for k, v in r.items() if k != "dat_offset"}
    if list(map(strip, rows235)) != list(map(strip, rows239[:10])):
        raise SystemExit("235 and 239 first 10 patch records do not match")

    win_sec, win_start = real_section_offset(r6, 0x2005276c, 0x20054800 - 0x2005276c)
    win_end = win_start + (0x20054800 - 0x2005276c)
    h42_sec, h42_off = real_section_offset(r6, 0x20171fd0, 4)

    selected_names = TIERS[args.tier]
    rows_by_name = {r["name"]: r for r in rows239}
    raw = bytearray(r6.raw)

    folded_windows = []
    site_records = []
    for name in selected_names:
        row = rows_by_name[name]
        va, size = row["address"], row["size"]
        sec_off_o = real_section_offset(official, va, size)
        sec_off_5 = real_section_offset(r5, va, size)
        sec_off_6 = real_section_offset(r6, va, size)
        if sec_off_o != sec_off_5 or sec_off_5 != sec_off_6:
            raise SystemExit(f"section offset mismatch across images at {name}")
        sec_idx, off = sec_off_6
        if off < win_end and win_start < off + size:
            raise SystemExit(f"{name} overlaps resident window")
        if off < 0x170 and 0x16c < off + size:
            raise SystemExit(f"{name} overlaps checksum field")
        if off < h42_off + 4 and h42_off < off + size:
            raise SystemExit(f"{name} overlaps H42 site")
        old_b = row["old"]
        if not (official.raw[off:off + size] == r5.raw[off:off + size] == r6.raw[off:off + size] == old_b):
            raise SystemExit(f"old bytes mismatch at {name} ({hex(va)})")
        raw[off:off + size] = row["new"]
        diff_n = sum(a != b for a, b in zip(old_b, row["new"]))
        folded_windows.append((off, off + size, f"fold_{name}"))
        site_records.append({
            "name": name,
            "va": hex(va),
            "file_offset": hex(off),
            "r6_section": sec_idx,
            "size": size,
            "actual_changed_bytes": diff_n,
            "old_sha256": sha256_bytes(old_b),
            "new_sha256": sha256_bytes(row["new"]),
        })

    new_sum = img_mod.checksum(raw)
    struct.pack_into(">I", raw, 0x16c, new_sum)
    if img_mod.checksum(raw) != struct.unpack_from(">I", raw, 0x16c)[0]:
        raise SystemExit("checksum verification failed after packing")
    if len(raw) != 3993340 or raw[32:352] != r6.raw[32:352]:
        raise SystemExit("file length or section headers altered")
    if raw[win_start:win_end] != r6.raw[win_start:win_end]:
        raise SystemExit("resident window modified")
    if raw[h42_off:h42_off + 4] != r6.raw[h42_off:h42_off + 4]:
        raise SystemExit("H42 site modified")

    final_bytes = bytes(raw)
    n_vs_r6, acc_vs_r6 = classify_delta(r6.raw, final_bytes, folded_windows + [(0x16c, 0x170, "checksum")])
    n_vs_r5, acc_vs_r5 = classify_delta(
        r5.raw, final_bytes, folded_windows + [(win_start, win_end, "resident_window"), (0x16c, 0x170, "checksum")]
    )

    out.mkdir(parents=True, exist_ok=True)
    (out / "ilaunch3").write_bytes(final_bytes)
    (out / "NOT_FOR_INSTALLATION").write_text(
        f"Offline folded candidate (Tier {args.tier}). NOT_FOR_INSTALLATION.\n"
    )
    receipt = {
        "tier": args.tier,
        "main_sha256": sha256_bytes(final_bytes),
        "main_bytes": len(final_bytes),
        "checksum_u32": f"0x{new_sum:08x}",
        "inputs": {
            "official_sha256": official.sha256,
            "r5_sha256": r5.sha256,
            "r6_step1_sha256": r6.sha256,
            "dat235_sha256": sha235,
            "dat239_sha256": sha239,
        },
        "resident_window_file": [hex(win_start), hex(win_end)],
        "resident_window_equal_r6_step1": True,
        "h42_site_equal_r6_step1": True,
        "section_headers_equal_official": True,
        "folded_span_bytes": sum(r["size"] for r in site_records),
        "folded_actual_changed_bytes": sum(r["actual_changed_bytes"] for r in site_records),
        "folded_sites": site_records,
        "delta_vs_r6_step1": {"total_bytes": n_vs_r6, "accounts": acc_vs_r6},
        "delta_vs_r5": {"total_bytes": n_vs_r5, "accounts": acc_vs_r5},
    }
    (out / "FOLD_MAIN_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({
        "pass": True,
        "tier": args.tier,
        "main_sha256": receipt["main_sha256"],
        "folded_actual_changed_bytes": receipt["folded_actual_changed_bytes"],
        "delta_vs_r6_step1": receipt["delta_vs_r6_step1"],
        "delta_vs_r5": receipt["delta_vs_r5"],
    }, indent=2))


if __name__ == "__main__":
    main()
