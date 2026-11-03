"""Shared paths, output fence and read-only module loading for the T1 v2 probe."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = HERE / "local"
PACKAGE = ROOT / "artifacts/stage2j-packages/tables-v3-probe2"
RAW_PACKAGE = PACKAGE / "local"
BASE = ROOT / "artifacts/stage2j-packages/tables-v3"
SCRATCH = Path("/tmp/t1p2")
BASE_SHA = "9f6b727fa9bf84b09b030a93338d0eaf49f7da2117278309c3683bf0c99bb2b1"
CAP = ROOT / "captures/a12-50/2026-10-20/stage2j-v1-calibration"
MODEL = ROOT / "research/hue_ring/local/ring_model_v2.json"
V2_CODE = ROOT / "research/hue_ring/local/calibration_20261020/followup_v2/code"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, Path(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jsonable(value):
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "tolist"):
        return jsonable(value.tolist())
    return value


def save(path, data):
    path = Path(path).resolve()
    require(any(path.is_relative_to(p.resolve()) for p in (HERE, PACKAGE, SCRATCH)),
            f"output outside authorized directories: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def dump(path, value):
    save(path, json.dumps(jsonable(value), ensure_ascii=False, indent=2,
                          allow_nan=False) + "\n")


def ignored(path):
    require(subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=ROOT).returncode == 0,
            f"private data is not git-ignored: {path}")


def preflight():
    p = subprocess.run(["diskutil", "info", "-plist", "/Volumes/Workspace"],
                       check=True, capture_output=True)
    info = plistlib.loads(p.stdout)
    require(info["MountPoint"] == "/Volumes/Workspace" and
            info["VolumeUUID"] == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8" and
            info["FilesystemType"] == "apfs" and info["WritableVolume"] and
            info["WritableMedia"] and os.access("/Volumes/Workspace", os.W_OK),
            "Workspace volume identity or writability mismatch")
    df = subprocess.run(["df", "-h", "/Volumes/Workspace"],
                        check=True, capture_output=True, text=True).stdout
    ignored(LOCAL / "test.json")
    ignored(RAW_PACKAGE / "DEEPTBL0.DAT")
    save(LOCAL / "df.txt", df)
    dump(LOCAL / "volume.json", {k: info[k] for k in (
        "MountPoint", "VolumeUUID", "FilesystemType", "WritableVolume", "WritableMedia")})


def generator():
    return load("t1p2_generator", ROOT / "firmware/stage2j/tools/make_table_files.py").src


def source_manifest(paths):
    return {str(Path(p).relative_to(ROOT)): sha(p) for p in sorted(set(map(Path, paths)))}
