"""T3 host-only paths, mount checks and enforced output boundaries."""
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
PACKAGE = ROOT / 'artifacts/stage2j-packages/tables-v4r2-probe3'
BASE = ROOT / 'artifacts/stage2j-packages/tables-v4r2-probe2'
SCRATCH = Path('/tmp/t3p').resolve()
STAGE = ROOT / 'firmware/stage2j'
BASE_SHA = '40665151292dcb2405d22f80092a474caa7959d9f60aceeb11d55755c19ae0ef'
CAP = ROOT / 'captures/a12-50/2026-10-20/stage2j-v1-calibration'
MODEL = ROOT / 'research/hue_ring/local/ring_model_v2.json'
V2_CODE = ROOT / 'research/hue_ring/local/calibration_20261020/followup_v2/code'


def require(value, message):
    if not value:
        raise ValueError(message)


def check_input(path):
    path = Path(path).resolve()
    require(not str(path).startswith('/Volumes/') or path.is_relative_to(Path('/Volumes/Workspace')),
            'Other /Volumes paths are forbidden')
    return path


def load(name, path):
    path = check_input(path)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(path):
    path = check_input(path)
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def jsonable(v):
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (tuple, list)):
        return [jsonable(x) for x in v]
    if isinstance(v, Path):
        return str(v)
    if hasattr(v, 'tolist'):
        return jsonable(v.tolist())
    return v


def save(path, data, private=False):
    path = Path(path).resolve()
    roots = (LOCAL, PACKAGE) if private else (HERE, PACKAGE, SCRATCH)
    require(any(path.is_relative_to(q.resolve()) for q in roots), f'Write outside authorized roots: {path}')
    if private:
        ignored(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding='utf-8')


def dump(path, data, private=False):
    save(path, json.dumps(jsonable(data), ensure_ascii=False, indent=2, allow_nan=False) + '\n', private)


def ignored(path):
    r = subprocess.run(['git', 'check-ignore', '-q', str(path)], cwd=ROOT)
    require(r.returncode == 0, f'Private output is not ignored: {path}')


def preflight():
    info = plistlib.loads(subprocess.run(['diskutil', 'info', '-plist', '/Volumes/Workspace'],
                                         check=True, capture_output=True).stdout)
    require(os.path.ismount('/Volumes/Workspace') and info['MountPoint'] == '/Volumes/Workspace' and
            info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and
            info['FilesystemType'] == 'apfs' and info['WritableVolume'] and
            info['WritableMedia'] and os.access('/Volumes/Workspace', os.W_OK), 'Volume check failed')
    df = subprocess.run(['df', '-h', '/Volumes/Workspace'], check=True, capture_output=True, text=True).stdout
    ignored(LOCAL / 'sentinel.json')
    ignored(PACKAGE / 'DEEPTBL0.DAT')
    SCRATCH.mkdir(parents=True, exist_ok=True)
    save(LOCAL / 'df.txt', df)
    dump(LOCAL / 'volume.json', {k: info[k] for k in ('MountPoint', 'VolumeUUID', 'FilesystemType',
                                                   'WritableVolume', 'WritableMedia')})


def generator():
    return load('t3_deep_generator', STAGE / 'tools/make_table_files.py').src


def source_manifest(paths):
    return {str(q.relative_to(ROOT)): sha(q) for q in sorted(set(map(Path, paths)))}


def legacy_analyzer():
    """Reuse probe2 without writing to its checkout or its original local cache."""
    a = load('t3_existing_probe2', ROOT / 'research/t1_probe/probe2/analyze_probe2.py')
    a.p.LOCAL = LOCAL
    a.p.SCRATCH = SCRATCH / 'probe2'
    a.p.save = lambda path, data: save(path, data, private=True)
    a.p.dump = lambda path, data: dump(path, data, private=True)
    return a
