#!/usr/bin/env python3
"""Prepare the identified card only after final package and review receipts match."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CARD = Path("/Volumes/RICOHDCX")
CARD_UUID = "0F824AED-99E3-397F-AC62-EFC0D90DD373"
TARGETS = ("ilaunch3", "DEEPTBL0.DAT", "DEEPTBL1.DAT")


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def card_info():
    info = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", str(CARD)]))
    assert info["VolumeUUID"] == CARD_UUID and info["WritableVolume"]
    assert info["MountPoint"] == str(CARD) and info["FilesystemType"] == "msdos"
    return info


def photos():
    return {str(path.relative_to(CARD)): digest(path)
            for path in sorted((CARD / "DCIM").rglob("*")) if path.is_file()}


def main():
    volume = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", "/Volumes/Workspace"]))
    assert volume["VolumeUUID"] == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
    assert volume["FilesystemType"] == "apfs" and volume["WritableVolume"]
    release = json.loads((HERE / "local/release.json").read_text())
    assert release["status"] == "REVIEWED_LOCAL_CANDIDATE_NOT_CAMERA_ACCEPTED"
    assert release["R_all_restored_user_confirmed"] is True
    package = (ROOT / release["package"]).resolve()
    assert package.is_relative_to(ROOT / "artifacts/stage2l-switch-packages")
    assert not (package.parent / ("BLOCKED-" + release["image_sha256"][:12] + ".json")).exists()
    review = (ROOT / release["review"]).resolve()
    assert review.is_relative_to(HERE) and digest(review) == release["review_sha256"]
    for name, expected in release["reviewed_files_sha256"].items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and digest(path) == expected, name
    spec = importlib.util.spec_from_file_location("switch_pre_card_audit", HERE / "audit_package.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    assert audit.PACKAGE == package and audit.IMAGE_SHA == release["image_sha256"]
    audit.main()
    candidate = package / "candidate/SD_ROOT"
    pointer = json.loads((HERE / "local/card-backup-pointer.json").read_text())
    backup = (ROOT / pointer["backup"]).resolve()
    assert backup.is_relative_to(ROOT / "artifacts/stage2l-switch-packages")
    before = json.loads((backup / "readback.json").read_text())
    assert before["card_uuid"] == CARD_UUID
    card_info()
    assert photos() == before["dcim_sha256"], "card photos changed since read-only backup"
    root_files = {p.name for p in CARD.iterdir() if p.is_file() and not p.name.startswith(".")}
    assert root_files in (set(before["root_files"]), set(before["root_files"]) - {"P"})
    for name, record in before["root_files"].items():
        if name == "P" and not (CARD / name).exists():
            continue
        allowed = {record["sha256"]}
        if name in TARGETS:
            allowed.add(digest(candidate / name))
        assert digest(CARD / name) in allowed, f"unexpected current card file: {name}"
    for source in candidate.iterdir():
        if source.name not in TARGETS:
            assert digest(CARD / source.name) == digest(source), source.name
    assert shutil.disk_usage(CARD).free > max((candidate / name).stat().st_size for name in TARGETS) + 1024 * 1024
    for name in TARGETS:
        card_info()
        source, target = candidate / name, CARD / name
        if digest(target) == digest(source):
            continue
        staging = CARD / (".stage2l-switch-" + name + ".tmp")
        assert not staging.exists() or digest(staging) == digest(source), "unrecognized staging file"
        data = source.read_bytes()
        with staging.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        assert digest(staging) == digest(source)
        os.replace(staging, target)
        assert digest(target) == digest(source)
    for source in candidate.iterdir():
        assert digest(CARD / source.name) == digest(source), source.name
    assert digest(CARD / "ilaunch3") == release["image_sha256"]
    card_info()
    if (CARD / "P").exists():
        assert digest(CARD / "P") == before["root_files"]["P"]["sha256"]
        (CARD / "P").unlink()
    assert photos() == before["dcim_sha256"], "photo readback differs"
    for name, record in before["root_files"].items():
        if name not in (*TARGETS, "P"):
            assert digest(CARD / name) == record["sha256"], name
    subprocess.run(["sync"], check=True)
    card_info()
    receipt = dict(status="CARD_PREPARED_AWAITING_CAMERA", time_utc=datetime.now(timezone.utc).isoformat(),
                   card_uuid=CARD_UUID, package=release["package"], image_sha256=release["image_sha256"],
                   backup=pointer["backup"], package_files_verified=35, dcim_files_unchanged=len(before["dcim_sha256"]),
                   changed_files=list(TARGETS), removed_file="P (backed up R-all)",
                   other_root_files_unchanged=True, camera_executed=False, safely_ejected=False)
    output = HERE / "local/card-prepared.json"
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    subprocess.run(["diskutil", "eject", str(CARD)], check=True, capture_output=True, text=True)
    receipt["safely_ejected"] = True
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
