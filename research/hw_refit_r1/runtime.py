"""Read-only adapters for the existing r7/GR4 response. No camera or firmware work."""
import os
import sys
from pathlib import Path
import hashlib
import importlib.util
import json
import plistlib
import subprocess

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
R7 = ROOT / 'research/refit_50mm_r7'
DATA = ROOT / 'research/chart_session_20261024/local/moire-review-v2/exchange-jpeg6/50mm'
INPUTS = {}
WRITES = set()
for key in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
for key in ('TMPDIR', 'TMP', 'TEMP', 'MPLCONFIGDIR'):
    os.environ[key] = str(LOCAL / 'tmp')
os.environ['GIT_OPTIONAL_LOCKS'] = '0'


def mount_guard():
    d = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount()
    assert d['FilesystemType'] == 'apfs'
    assert d['VolumeUUID'].upper() == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert d['WritableVolume'] and d['WritableMedia']
    assert not HERE.is_symlink()


mount_guard()


def audit(event, args):
    if event in ('socket.connect', 'socket.bind'):
        raise PermissionError('offline modelling: network forbidden')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        p = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        writing = isinstance(mode, str) and any(c in mode for c in 'wax+')
        writing |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing:
            if not p.is_relative_to(HERE):
                raise PermissionError('write outside hw_refit_r1: ' + str(p))
            WRITES.add(str(p.relative_to(HERE)))
        if str(p).startswith('/Volumes/') and not p.is_relative_to(ROOT):
            raise PermissionError('read outside named checkout: ' + str(p))
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename'):
        for v in args[:2] if event == 'os.rename' else args[:1]:
            if isinstance(v, (str, bytes, Path)) and not Path(os.fsdecode(v)).resolve().is_relative_to(HERE):
                raise PermissionError('mutation outside hw_refit_r1')


sys.addaudithook(audit)
LOCAL.mkdir(exist_ok=True)
(LOCAL / 'tmp').mkdir(exist_ok=True)
import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inp(path):
    p = Path(path)
    p = (ROOT / p if not p.is_absolute() else p).resolve()
    assert p.is_relative_to(ROOT) and p.is_file(), p
    if not p.is_relative_to(HERE):
        key = str(p.relative_to(ROOT))
        h = sha(p)
        assert key not in INPUTS or INPUTS[key] == h, key
        INPUTS[key] = h
    return p


def read(path):
    return json.loads(inp(path).read_text())


def arrays(path):
    with np.load(inp(path), allow_pickle=False) as z:
        return dict(z)


def plain(v):
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if isinstance(v, np.ndarray):
        return plain(v.tolist())
    if isinstance(v, np.generic):
        return plain(v.item())
    if isinstance(v, Path):
        return str(v)
    return v


def dump(path, value):
    path = Path(path)
    path = LOCAL / path if not path.is_absolute() else path
    assert path.resolve().is_relative_to(HERE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain(value), indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def load(path):
    return read(LOCAL / path)


def module(name, path):
    p = inp(path)
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sys.modules['runtime'] = sys.modules[__name__]
sys.path.insert(0, str(ROOT / 'research/module_adapt'))
s = module('support', 'research/module_adapt/support.py')
s.HERE, s.LOCAL = HERE, LOCAL
s.source, s.digest = inp, sha
sys.path.insert(0, str(ROOT / 'research/closed_loop'))
common = module('common', 'research/closed_loop/common.py')
calibrate = module('calibrate', 'research/module_adapt/calibrate.py')
um = module('unit_model', 'research/module_adapt/unit_model.py')
f = module('refit', 'research/refit_50mm_r7/refit.py')
cm = module('colour_math', 'research/color_references/colour_math.py')


def model():
    return um.UnitModel('50mm', iso=200)


def exchange(slot='04'):
    return calibrate.load_exchange(DATA / 'patches.jsonl', DATA / 'frames.json', '50mm', slot)[0]


def finish(tag):
    for k, h in INPUTS.items():
        assert sha(ROOT / k) == h, k
    dump('inputs/' + tag + '.json', {'sha256': INPUTS, 'all_inputs_unchanged': True,
                                    'writes': sorted(WRITES)})
