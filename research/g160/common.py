"""Offline g160 evidence tools. Firmware and derived records stay in local/."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "research/g160"
LOCAL = HERE / "local"
BASE = ROOT / "firmware/engine_v70_g158"
ENGINE = ROOT / "firmware/engine_v71_g160"
PRODUCT = BASE / "candidate/containers/product"
PACKAGES = {p: ROOT / ("firmware/package_v310_g160" + ("_test" if p == "test" else ""))
            for p in ("test", "release")}
UNITS = ("50mm", "28mm", "MOUNT")
LOCKED = ("Acros", "ARRI 709", "M9 STD", "instax mini", "HNCS HiCon", "HNCS LowSat")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + str(os.getpid()))
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def setup():
    assert sys.flags.isolated, "Run Python -I -B"
    assert os.getpriority(os.PRIO_PROCESS, 0) == 15, "Run at nice 15, without stacking nice"
    sys.dont_write_bytecode = True
    info = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", "/Volumes/Workspace"]))
    assert info["MountPoint"] == "/Volumes/Workspace" and info["FilesystemType"] == "apfs"
    assert info["VolumeUUID"] == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8" and info["WritableVolume"]
    allowed = (HERE, ENGINE, *PACKAGES.values())
    assert all(not p.is_symlink() for p in allowed)

    def audit(event, args):
        if event in ("socket.connect", "socket.bind", "socket.getaddrinfo"):
            raise PermissionError("g160 offline")
        paths = []
        if event == "open":
            path, mode, flags = args
            if isinstance(path, (str, bytes, os.PathLike)) and os.fsdecode(path).startswith(("/dev/disk", "/dev/rdisk")):
                raise PermissionError("Physical device fence")
            if ((isinstance(mode, str) and any(c in mode for c in "wax+")) or
                    flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                paths = [path]
        elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.truncate", "os.utime"):
            paths = [args[0]]
        elif event in ("os.rename", "os.link", "os.symlink"):
            paths = list(args[:2])
        for path in paths:
            if not isinstance(path, (str, bytes, os.PathLike)):
                continue
            target = Path(os.fsdecode(path)).resolve()
            if target != Path("/dev/null") and not any(target.is_relative_to(p) for p in allowed):
                raise PermissionError("g160 write fence: " + str(target))

    sys.addaudithook(audit)
    (LOCAL / "tmp").mkdir(parents=True, exist_ok=True)
    os.environ.update(TMPDIR=str(LOCAL / "tmp"), PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0",
                      CLANG_MODULE_CACHE_PATH=str(LOCAL / "tmp/modules"), OPENBLAS_NUM_THREADS="1",
                      OMP_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1", MPLCONFIGDIR=str(LOCAL / "tmp/mpl"))


def gate(label):
    sys.path.insert(0, str(ROOT / "tools"))
    import loadgate
    workers, info = loadgate.workers()
    with (LOCAL / "admissions.jsonl").open("a") as output:
        output.write(json.dumps(dict(label=label, nice=os.getpriority(os.PRIO_PROCESS, 0),
                                     pid=os.getpid(), info=info)) + "\n")
    if not workers:
        print("LOAD_DEFERRED " + json.dumps(info), flush=True)
        raise SystemExit(75)
    return workers


def baseline_dat(profile="test"):
    return ROOT / ("firmware/package_v310_g158" + ("_test" if profile == "test" else "")) / "local/SD_ROOT/GXRCE.DAT"


D = load(ROOT / "research/v39_g153/dat_format.py", "g160_dat_format")
