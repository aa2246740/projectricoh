"""Task fences and explicit adapters; no legacy entrypoint is run."""
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
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
RETURNS = ROOT / 'research/gr_dense_reference/local/private/gr4/r3/camera-returns-20261025-bleach'
INPUT = ROOT / 'captures/contrib/2026-10-25-gr4-wechat-nega-redo/extracted/GR4'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/gr4-bleach')
DATA = ROOT / 'research/chart_session_20261024/local/moire-review-v2/exchange-jpeg6/50mm'
for name in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
os.environ['GIT_OPTIONAL_LOCKS'] = '0'


def guard():
    d = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount() and d['MountPoint'] == '/Volumes/Workspace'
    assert d['FilesystemType'] == 'apfs' and d['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert all(d[k] for k in ('Writable', 'WritableMedia', 'WritableVolume'))
    for base in (LOCAL, RETURNS):
        assert not base.is_symlink() and base.resolve().is_relative_to(ROOT)
        subprocess.run(['git', 'check-ignore', '-q', str(base / 'probe')], cwd=ROOT, check=True)
    LOCAL.mkdir(exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for key in ('TMPDIR', 'TMP', 'TEMP', 'CLANG_MODULE_CACHE_PATH'):
        os.environ[key] = str(SCRATCH)


guard()


def audit(event, args):
    if event != 'open' or not isinstance(args[0], (str, bytes, Path)):
        return
    mode, flags = args[1:3]
    write = isinstance(mode, str) and any(c in mode for c in 'wax+')
    write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
    p = Path(os.fsdecode(args[0])).resolve()
    if str(p).startswith('/Volumes/') and not (p.is_relative_to(ROOT) or p.is_relative_to(SCRATCH)):
        raise PermissionError('read outside named checkout: ' + str(p))
    if write and not (p.is_relative_to(HERE) or p.is_relative_to(RETURNS) or p.is_relative_to(SCRATCH)):
        raise PermissionError('write outside task and readback return directory: ' + str(p))


sys.addaudithook(audit)
import numpy as np


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        assert not np.iscomplexobj(value)
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, Path):
        return str(value)
    return value


def dump(path, value):
    p = Path(path)
    p = p if p.is_absolute() else LOCAL / p
    assert p.resolve().is_relative_to(LOCAL) or p.resolve().is_relative_to(RETURNS)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def read(path):
    p = Path(path)
    return json.loads((p if p.is_absolute() else LOCAL / p).read_text())


load = read


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def stats(a):
    a = np.asarray(a, float)
    assert np.isfinite(a).all()
    return dict(n=len(a), median=float(np.median(a)), p90=float(np.percentile(a, 90)),
                max=float(a.max()), mean=float(a.mean()), share_under_2=float(np.mean(a < 2))) if len(a) else dict(n=0)


def calibration_modules():
    sys.path.insert(0, str(ROOT / 'research/module_adapt'))
    global s, calibrate, UnitModel
    import support as s
    s.HERE, s.LOCAL = HERE, LOCAL
    import calibrate
    from unit_model import UnitModel
    return s, calibrate, UnitModel


def model():
    calibration_modules()
    if not hasattr(sys.modules.get('common'), 'helper'):
        module('common', ROOT / 'research/closed_loop/common.py')
    return UnitModel('50mm', iso=200)


def exchange(slot='04'):
    calibration_modules()
    return calibrate.load_exchange(DATA / 'patches.jsonl', DATA / 'frames.json', '50mm', slot)[0]


def readback_modules():
    sys.path.insert(0, str(ROOT / 'research/gr_dense_reference'))
    if not hasattr(sys.modules.get('common'), 'pin'):
        module('common', ROOT / 'research/gr_incamera_dev/common.py')
    import readback_r3 as rb
    import common
    common.LOCAL, common.TMP = RETURNS, SCRATCH
    import analyze
    analyze.LOCAL = RETURNS
    return rb, analyze, common
