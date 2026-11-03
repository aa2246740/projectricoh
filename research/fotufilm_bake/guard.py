"""Copied from research/film_engines_eval/guard.py (from lut_convert); output fence moved to research/fotufilm_bake/local/."""
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
DOWNLOADS = LOCAL / 'luts'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/fotufilm/eval-tmp')
UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'


def input_path(value):
    p = Path(value).expanduser().absolute()
    if str(p).startswith('/Volumes/') and not p.is_relative_to('/Volumes/Workspace'):
        raise ValueError('禁止读取其他卷：' + str(p))
    p = p.resolve()
    if str(p).startswith('/Volumes/') and not p.is_relative_to('/Volumes/Workspace'):
        raise ValueError('符号链接指向其他卷：' + str(p))
    return p


def output_path(value):
    p = input_path(value)
    if not p.is_relative_to(LOCAL) or LOCAL.is_symlink():
        raise ValueError('派生数据只能写入 research/fotufilm_bake/local/')
    return p


def mount_guard():
    v = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    if (v.get('MountPoint') != '/Volumes/Workspace' or not Path('/Volumes/Workspace').is_mount()
            or v.get('FilesystemType') != 'apfs' or v.get('VolumeUUID', '').upper() != UUID
            or not all(v.get(k) for k in ('Writable', 'WritableMedia', 'WritableVolume'))):
        raise ValueError('Workspace 挂载、APFS、UUID 或可写性不符')
    if 'local/' not in (HERE / '.gitignore').read_text().splitlines():
        raise ValueError('缺少 local/ ignore')
    subprocess.run(['git', 'check-ignore', '-q', str(LOCAL / 'guard')], cwd=ROOT, check=True)
    return {'uuid': UUID, 'filesystem': 'apfs', 'writable': True}


def install_write_fence(download=False):
    """Also prevents imported legacy helpers from writing their own caches."""
    allowed = (LOCAL, SCRATCH)

    def audit(event, args):
        if event != 'open' or not isinstance(args[0], (str, bytes, Path)):
            return
        p = input_path(os.fsdecode(args[0]))
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing and not any(p.is_relative_to(r) for r in allowed):
            raise PermissionError('Write outside fotufilm_bake fence: ' + str(p))
    sys.addaudithook(audit)
    for k in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[k] = '1'
    os.environ['TMPDIR'] = str(SCRATCH)


def sha(path):
    h = hashlib.sha256()
    with input_path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def jsonable(v):
    import numpy as np
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (tuple, list)):
        return [jsonable(x) for x in v]
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, Path):
        return str(v)
    return v


def dump(path, value):
    p = output_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(jsonable(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, input_path(path))
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj
