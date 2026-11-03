"""Offline research I/O and read-only adapters for the frozen response model."""
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
R7 = ROOT / 'research/refit_50mm_r7'
DATA = ROOT / 'research/chart_session_20261024/local/moire-review-v2/exchange-jpeg6/50mm'
info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
assert Path('/Volumes/Workspace').is_mount() and info['FilesystemType'] == 'apfs'
assert info['VolumeUUID'].upper() == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
assert info['WritableVolume'] and info['WritableMedia'] and not HERE.is_symlink()
LOCAL.mkdir(exist_ok=True)
(LOCAL / 'tmp').mkdir(exist_ok=True)
subprocess.run(['git', 'check-ignore', '-q', str(LOCAL / 'guard')], cwd=ROOT, check=True)
for key in ('TMPDIR', 'TMP', 'TEMP', 'MPLCONFIGDIR'):
    os.environ[key] = str(LOCAL / 'tmp')
for key in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
INPUTS = json.loads((LOCAL / 'inputs.json').read_text()) if (LOCAL / 'inputs.json').exists() else {}
WRITES = set()
EXCLUDED = ROOT / 'research/hw_mining_r3'


def audit(event, args):
    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('offline research only')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        p = Path(os.fsdecode(args[0])).resolve()
        if p.is_relative_to(EXCLUDED):
            raise PermissionError('excluded research directory')
        mode, flags = args[1:3]
        writing = isinstance(mode, str) and any(c in mode for c in 'wax+')
        writing |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing:
            if not p.is_relative_to(HERE):
                raise PermissionError('write outside research output')
            WRITES.add(str(p.relative_to(HERE)))
        if str(p).startswith('/Volumes/') and not p.is_relative_to(ROOT):
            raise PermissionError('read outside named checkout')
        if str(p).startswith('/dev/') and str(p) not in ('/dev/null', '/dev/urandom', '/dev/random'):
            raise PermissionError('device access is outside scope')
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename', 'os.symlink', 'os.link', 'os.chmod', 'os.utime'):
        for p in args[:2] if event in ('os.rename', 'os.link', 'os.symlink') else args[:1]:
            if isinstance(p, (str, bytes, Path)) and not Path(os.fsdecode(p)).resolve().is_relative_to(HERE):
                raise PermissionError('mutation outside research output')


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
    if not p.is_relative_to(ROOT) or p.is_relative_to(EXCLUDED) or not p.is_file():
        raise ValueError('input outside research scope')
    if not p.is_relative_to(HERE):
        key, digest = str(p.relative_to(ROOT)), sha(p)
        if key in INPUTS and INPUTS[key] != digest:
            raise ValueError('frozen input changed: ' + key)
        if expected is not None and digest != expected:
            raise ValueError('input hash mismatch: ' + key)
        INPUTS[key] = digest
    return p


def read(path):
    return json.loads(inp(path).read_text())


def arrays(path):
    with np.load(inp(path), allow_pickle=False) as z:
        return dict(z)


def plain(v):
    if isinstance(v, dict): return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [plain(x) for x in v]
    if isinstance(v, np.ndarray): return plain(v.tolist())
    if isinstance(v, np.generic): return v.item()
    if isinstance(v, Path): return str(v)
    return v


def dump(path, value):
    p = Path(path)
    p = LOCAL / p if not p.is_absolute() else p
    assert p.resolve().is_relative_to(HERE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def module(name, path):
    p = inp(path)
    if p.is_relative_to(ROOT / 'artifacts/downloads'):
        raise PermissionError('reference source is data only')
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def finish(tag='exit'):
    changed = [p for p, h in INPUTS.items() if sha(ROOT / p) != h]
    assert not changed, changed
    dump('inputs.json', INPUTS)
    dump('boundaries/' + tag + '.json', dict(all_inputs_unchanged=True, input_count=len(INPUTS), writes=sorted(WRITES)))


atexit.register(finish)
sys.modules['runtime'] = sys.modules[__name__]
s = module('support', 'research/module_adapt/support.py')
s.HERE, s.LOCAL, s.source, s.digest = HERE, LOCAL, inp, sha
common = module('common', 'research/closed_loop/common.py')
common.input_path, common.read, common.sha = inp, read, sha
common.SCRATCH = LOCAL / 'tmp'
sys.path.insert(0, str(ROOT / 'research/module_adapt'))
um = module('unit_model', 'research/module_adapt/unit_model.py')
calibrate = module('calibrate', 'research/module_adapt/calibrate.py')
f = module('refit', 'research/refit_50mm_r7/refit.py')
cm = module('colour_math', 'research/color_references/colour_math.py')
old = module('mcr_frozen_hw_model', 'research/hw_refit_r1/model.py')


def model():
    return um.UnitModel('50mm', iso=200)
