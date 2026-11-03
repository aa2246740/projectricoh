"""Scoped, read-only-input research utilities. Run every entry point with -I -B."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import fcntl

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
DOWNLOADS = ROOT / 'artifacts/downloads/bridge_public_r1'
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[key] = '1'
for key in ('TMPDIR', 'TMP', 'TEMP', 'MPLCONFIGDIR'):
    os.environ[key] = str(LOCAL / 'tmp')
info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
assert info['FilesystemType'] == 'apfs' and info['WritableVolume'] and Path('/Volumes/Workspace').is_mount()
LOCAL.mkdir(exist_ok=True)
(LOCAL / 'tmp').mkdir(exist_ok=True)
DOWNLOADS.mkdir(parents=True, exist_ok=True)
NETWORK = False


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def plain(x):
    if isinstance(x, dict): return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, (tuple, list)): return [plain(v) for v in x]
    if hasattr(x, 'tolist'): return plain(x.tolist())
    if isinstance(x, Path): return str(x)
    return x


def dump(path, value):
    path = Path(path)
    if not path.is_absolute(): path = LOCAL / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


_manifest = LOCAL / 'inputs.json'
_inputs = json.loads(_manifest.read_text()) if _manifest.exists() else {}


def inp(path):
    p = Path(path)
    if not p.is_absolute(): p = ROOT / p
    p = p.resolve()
    assert p.is_relative_to(ROOT) and p.is_file(), p
    assert p.name != 'decisions.tsv', 'orchestrator log is not an input'
    assert not any(p.is_relative_to(ROOT / d) for d in ('firmware/engine_v36_r28', 'firmware/lut_p0_timing'))
    if p.is_relative_to(HERE) or p.is_relative_to(DOWNLOADS): return p
    key = str(p.relative_to(ROOT)); digest = sha(p)
    if key in _inputs:
        if digest != _inputs[key]: raise SystemExit('STOP: FROZEN PROTECTED INPUT CHANGED: ' + key)
    else:
        with (LOCAL / '.inputs.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            latest=json.loads(_manifest.read_text()) if _manifest.exists() else {}
            if key in latest and latest[key]!=digest:
                raise SystemExit('STOP: FROZEN PROTECTED INPUT CHANGED: '+key)
            for known,value in _inputs.items():
                if known in latest and latest[known]!=value:
                    raise SystemExit('STOP: FROZEN PROTECTED INPUT CHANGED: '+known)
                latest[known]=value
            latest[key]=digest
            _inputs.clear();_inputs.update(latest);dump(_manifest,_inputs)
    return p


def read(path): return json.loads(inp(path).read_text())


def module(name, path):
    path = inp(path)
    assert path.suffix == '.py' and not path.is_relative_to(DOWNLOADS)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def audit(event, args):
    if event in ('socket.connect', 'socket.bind') and not NETWORK:
        raise PermissionError('offline analysis: network forbidden')
    if event == 'exec' and hasattr(args[0], 'co_filename'):
        p = Path(args[0].co_filename)
        if p.is_absolute() and p.is_relative_to(ROOT):
            if p.is_relative_to(ROOT / 'artifacts') or p.is_relative_to(ROOT / 'captures'):
                raise PermissionError('untrusted data may not execute: ' + str(p))
            if p.is_file() and not p.is_relative_to(HERE): inp(p)
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        p = Path(os.fsdecode(args[0])).resolve(); mode, flags = args[1:3]
        write = isinstance(mode, str) and any(c in mode for c in 'wax+')
        write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if write and not (p.is_relative_to(HERE) or p.is_relative_to(DOWNLOADS)):
            raise PermissionError('write outside research scope: ' + str(p))
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename'):
        for v in args[:2] if event == 'os.rename' else args[:1]:
            if isinstance(v, (str, bytes, Path)):
                p = Path(os.fsdecode(v)).resolve()
                if not (p.is_relative_to(HERE) or p.is_relative_to(DOWNLOADS)):
                    raise PermissionError('mutation outside research scope: ' + str(p))


sys.addaudithook(audit)
import numpy as np


def arrays(path):
    with np.load(inp(path), allow_pickle=False) as z: return dict(z)


def stats(x):
    x = np.asarray(x, float)
    assert np.isfinite(x).all()
    if not x.size: return {'n': 0}
    return dict(n=len(x), median=float(np.median(x)), p90=float(np.percentile(x, 90)),
                mean=float(np.mean(x)), maximum=float(np.max(x)))


def verify():
    latest=json.loads(_manifest.read_text()) if _manifest.exists() else {}
    for key,value in latest.items():
        if key in _inputs and _inputs[key]!=value:
            raise SystemExit('STOP: FROZEN PROTECTED INPUT CHANGED: '+key)
        _inputs[key]=value
    result = {k: sha(ROOT / k) == v for k, v in _inputs.items()}
    dump('frozen_verified.json', {'all_unchanged': all(result.values()), 'files': result})
    if not all(result.values()): raise SystemExit('STOP: FROZEN PROTECTED INPUT CHANGED')
    return len(result)


cm = module('bridge_public_colour_math', 'research/color_references/colour_math.py')


def lab(rgb): return cm.xyz_lab(cm.srgb_decode(np.asarray(rgb) / 255) @ cm.SRGB_XYZ.T, cm.D65)


if __name__ == '__main__':
    print('frozen protected inputs unchanged:', verify())
