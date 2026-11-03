"""Offline research boundary and frozen-input ledger. Run with python3 -I -B."""
from pathlib import Path
import atexit
import hashlib
import importlib.util
import json
import os
import sys
from mount_guard import guard

sys.dont_write_bytecode = True
guard()
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
LOCAL.mkdir(exist_ok=True)
(LOCAL / "tmp").mkdir(exist_ok=True)
for key in ("TMPDIR", "TMP", "TEMP", "MPLCONFIGDIR"):
    os.environ[key] = str(LOCAL / "tmp")
for key in ("OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
LEDGER = LOCAL / "inputs.json"
INPUTS = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
WRITES = set()


def within(path, parent):
    return path == parent or parent in path.parents


def audit(event, args):
    if event in ("socket.connect", "socket.bind", "socket.getaddrinfo"):
        raise PermissionError("offline research: network disabled")
    if event == "exec":
        name = Path(args[0].co_filename).resolve()
        if within(name, ROOT / "artifacts/downloads"):
            raise PermissionError("downloaded sources are data only")
    if event == "open" and isinstance(args[0], (str, bytes, Path)):
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        writing = isinstance(mode, str) and any(c in mode for c in "wax+")
        writing |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing:
            if not within(path, HERE):
                raise PermissionError("write outside gr4_analytic_target_r1: " + str(path))
            WRITES.add(str(path.relative_to(HERE)))
        if str(path).startswith("/Volumes/") and not within(path, ROOT):
            raise PermissionError("read outside the named checkout: " + str(path))
    if event in ("os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.symlink", "os.link", "os.chmod", "os.utime"):
        paths = args[:2] if event in ("os.rename", "os.link", "os.symlink") else args[:1]
        for value in paths:
            if isinstance(value, (str, bytes, Path)) and not within(Path(os.fsdecode(value)).resolve(), HERE):
                raise PermissionError("mutation outside output directory")


sys.addaudithook(audit)
import numpy as np


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(2 ** 20), b""):
            h.update(block)
    return h.hexdigest()


def inp(path, expected=None):
    path = Path(path)
    path = (ROOT / path if not path.is_absolute() else path).resolve()
    if not within(path, ROOT) or not path.is_file():
        raise ValueError("invalid input: " + str(path))
    if not within(path, HERE):
        key = str(path.relative_to(ROOT))
        digest = sha(path)
        if key in INPUTS and INPUTS[key] != digest:
            raise ValueError("frozen input changed: " + key)
        if expected is not None and digest != expected:
            raise ValueError("expected hash mismatch: " + key)
        INPUTS[key] = digest
    return path


def read(path, expected=None):
    return json.loads(inp(path, expected).read_text())


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def dump(path, value):
    path = LOCAL / path
    if not within(path.resolve(), HERE):
        raise ValueError("invalid output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def module(name, path):
    path = inp(path)
    if within(path, ROOT / "artifacts/downloads"):
        raise PermissionError("downloaded modules must never execute")
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def stats(values):
    values = np.asarray(values, float)
    if values.size == 0:
        return {"n": 0}
    if not np.isfinite(values).all():
        raise ValueError("nonfinite metric")
    return dict(n=values.size, median=float(np.median(values)), p90=float(np.percentile(values, 90)),
                mean=float(values.mean()), maximum=float(values.max()))


def finish():
    dump("inputs.json", INPUTS)
    dump("last_writes.json", sorted(WRITES))


atexit.register(finish)
cm = module("analytic_colour_math", "research/color_references/colour_math.py")


def lab(rgb):
    return cm.xyz_lab(cm.srgb_decode(np.clip(rgb, 0, 1)) @ cm.SRGB_XYZ.T, cm.D65)


def de(a, b):
    return cm.delta_e00(lab(a), lab(b))
