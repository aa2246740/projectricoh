#!/usr/bin/env python3
"""Rebuild the daily engine DAT from firmware/mainline.

Toolchain, the ELF reader and the service flag profile come from
GXR_PRIVATE_ROOT (default: the main checkout of the Git repository holding this
script). Run prepare_local.py first. The optional volume guard is configured
with GXR_WORKSPACE_GUARD or <private root>/local/workspace_guard.json; see
workspace_guard_config().
--profile daily writes generation 185 and uses the g185 random-seed paths.
--profile g188-r2 writes generation 188 and uses the g188 seed paths; apply
patches/g188-r2.patch and prepare the g188 local overlay before that build.
--profile g188-r3 writes generation 214 and defines G188_R3. Its random-seed
prefix is research/g188_r3/local/engine. Prepare the g188-r2 local overlay
first; this profile does not have its own overlay.
--profile user-slots-r4 writes generation 216 and defines G188_R3 and
USER_SLOTS_R4. Its random-seed prefix is research/user_slots_r4/local/engine.
It uses the same g188-r2 local overlay.
--profile xpan-d123-r1 writes generation 218 and defines G188_R3,
USER_SLOTS_R4, XPAN_D123_R1 and XPAN_D2_DIAG. Its random-seed prefix is
research/xpan_d123_fix/local/engine. It uses the same g188-r2 local overlay.
--profile xpan-d123-r1-nodiag writes generation 219 with the same fixes and
without XPAN_D2_DIAG. Its random-seed prefix is
research/xpan_d123_fix/local/engine-nodiag.
--profile xpan-d123-r2 writes generation 220 and defines G188_R3,
USER_SLOTS_R4, XPAN_D123_R1, XPAN_D2_DIAG and XPAN_D1_R2. Its random-seed
prefix is research/xpan_d123_fix_r2/local/engine. It uses the same g188-r2
local overlay.
--profile xpan-d123-r2-nodiag writes generation 221 with the same fixes and
without XPAN_D2_DIAG. Its random-seed prefix is
research/xpan_d123_fix_r2/local/engine-nodiag.
--profile merged-r1d-fold-a-zoom writes generation 242: 240 plus XPAN_ZOOM_R1
(playback-zoom fix B + Z7 in the L2N RAM table, 14 rows) and HF7_H43 (half-frame
photo-1 small image side bands at H43), with the 242 diagnostic rows.
--profile merged-r1-fold-a-zoom writes generation 243: 241 plus the same two
changes, no diagnostics.
--profile merged-r1-fold-a-cand writes generation 244 (daily candidate): 241 plus
HF7_H43, HF8_UNDO15 (half-frame bars off from the shutter word 15) and L2N_R2V2
(XPan review bands R2 v2, 3 L2N rows, 32-bit table masks). No zoom, no diagnostics.
--profile merged-r1d-fold-a-cand writes generation 245 (test): 244 plus
XPAN_ZOOM_R2 (zoom plan B + Z7, three `nop || mul` words re-encoded as `mul || nop`)
and HF8_DIAG (rows Z z A a h k x y H R P Q X; S, Z, U and hf5_scan_z dropped).

The compile still defines G175_BOOT and G175_DIAG_SILENT. Both recorded
builds used those macros; the generation field in the DAT header is separate.
A profile may add defines. g188-r2 adds none, so its command line stays the
recorded one.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import types
import zlib


MAIN = Path(__file__).resolve().parent
PROFILES = {
    "daily": {
        "generation": 185,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
    },
    "g188-r2": {
        "generation": 188,
        "seed_prefix": "research/boot_copyright_g188_r2/local/engine",
    },
    "g188-r3": {
        "generation": 214,
        "seed_prefix": "research/g188_r3/local/engine",
        "defines": ["-DG188_R3=1"],
    },
    "user-slots-r4": {
        "generation": 216,
        "seed_prefix": "research/user_slots_r4/local/engine",
        "defines": ["-DG188_R3=1", "-DUSER_SLOTS_R4=1"],
    },
    "xpan-d123-r1": {
        "generation": 218,
        "seed_prefix": "research/xpan_d123_fix/local/engine",
        "defines": ["-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D2_DIAG=1"],
    },
    "xpan-d123-r1-nodiag": {
        "generation": 219,
        "seed_prefix": "research/xpan_d123_fix/local/engine-nodiag",
        "defines": ["-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1"],
    },
    "xpan-d123-r2": {
        "generation": 220,
        "seed_prefix": "research/xpan_d123_fix_r2/local/engine",
        "defines": ["-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D2_DIAG=1", "-DXPAN_D1_R2=1"],
    },
    "xpan-d123-r2-nodiag": {
        "generation": 221,
        "seed_prefix": "research/xpan_d123_fix_r2/local/engine-nodiag",
        "defines": ["-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1"],
    },
    "feat-hf2d": {
        "generation": 223,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
        "defines": ["-DHF1=1", "-DHF1_DIAG=1"],
        "xdata": True,
    },
    "feat-hf2": {
        "generation": 224,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
        "defines": ["-DHF1=1"],
        "xdata": True,
    },
    "feat-hf3d": {
        "generation": 225,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
        "defines": ["-DHF1=1", "-DHF1_DIAG=1", "-DHF3=1"],
        "xdata": True,
    },
    "feat-hf3": {
        "generation": 226,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
        "defines": ["-DHF1=1", "-DHF3=1"],
        "xdata": True,
    },
    "feat-hf4d": {
        "generation": 227,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
        "defines": ["-DHF1=1", "-DHF1_DIAG=1", "-DHF3=1", "-DHF4=1"],
        "xdata": True,
    },
    "feat-hf4": {
        "generation": 228,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
        "defines": ["-DHF1=1", "-DHF3=1", "-DHF4=1"],
        "xdata": True,
    },
    "feat-hf5d": {
        "generation": 229,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
        "defines": ["-DHF1=1", "-DHF1_DIAG=1", "-DHF3=1", "-DHF4=1", "-DHF5=1", "-DHF5_H42=1"],
        "xdata": True,
    },
    "feat-hf5": {
        "generation": 230,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
        "defines": ["-DHF1=1", "-DHF3=1", "-DHF4=1", "-DHF5=1", "-DHF5_H42=1"],
        "xdata": True,
    },
    "feat-hf5d-h40": {
        "generation": 231,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
        "defines": ["-DHF1=1", "-DHF1_DIAG=1", "-DHF3=1", "-DHF4=1", "-DHF5=1"],
        "xdata": True,
    },
    "feat-hf6d": {
        "generation": 232,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
        "defines": ["-DHF1=1", "-DHF1_DIAG=1", "-DHF3=1", "-DHF4=1", "-DHF5=1", "-DHF5_H42=1", "-DHF6=1"],
        "xdata": True,
    },
    "feat-hf6": {
        "generation": 233,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
        "defines": ["-DHF1=1", "-DHF3=1", "-DHF4=1", "-DHF5=1", "-DHF5_H42=1", "-DHF6=1"],
        "xdata": True,
    },
    "feat-hf6d-h40": {
        "generation": 234,
        "seed_prefix": "research/xpan_realfix_r3/local/engine",
        "defines": ["-DHF1=1", "-DHF1_DIAG=1", "-DHF3=1", "-DHF4=1", "-DHF5=1", "-DHF6=1"],
        "xdata": True,
    },
    "merged-r1d": {
        "generation": 237,
        "seed_prefix": "research/merged_line_r1/local/engine",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF1_DIAG=1", "-DHF5_DIAG_TRIM=0", "-DHF3=1", "-DHF4=1",
            "-DHF5=1", "-DHF5_H42=1", "-DHF6=1", "-DMERGED_R1=1",
        ],
        "xdata": True,
    },
    "merged-r1": {
        "generation": 238,
        "seed_prefix": "research/merged_line_r1/local/engine-nodiag",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF3=1", "-DHF4=1", "-DHF5=1", "-DHF5_H42=1", "-DHF6=1",
            "-DMERGED_R1=1",
        ],
        "xdata": True,
    },
    "merged-r1d-fold-a": {
        "generation": 240,
        "seed_prefix": "research/merged_line_r1/local/engine",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF1_DIAG=1", "-DHF5_DIAG_TRIM=0", "-DHF3=1", "-DHF4=1",
            "-DHF5=1", "-DHF5_H42=1", "-DHF6=1", "-DMERGED_R1=1", "-DL2N_FOLD_A=1",
        ],
        "xdata": True,
        "resident_build_id": "18e530aa29a667824828e1b21d1f10b15c9b6eeee4f500d5607436583789457d",
        "resident_abi_id": "9bad13d535a686a911f246acbac36f34",
    },
    "merged-r1-fold-a": {
        "generation": 241,
        "seed_prefix": "research/merged_line_r1/local/engine-nodiag",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF3=1", "-DHF4=1", "-DHF5=1", "-DHF5_H42=1", "-DHF6=1",
            "-DMERGED_R1=1", "-DL2N_FOLD_A=1",
        ],
        "xdata": True,
        "resident_build_id": "18e530aa29a667824828e1b21d1f10b15c9b6eeee4f500d5607436583789457d",
        "resident_abi_id": "9bad13d535a686a911f246acbac36f34",
    },
    "merged-r1d-fold-a-zoom": {
        "generation": 242,
        "seed_prefix": "research/merged_line_r1/local/engine",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF1_DIAG=1", "-DHF5_DIAG_TRIM=0", "-DHF3=1", "-DHF4=1",
            "-DHF5=1", "-DHF5_H42=1", "-DHF6=1", "-DMERGED_R1=1", "-DL2N_FOLD_A=1",
            "-DXPAN_ZOOM_R1=1", "-DHF7_H43=1",
        ],
        "xdata": True,
        "resident_build_id": "18e530aa29a667824828e1b21d1f10b15c9b6eeee4f500d5607436583789457d",
        "resident_abi_id": "9bad13d535a686a911f246acbac36f34",
    },
    "merged-r1-fold-a-zoom": {
        "generation": 243,
        "seed_prefix": "research/merged_line_r1/local/engine-nodiag",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF3=1", "-DHF4=1", "-DHF5=1", "-DHF5_H42=1", "-DHF6=1",
            "-DMERGED_R1=1", "-DL2N_FOLD_A=1", "-DXPAN_ZOOM_R1=1", "-DHF7_H43=1",
        ],
        "xdata": True,
        "resident_build_id": "18e530aa29a667824828e1b21d1f10b15c9b6eeee4f500d5607436583789457d",
        "resident_abi_id": "9bad13d535a686a911f246acbac36f34",
    },
    "merged-r1-fold-a-cand": {
        "generation": 244,
        "seed_prefix": "research/merged_line_r1/local/engine-nodiag",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF3=1", "-DHF4=1", "-DHF5=1", "-DHF5_H42=1", "-DHF6=1",
            "-DMERGED_R1=1", "-DL2N_FOLD_A=1", "-DHF7_H43=1", "-DHF8_UNDO15=1",
            "-DL2N_R2V2=1",
        ],
        "xdata": True,
        "resident_build_id": "18e530aa29a667824828e1b21d1f10b15c9b6eeee4f500d5607436583789457d",
        "resident_abi_id": "9bad13d535a686a911f246acbac36f34",
    },
    "merged-r1d-fold-a-cand": {
        "generation": 245,
        "seed_prefix": "research/merged_line_r1/local/engine",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF1_DIAG=1", "-DHF5_DIAG_TRIM=0", "-DHF3=1", "-DHF4=1",
            "-DHF5=1", "-DHF5_H42=1", "-DHF6=1", "-DMERGED_R1=1", "-DL2N_FOLD_A=1",
            "-DHF7_H43=1", "-DHF8_UNDO15=1", "-DL2N_R2V2=1", "-DXPAN_ZOOM_R2=1",
            "-DHF8_DIAG=1",
        ],
        "xdata": True,
        "resident_build_id": "18e530aa29a667824828e1b21d1f10b15c9b6eeee4f500d5607436583789457d",
        "resident_abi_id": "9bad13d535a686a911f246acbac36f34",
    },
    "merged-r1-fold-a-hf9": {
        "generation": 246,
        "seed_prefix": "research/merged_line_r1/local/engine-nodiag",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF3=1", "-DHF4=1", "-DHF5=1", "-DHF5_H42=1", "-DHF6=1",
            "-DMERGED_R1=1", "-DL2N_FOLD_A=1", "-DHF7_H43=1", "-DHF8_UNDO15=1",
            "-DL2N_R2V2=1", "-DXPAN_ZOOM_R2=1", "-DHF9_REVIEW=1",
        ],
        "xdata": True,
        "resident_build_id": "18e530aa29a667824828e1b21d1f10b15c9b6eeee4f500d5607436583789457d",
        "resident_abi_id": "9bad13d535a686a911f246acbac36f34",
    },
    "merged-r1d-fold-a-hf9": {
        "generation": 247,
        "seed_prefix": "research/merged_line_r1/local/engine",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF1_DIAG=1", "-DHF5_DIAG_TRIM=2", "-DHF3=1", "-DHF4=1",
            "-DHF5=1", "-DHF5_H42=1", "-DHF6=1", "-DMERGED_R1=1", "-DL2N_FOLD_A=1",
            "-DHF7_H43=1", "-DHF8_UNDO15=1", "-DL2N_R2V2=1", "-DXPAN_ZOOM_R2=1",
            "-DHF8_DIAG=1", "-DHF9_REVIEW=1", "-DHF9_DIAG=1", "-DHF9_DIAG_TRIM=3",
        ],
        "xdata": True,
        "resident_build_id": "18e530aa29a667824828e1b21d1f10b15c9b6eeee4f500d5607436583789457d",
        "resident_abi_id": "9bad13d535a686a911f246acbac36f34",
    },
    "merged-r1-fold-a-hf9c": {
        "generation": 248,
        "seed_prefix": "research/merged_line_r1/local/engine-nodiag",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF3=1", "-DHF4=1", "-DHF5=1", "-DHF5_H42=1", "-DHF6=1",
            "-DMERGED_R1=1", "-DL2N_FOLD_A=1", "-DHF7_H43=1", "-DHF8_UNDO15=1",
            "-DL2N_R2V2=1", "-DXPAN_ZOOM_R2=1", "-DHF9_REVIEW=1", "-DHF9_CHECKED=1",
        ],
        "xdata": True,
        "resident_build_id": "18e530aa29a667824828e1b21d1f10b15c9b6eeee4f500d5607436583789457d",
        "resident_abi_id": "9bad13d535a686a911f246acbac36f34",
    },
    "merged-r1d-fold-a-hf9c": {
        "generation": 249,
        "seed_prefix": "research/merged_line_r1/local/engine",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF1_DIAG=1", "-DHF5_DIAG_TRIM=2", "-DHF3=1", "-DHF4=1",
            "-DHF5=1", "-DHF5_H42=1", "-DHF6=1", "-DMERGED_R1=1", "-DL2N_FOLD_A=1",
            "-DHF7_H43=1", "-DHF8_UNDO15=1", "-DL2N_R2V2=1", "-DXPAN_ZOOM_R2=1",
            "-DHF8_DIAG=1", "-DHF9_REVIEW=1", "-DHF9_DIAG=1", "-DHF9_DIAG_TRIM=3", "-DHF9_CHECKED=1",
        ],
        "xdata": True,
        "resident_build_id": "18e530aa29a667824828e1b21d1f10b15c9b6eeee4f500d5607436583789457d",
        "resident_abi_id": "9bad13d535a686a911f246acbac36f34",
    },
    "merged-r1-fold-a-hf10": {
        "generation": 250,
        "seed_prefix": "research/merged_line_r1/local/engine-nodiag",
        "defines": [
            "-DG188_R3=1", "-DUSER_SLOTS_R4=1", "-DXPAN_D123_R1=1", "-DXPAN_D1_R2=1",
            "-DHF1=1", "-DHF3=1", "-DHF4=1", "-DHF5=1", "-DHF5_H42=1", "-DHF6=1",
            "-DMERGED_R1=1", "-DL2N_FOLD_A=1", "-DHF7_H43=1", "-DHF8_UNDO15=1",
            "-DL2N_R2V2=1", "-DXPAN_ZOOM_R2=1", "-DHF9_REVIEW=1", "-DHF9_CHECKED=1",
            "-DHF10_SEAM25=1", "-DHF10_PORTRAIT=1", "-DHF10_REVIEW=1",
        ],
        "xdata": True,
        "resident_build_id": "18e530aa29a667824828e1b21d1f10b15c9b6eeee4f500d5607436583789457d",
        "resident_abi_id": "9bad13d535a686a911f246acbac36f34",
    },
}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_path(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def private_root(args):
    chosen = args.private_root or os.environ.get("GXR_PRIVATE_ROOT") or default_private_root()
    if not chosen:
        raise SystemExit("set GXR_PRIVATE_ROOT or pass --private-root (no Git checkout found)")
    root = Path(chosen).resolve()
    if not (root / "tools/loadgate.py").is_file():
        raise SystemExit("GXR_PRIVATE_ROOT is not the project checkout: " + str(root))
    return root


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


def admit(private):
    sys.path.insert(0, str(private / "tools"))
    import loadgate
    workers, gate = loadgate.workers()
    print(json.dumps({
        "admit": bool(workers),
        "workers": workers,
        "idle_cores": gate.get("idle_cores"),
        "mem_free": gate.get("mem_free"),
    }), flush=True)
    if not workers:
        raise SystemExit(75)
    os.environ.setdefault("BODY_R5_RSS_LIMIT_MIB", "1536")
    if os.getpriority(os.PRIO_PROCESS, 0) < 15:
        os.nice(15)


def seal(blob):
    raw = bytearray(blob)
    struct.pack_into(">I", raw, 16, len(raw))
    struct.pack_into(">I", raw, 24, zlib.crc32(raw[256:]))
    raw[20:24] = bytes(4)
    struct.pack_into(">I", raw, 20, zlib.crc32(raw[:256]))
    return bytes(raw)


def stage_sources(out, seed_prefix):
    dest = out / "stage" / seed_prefix
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(MAIN / "engine", dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    overlay = MAIN / "local" / "engine"
    if not overlay.is_dir():
        raise SystemExit("missing local overlay; run prepare_local.py first")
    copied = 0
    for src in overlay.rglob("*"):
        if not src.is_file() or src.name == "eng_core.c":
            continue
        target = dest / src.relative_to(overlay)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        copied += 1
    if copied == 0:
        raise SystemExit("local overlay is empty; run prepare_local.py first")
    return dest


def compile_engine(engine, stage_root, private, log_dir, prefix, defines=(), xdata=False):
    candidate = engine / "candidate"
    resident = engine / "resident"
    product = candidate / "containers" / "product"
    gcc = private / "research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc"
    ld = private / "research/tooling_m32r_asm/prefix/bin/m32r-elf-ld"
    objdump = private / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"
    for tool in (gcc, ld, objdump):
        if not tool.is_file():
            raise SystemExit("missing toolchain: " + str(tool))
    log_dir.mkdir(parents=True, exist_ok=True)

    def run(cmd, label, timeout=1800):
        logfile = log_dir / (prefix + label + ".log")
        if logfile.exists():
            raise SystemExit("log already exists: " + str(logfile))
        result = subprocess.run(
            list(map(str, cmd)), cwd=private, capture_output=True, text=True, timeout=timeout)
        logfile.write_text(result.stdout + result.stderr)
        if result.returncode:
            tail = (result.stderr or result.stdout)[-1800:]
            raise RuntimeError(label + ": " + str(result.returncode) + " " + tail)
        return result

    def loader(path, name):
        path = Path(path)
        if name == "approved_service_profile":
            path = private / "firmware/resident_v37/resident/build.py"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    def file_sha(value):
        if isinstance(value, (str, Path)):
            return sha256_path(value)
        return sha256_bytes(value)

    common = types.ModuleType("common")
    for key, value in dict(
        ROOT=stage_root, HERE=candidate, LOCAL=candidate / "local", RESIDENT=resident,
        GCC=gcc, LD=ld, OBJDUMP=objdump, guard=lambda: None, run=run, sha=file_sha, load=loader,
    ).items():
        setattr(common, key, value)
    common.LOCAL.mkdir(parents=True, exist_ok=True)
    sys.modules["common"] = common
    print(json.dumps({"phase": "service-library"}), flush=True)
    service = loader(candidate / "service_build.py", prefix + "services")
    service.LOCAL.mkdir(parents=True, exist_ok=True)
    reader = loader(private / "firmware/stage2l_switch/tools/build.py", prefix + "elf")
    service.engine_library(reader)

    runtime = types.ModuleType("runtime")
    for key, value in dict(
        HERE=product, ROOT=private, PUBLIC=MAIN, LOCAL=candidate / "local" / "product", SRC=product / "src",
        GCC=gcc, LD=ld, OBJDUMP=objdump, guard=lambda: None, load=loader, run=run, sha=file_sha,
    ).items():
        setattr(runtime, key, value)
    runtime.LOCAL.mkdir(parents=True, exist_ok=True)
    sys.modules["runtime"] = runtime
    print(json.dumps({"phase": "product-link"}), flush=True)
    builder = loader(product / "build.py", prefix + "product")
    builder.FLAGS += ["-DG175_BOOT=1", "-DG175_DIAG_SILENT=21"] + list(defines)
    builder.XDATA = bool(xdata)
    original = builder.sources

    def sources():
        rows = []
        for path, service_flag in original():
            if path.name == "shared.c":
                path = resident / "shared.c"
            rows.append((path, service_flag))
        for name in ("fx_store.c", "fx_platform.c", "fx_image.c", "fx_kernel.c"):
            rows.append((product / name, False))
        if any("HF1" in item for item in defines):
            rows.append((product / "hf1.c", False))
        return rows

    builder.sources = sources
    layout = builder.build(0, True, "oz")
    built = runtime.LOCAL / "m32r-lto-oz"
    return built, layout


def daily_expect(private):
    text = (private / "docs/DAILY.md").read_text()
    match = re.search(
        r"GXRCE\.DAT`\s*\|\s*\S+\s*`([0-9a-f]{64})`(?:，([0-9,]+)\s*B)?", text)
    if not match:
        raise SystemExit("docs/DAILY.md has no GXRCE.DAT hash")
    expect = match.group(1)
    size = int(match.group(2).replace(",", "")) if match.group(2) else None
    return expect, size


def pack(out, generation, built, layout, profile=None):
    header_path = MAIN / "local" / "inputs" / "g178-header.bin"
    header = bytearray(header_path.read_bytes())
    if len(header) != 256 or not bytes(header).startswith(b"GXRCE001"):
        raise SystemExit("local header is not the 256-byte g178 prefix")
    if profile and profile.get("resident_build_id"):
        build_id = bytes.fromhex(profile["resident_build_id"])
        assert len(build_id) == 32
        header[80:112] = build_id
    if profile and profile.get("resident_abi_id"):
        abi_id = bytes.fromhex(profile["resident_abi_id"])
        assert len(abi_id) == 16
        header[212:228] = abi_id
    engine = (built / "engine.bin").read_bytes()
    reloc = (built / "reloc.bin").read_bytes()
    xpath = built / "xdata.bin"
    xdata = xpath.read_bytes() if layout.get("xdata_bytes") else b""
    if len(xdata) != layout.get("xdata_bytes", 0) or len(xdata) % 4:
        raise SystemExit("xdata.bin does not match the link layout")
    struct.pack_into(">I", header, 28, generation)
    struct.pack_into(
        ">IIH", header, 112, layout["entries"]["ig_bootstrap"], layout["bss_bytes"], len(reloc) // 8)
    parts = [engine, reloc, xdata] + [b""] * 4
    if xdata and 256 + len(engine) + len(reloc) != layout["xdata_start"]:
        raise SystemExit("xdata is not linked where section 3 lands")
    at = 256
    for index, part in enumerate(parts):
        struct.pack_into(">II", header, 132 + 12 * index, at, len(part))
        at += len(part)
    dat = seal(bytes(header) + b"".join(parts))
    dat_path = out / "GXRCE.DAT"
    dat_path.write_bytes(dat)
    names = ["engine.bin", "reloc.bin", "engine.elf", "engine.map", "size.json", "relocations.json"]
    if xdata:
        names.append("xdata.bin")
    for name in names:
        shutil.copyfile(built / name, out / name)
    return dat


def main():
    parser = argparse.ArgumentParser(description="Build the mainline engine DAT")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="daily")
    parser.add_argument("--private-root")
    parser.add_argument("--out", type=Path, help="output directory; default local/build/<profile>")
    parser.add_argument("--verify", action="store_true", help="compare the DAT with docs/DAILY.md")
    parser.add_argument("--verify-against", type=Path, help="compare the DAT with this file")
    args = parser.parse_args()
    if not sys.flags.isolated or not sys.dont_write_bytecode:
        raise SystemExit("run with python3 -I -B")
    private = private_root(args)
    workspace_guard = assert_workspace(private)
    print(json.dumps({"workspace_guard": workspace_guard}), flush=True)
    profile = PROFILES[args.profile]
    out = (args.out or (MAIN / "local" / "build" / args.profile)).resolve()
    if (out / "GXRCE.DAT").exists():
        raise SystemExit("output already exists: " + str(out / "GXRCE.DAT"))
    out.mkdir(parents=True, exist_ok=True)
    admit(private)
    engine = stage_sources(out, profile["seed_prefix"])
    stage_root = out / "stage"
    try:
        built, layout = compile_engine(
            engine, stage_root, private, out / "logs", args.profile + "-",
            profile.get("defines", ()), profile.get("xdata", False))
    except RuntimeError as exc:
        text = str(exc)
        found = re.search(r"\.engine VMA \[([0-9a-fA-F]+),([0-9a-fA-F]+)\]", text)
        if found and args.profile in ("feat-hf2d", "feat-hf2", "feat-hf3d", "feat-hf3", "feat-hf4d", "feat-hf4", "feat-hf5d", "feat-hf5", "feat-hf5d-h40", "feat-hf6d", "feat-hf6", "feat-hf6d-h40", "merged-r1d", "merged-r1", "merged-r1d-fold-a", "merged-r1-fold-a", "merged-r1d-fold-a-zoom", "merged-r1-fold-a-zoom", "merged-r1-fold-a-cand", "merged-r1d-fold-a-cand", "merged-r1-fold-a-hf9", "merged-r1d-fold-a-hf9", "merged-r1-fold-a-hf9c", "merged-r1d-fold-a-hf9c", "merged-r1-fold-a-hf10"):
            nbytes = int(found.group(2), 16) - int(found.group(1), 16)
            hard = 98304 if args.profile.startswith("merged-") else 81920
            target = 98304 if args.profile.startswith("merged-") else 81700
            print(json.dumps({
                "engine_bytes": nbytes,
                "engine_cap_target": target,
                "engine_cap_hard": hard,
                "engine_under_target": nbytes <= target,
                "engine_under_hard": nbytes <= hard,
                "link": "failed",
            }), flush=True)
        raise
    dat = pack(out, profile["generation"], built, layout, profile)
    main_request = 7628 + ((len(dat) + layout["bss_bytes"] + 3) & ~3)
    if len(dat) > 98304 or len(dat) + layout["bss_bytes"] > 114688 or main_request > 107612:
        raise SystemExit(
            f"mainline size limit exceeded: dat={len(dat)} (<=98304), "
            f"image+bss={len(dat) + layout['bss_bytes']} (<=114688), "
            f"main_request={main_request} (<=107612)"
        )
    info = {
        "profile": args.profile,
        "generation": profile["generation"],
        "dat_bytes": len(dat),
        "dat_sha256": sha256_bytes(dat),
        "engine_bytes": layout["engine_bytes"],
        "engine_sha256": sha256_path(out / "engine.bin"),
        "bss_bytes": layout["bss_bytes"],
        "main_request": main_request,
        "relocations": layout["relocations"],
    }
    if layout.get("xdata_bytes"):
        info["xdata_bytes"] = layout["xdata_bytes"]
        info["xdata_start"] = layout["xdata_start"]
    if args.profile in ("feat-hf2d", "feat-hf2", "feat-hf3d", "feat-hf3", "feat-hf4d", "feat-hf4", "feat-hf5d", "feat-hf5", "feat-hf5d-h40", "feat-hf6d", "feat-hf6", "feat-hf6d-h40", "merged-r1d", "merged-r1", "merged-r1d-fold-a", "merged-r1-fold-a", "merged-r1d-fold-a-zoom", "merged-r1-fold-a-zoom", "merged-r1-fold-a-cand", "merged-r1d-fold-a-cand", "merged-r1-fold-a-hf9", "merged-r1d-fold-a-hf9", "merged-r1-fold-a-hf9c", "merged-r1d-fold-a-hf9c", "merged-r1-fold-a-hf10"):
        eng = info["engine_bytes"]
        main_request = 7628 + ((info["dat_bytes"] + info["bss_bytes"] + 3) & ~3)
        hard = 98304 if args.profile.startswith("merged-") else 81920
        target = 98304 if args.profile.startswith("merged-") else 81700
        info["engine_cap_target"] = target
        info["engine_cap_hard"] = hard
        info["engine_under_target"] = eng <= target
        info["engine_under_hard"] = eng <= hard
        info["main_request"] = main_request
        info["main_request_cap"] = 107612
        info["main_request_under_cap"] = main_request <= 107612
    if args.verify:
        expect, size = daily_expect(private)
        info["daily_sha256"] = expect
        info["daily_bytes"] = size
        info["verified"] = info["dat_sha256"] == expect and (size is None or size == len(dat))
        if not info["verified"]:
            print(json.dumps(info, indent=2), flush=True)
            raise SystemExit(1)
    if args.verify_against:
        other = args.verify_against.read_bytes()
        info["against_sha256"] = sha256_bytes(other)
        info["against_bytes"] = len(other)
        info["against_verified"] = other == dat
        if not info["against_verified"]:
            print(json.dumps(info, indent=2), flush=True)
            raise SystemExit(1)
    (out / "BUILD.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2), flush=True)


if __name__ == "__main__":
    main()
