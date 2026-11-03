"""Local-only I/O, frozen helper loading and reproducible provenance."""
import sys
sys.dont_write_bytecode = True
import hashlib
import importlib.util
import json
import plistlib
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
SCRATCH = LOCAL / 'tmp'
UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def input_path(value):
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = ROOT / p
    require(not str(p).startswith('/Volumes/') or p.is_relative_to('/Volumes/Workspace'),
            '禁止访问其他 /Volumes 路径')
    p = p.resolve()
    require(not str(p).startswith('/Volumes/') or p.is_relative_to('/Volumes/Workspace'),
            '符号链接指向其他卷')
    return p


def output_path(value):
    p = input_path(value)
    require(p.is_relative_to(LOCAL.resolve()), '派生数据只能写入 closed_loop/local/')
    require(not LOCAL.is_symlink(), 'local/ 不得是符号链接')
    return p


def mount_guard():
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    require(info.get('MountPoint') == '/Volumes/Workspace' and Path('/Volumes/Workspace').is_mount(),
            'Workspace 未挂载')
    require(info.get('FilesystemType') == 'apfs' and info.get('VolumeUUID', '').upper() == UUID,
            'Workspace 文件系统或 UUID 不符')
    require(all(info.get(k) for k in ('Writable', 'WritableMedia', 'WritableVolume')), 'Workspace 不可写')
    require('local/' in (HERE / '.gitignore').read_text().splitlines(), '.gitignore 缺少 local/')
    subprocess.run(['git', 'check-ignore', '-q', str(LOCAL / 'guard')], cwd=ROOT, check=True)
    return {'uuid': UUID, 'filesystem': 'apfs', 'writable': True}


def sha(path):
    h = hashlib.sha256()
    with input_path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(input_path(path).read_text())


def jsonable(v):
    import numpy as np
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, np.ndarray):
        require(not np.iscomplexobj(v), '复杂数组应显式保存为实部和虚部')
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, Path):
        return str(v)
    return v


def dump(path, value):
    p = output_path(path)
    encoded = json.dumps(jsonable(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(encoded)


_MODULES = {}


def load(name, path):
    key = str(input_path(path))
    if key not in _MODULES:
        spec = importlib.util.spec_from_file_location('closedloop_' + name, key)
        obj = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = obj
        spec.loader.exec_module(obj)
        _MODULES[key] = obj
    return _MODULES[key]


def helper(name):
    paths = {'mm': 'research/color_table_fit/matrix_model.py',
             'fs': 'research/color_table_fit/fit_sectors.py',
             'ar': 'research/hue_ring/analyze_ring.py',
             'geo': 'research/t1_probe/probe2/calibration_geometry.py',
             'physical': 'research/stage2e_verification/analyze_2e.py',
             'dng': 'research/color_table_fit/dng_scene.py',
             'src': 'firmware/stage2j/tools/deep_sources.py',
             'v2': 'pretable.py', 'safety': 'safety.py'}
    p = LOCAL / 'vendor' / paths[name]
    require(p.is_file(), '先运行 python3 -I -B research/closed_loop/bootstrap.py')
    obj = load(name, p)
    if name == 'v2':
        obj.sm = helper('ar').sm
    if name == 'safety':
        obj.fs = helper('fs')
    return obj


class Provenance:
    def __init__(self):
        self.before = {}

    def add(self, path):
        p = input_path(path)
        self.before.setdefault(str(p), sha(p))
        return p

    def finish(self):
        rows = {p: {'sha256': h, 'unchanged': sha(p) == h} for p, h in self.before.items()}
        require(all(v['unchanged'] for v in rows.values()), '运行期间输入发生变化，结果不可用')
        return rows
