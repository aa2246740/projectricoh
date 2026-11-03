"""Offline research boundary and read-only provenance. Run with python3 -I -B."""
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
for key in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
for key in ('TMPDIR', 'TMP', 'TEMP', 'MPLCONFIGDIR'):
    os.environ[key] = str(LOCAL / 'tmp')
os.environ['GIT_OPTIONAL_LOCKS'] = '0'


def guard():
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount()
    assert info['FilesystemType'] == 'apfs'
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['WritableVolume'] and info['WritableMedia']
    assert not HERE.is_symlink() and not LOCAL.is_symlink()
    subprocess.run(['git', 'check-ignore', '-q', str(LOCAL / 'probe')], cwd=ROOT, check=True)


guard()


def audit(event, args):
    if event == 'socket.connect' or event == 'socket.bind':
        raise PermissionError('HOST-ONLY: network disabled')
    if event == 'exec' and hasattr(args[0], 'co_filename'):
        source = Path(args[0].co_filename)
        if source.is_absolute() and source.is_file() and source.is_relative_to(ROOT):
            if source.is_relative_to(ROOT / 'captures') or source.is_relative_to(ROOT / 'artifacts/downloads'):
                raise PermissionError('untrusted input must not execute: ' + str(source))
            if not source.is_relative_to(HERE) and 'inp' in globals():
                inp(source)
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        write = isinstance(mode, str) and any(c in mode for c in 'wax+')
        write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if write and not path.is_relative_to(HERE):
            raise PermissionError('write outside gr4_lut_ceiling: ' + str(path))
        if str(path).startswith('/Volumes/') and not path.is_relative_to(ROOT):
            raise PermissionError('read outside checkout: ' + str(path))
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename'):
        for value in args[:2] if event == 'os.rename' else args[:1]:
            if isinstance(value, (str, bytes, Path)):
                path = Path(os.fsdecode(value)).resolve()
                if not path.is_relative_to(HERE):
                    raise PermissionError('mutation outside gr4_lut_ceiling: ' + str(path))


sys.addaudithook(audit)
import numpy as np
_ADDITIONS = {}
_FROZEN_STATE = None


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, Path):
        return str(value)
    return value


def dump(name, value):
    path = LOCAL / name
    assert path.resolve().is_relative_to(LOCAL)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain(value), indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def inp(path):
    global _FROZEN_STATE
    path = Path(path)
    path = path if path.is_absolute() else ROOT / path
    path = path.resolve()
    assert path.is_relative_to(ROOT) and path.is_file()
    assert path.name != 'decisions.tsv'
    assert not path.is_relative_to(ROOT / 'firmware/engine_v35_publish')
    assert not path.is_relative_to(ROOT / 'research/body_lut_r2')
    if path.is_relative_to(HERE):
        return path
    if _FROZEN_STATE is None:
        manifest = LOCAL / 'inputs.json'
        _FROZEN_STATE = json.loads(manifest.read_text()) if manifest.exists() else {}
        for extra in sorted((LOCAL / 'input_additions').glob('*.json')):
            for key, value in json.loads(extra.read_text()).items():
                assert key not in _FROZEN_STATE or _FROZEN_STATE[key] == value, 'FROZEN INPUT CHANGED: ' + key
                _FROZEN_STATE[key] = value
    state = _FROZEN_STATE
    key = str(path.relative_to(ROOT))
    value = sha(path)
    if key in state:
        assert value == state[key], 'FROZEN INPUT CHANGED: ' + key
    else:
        assert key not in _ADDITIONS or _ADDITIONS[key] == value, 'FROZEN INPUT CHANGED: ' + key
        _ADDITIONS[key] = value
        state[key] = value
        dump(f'input_additions/{os.getpid()}.json', _ADDITIONS)
    return path


def read(path):
    return json.loads(inp(path).read_text())


def arrays(path):
    with np.load(inp(path), allow_pickle=False) as doc:
        return dict(doc)


def module(name, path):
    path = inp(path)
    assert path.suffix == '.py'
    assert not path.is_relative_to(ROOT / 'captures')
    assert not path.is_relative_to(ROOT / 'artifacts/downloads')
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cm = module('ceiling_colour_math', 'research/color_references/colour_math.py')


def lab(rgb):
    return cm.xyz_lab(cm.srgb_decode(np.asarray(rgb) / 255) @ cm.SRGB_XYZ.T, cm.D65)


def rgb(labs):
    return cm.srgb_encode(cm.lab_xyz(labs, cm.D65) @ np.linalg.inv(cm.SRGB_XYZ).T) * 255


def stats(value):
    value = np.asarray(value, float)
    assert np.isfinite(value).all()
    if not value.size:
        return {'n': 0}
    return dict(n=len(value), median=float(np.median(value)), mean=float(np.mean(value)),
                p90=float(np.percentile(value, 90)), max=float(np.max(value)))


def score(error, baseline):
    e, b = stats(error), stats(baseline)
    return dict(error=e, baseline=b,
                similarity_median=1-e['median']/b['median'] if e['n'] and b['median'] > 1e-12 else None,
                similarity_mean=1-e['mean']/b['mean'] if e['n'] and b['mean'] > 1e-12 else None,
                similarity_p90=1-e['p90']/b['p90'] if e['n'] and b['p90'] > 1e-12 else None)


def verify_inputs():
    state = json.loads((LOCAL / 'inputs.json').read_text())
    for path in sorted((LOCAL / 'input_additions').glob('*.json')):
        for key, value in json.loads(path.read_text()).items():
            assert key not in state or state[key] == value, 'FROZEN INPUT CHANGED: ' + key
            state[key] = value
    changed = [key for key, value in state.items() if sha(ROOT / key) != value]
    dump('verification/frozen_inputs.json', dict(n=len(state), changed=changed, decisions_tsv_excluded=True))
    assert not changed, 'FROZEN INPUT CHANGED: ' + ', '.join(changed[:5])
    return len(state)
