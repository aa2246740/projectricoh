"""Offline research I/O, input digests, and one output directory."""
from pathlib import Path
import atexit
import hashlib
import importlib.util
import json
import os
import plistlib
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
info = plistlib.loads(subprocess.check_output(
    ['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
assert Path('/Volumes/Workspace').is_mount()
assert info['FilesystemType'] == 'apfs'
assert info['VolumeUUID'].upper() == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
assert info['WritableVolume'] and info['WritableMedia'] and not HERE.is_symlink()
LOCAL.mkdir(exist_ok=True)
(LOCAL / 'tmp').mkdir(exist_ok=True)
for key in ('TMPDIR', 'TMP', 'TEMP', 'MPLCONFIGDIR'):
    os.environ[key] = str(LOCAL / 'tmp')
for key in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
LEDGER = LOCAL / 'inputs.json'
INPUTS = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
WRITES = set()


def audit(event, args):
    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('offline research: network unavailable')
    if event == 'exec' and Path(args[0].co_filename).resolve().is_relative_to(ROOT / 'artifacts/downloads'):
        raise PermissionError('downloaded material is read-only data')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        p = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        write = isinstance(mode, str) and any(c in mode for c in 'wax+')
        write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if write:
            if not p.is_relative_to(HERE):
                raise PermissionError('write outside gr4_sim_r3: ' + str(p))
            WRITES.add(str(p.relative_to(HERE)))
        if str(p).startswith('/Volumes/') and not p.is_relative_to(ROOT):
            raise PermissionError('read outside named repository: ' + str(p))
        if str(p).startswith('/dev/') and str(p) not in ('/dev/null', '/dev/random', '/dev/urandom'):
            raise PermissionError('device access unavailable')
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename', 'os.symlink', 'os.link', 'os.chmod', 'os.utime'):
        for p in args[:2] if event in ('os.rename', 'os.symlink', 'os.link') else args[:1]:
            if isinstance(p, (str, bytes, Path)) and not Path(os.fsdecode(p)).resolve().is_relative_to(HERE):
                raise PermissionError('mutation outside output directory')


sys.addaudithook(audit)
import numpy as np


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def inp(path, expected=None):
    p = Path(path)
    p = (ROOT / p if not p.is_absolute() else p).resolve()
    if not p.is_relative_to(ROOT) or not p.is_file():
        raise ValueError('invalid input: ' + str(p))
    if not p.is_relative_to(HERE):
        key, digest = str(p.relative_to(ROOT)), sha(p)
        if key in INPUTS and INPUTS[key] != digest:
            raise ValueError('frozen input changed: ' + key)
        if expected is not None and digest != expected:
            raise ValueError('expected input digest differs: ' + key)
        INPUTS[key] = digest
    return p


def read(path, expected=None):
    return json.loads(inp(path, expected).read_text())


def arrays(path):
    with np.load(inp(path), allow_pickle=False) as a:
        return dict(a)


def plain(value):
    if isinstance(value, dict): return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [plain(v) for v in value]
    if isinstance(value, np.ndarray): return plain(value.tolist())
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, Path): return str(value)
    return value


def dump(name, value):
    p = (LOCAL / name).resolve()
    if not p.is_relative_to(LOCAL): raise ValueError('local output required')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def module(name, path, rt_alias=False):
    p = inp(path)
    if p.is_relative_to(ROOT / 'artifacts/downloads'):
        raise PermissionError('downloaded material is read-only data')
    if rt_alias: sys.modules['runtime'] = sys.modules[__name__]
    spec = importlib.util.spec_from_file_location(name, p)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def stats(a):
    a = np.asarray(a, float)
    if not a.size: return {'n': 0}
    if not np.isfinite(a).all(): raise ValueError('nonfinite result')
    return dict(n=int(a.size), median=float(np.median(a)), p90=float(np.percentile(a, 90)),
                mean=float(a.mean()), maximum=float(a.max()))


def finish():
    latest = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    for name, digest in latest.items():
        if name in INPUTS and INPUTS[name] != digest:
            raise ValueError('input ledger digest differs: ' + name)
        INPUTS[name] = digest
    dump('inputs.json', INPUTS)
    dump('last_writes.json', sorted(WRITES))


atexit.register(finish)
cm = module('r3_colour_math', 'research/color_references/colour_math.py')


def lab(rgb):
    return cm.xyz_lab(cm.srgb_decode(np.clip(rgb, 0, 1)) @ cm.SRGB_XYZ.T, cm.D65)


def de(a, b):
    return cm.delta_e00(lab(a), lab(b))
