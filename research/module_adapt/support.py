"""Read-only project inputs and task-local outputs."""
import hashlib
import importlib.util
import json
import plistlib
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
FW = ROOT / 'artifacts/firmware/gxr-1.51'
DAILY = ROOT / 'artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8/candidate/SD_ROOT/DEEPTBL0.DAT'
INPUTS = {}


def guard():
    d = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount() and d.get('MountPoint') == '/Volumes/Workspace'
    assert d.get('FilesystemType') == 'apfs'
    assert d.get('VolumeUUID', '').upper() == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert all(d.get(k) for k in ('Writable', 'WritableMedia', 'WritableVolume'))
    assert not LOCAL.is_symlink()
    subprocess.run(['git', 'check-ignore', '-q', str(LOCAL / 'guard.json')], cwd=ROOT, check=True)


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def source(p):
    p = Path(p)
    p = (ROOT / p if not p.is_absolute() else p).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError('输入必须在本检出内，禁止访问其它卷或存储卡')
    INPUTS.setdefault(str(p.relative_to(ROOT)), digest(p))
    return p


def read(p):
    return json.loads(source(p).read_text())


def output(p):
    p = Path(p)
    p = (HERE / p if not p.is_absolute() else p).resolve()
    if not p.is_relative_to(LOCAL.resolve()):
        raise ValueError('派生数据只能写入 module_adapt/local/')
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def jsonable(v):
    import numpy as np
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (tuple, list)):
        return [jsonable(x) for x in v]
    if isinstance(v, np.ndarray):
        assert not np.iscomplexobj(v), '显式保存复数的实部和虚部'
        return jsonable(v.tolist())
    if isinstance(v, np.generic):
        return jsonable(v.item())
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, complex):
        return [v.real, v.imag]
    return v


def dump(p, obj):
    output(p).write_text(json.dumps(jsonable(obj), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def load(name, path):
    p = source(path)
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def engine(iso=200):
    sys.path.insert(0, str(ROOT / 'research/closed_loop'))
    model = load('module_adapt_closedloop', ROOT / 'research/closed_loop/model.py')
    e = model.Engine(source(DAILY), iso=iso)
    for p in e.provenance.before:
        source(p)
    manifest = read(ROOT / 'research/closed_loop/local/vendor_manifest.json')
    for rel in manifest['copies_sha256']:
        source(ROOT / 'research/closed_loop/local' / rel)
    source(ROOT / 'research/closed_loop/common.py')
    return e


def finish(name):
    changed = [p for p, h in INPUTS.items() if digest(ROOT / p) != h]
    assert not changed, f'运行中输入变化: {changed}'
    dump(name, {'sha256': INPUTS, 'all_inputs_unchanged': True})


def stats(x):
    import numpy as np
    x = np.asarray(x, float)
    assert np.isfinite(x).all()
    if not len(x):
        return {'n': 0, 'median': None, 'p90': None, 'max': None}
    return {'n': len(x), 'median': float(np.median(x)), 'p90': float(np.percentile(x, 90)),
            'max': float(x.max()), 'share_under_2': float(np.mean(x < 2))}


def similarity(errors, baseline):
    a, b = stats(errors), stats(baseline)
    return None if not a['n'] or not b['n'] or b['median'] < .25 else 1 - a['median'] / b['median']
