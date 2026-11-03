"""Read-only inputs and body_lut-only outputs. Run with python3 -I -B."""
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
UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'


def guard():
    p = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount()
    assert p['MountPoint'] == '/Volumes/Workspace' and p['FilesystemType'] == 'apfs'
    assert p['VolumeUUID'].upper() == UUID
    assert all(p[k] for k in ('Writable', 'WritableMedia', 'WritableVolume'))
    assert (HERE / '.gitignore').read_text() == 'local/\n'
    subprocess.run(['git', 'check-ignore', '-q', 'research/body_lut/local/x'], cwd=ROOT, check=True)
    assert not LOCAL.is_symlink()
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / 'tmp').mkdir(exist_ok=True)
    os.environ['TMPDIR'] = str(LOCAL / 'tmp')
    os.environ['MPLCONFIGDIR'] = str(LOCAL / 'tmp' / 'mpl')
    return p


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def inp(p):
    p = Path(p)
    if not p.is_absolute():
        p = ROOT / p
    p = p.resolve()
    assert p.is_relative_to(ROOT) and p.is_file(), p
    if not p.is_relative_to(HERE):
        registry = LOCAL / 'inputs.json'
        rows = json.loads(registry.read_text()) if registry.exists() else {}
        key = str(p.relative_to(ROOT))
        digest = sha(p)
        if key in rows:
            assert rows[key] == digest, f'input changed: {p}'
        else:
            rows[key] = digest
            registry.write_text(json.dumps(rows, sort_keys=True, indent=2) + '\n')
    return p


def read(p):
    return json.loads(inp(p).read_text())


def jsonable(v):
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (tuple, list)):
        return [jsonable(x) for x in v]
    if hasattr(v, 'tolist'):
        return v.tolist()
    if isinstance(v, Path):
        return str(v)
    return v


def dump(name, v):
    p = (LOCAL / name).resolve()
    assert p.is_relative_to(LOCAL.resolve())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(jsonable(v), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location('body_lut_' + name, inp(path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def tree_state():
    rows = {}
    for folder, dirs, files in os.walk(ROOT, followlinks=False):
        dirs[:] = [d for d in dirs if d != '.git' and not (Path(folder)/d).is_symlink()
                   and (Path(folder)/d).resolve() != HERE]
        for name in files:
            p = Path(folder)/name
            st = p.lstat()
            rows[str(p.relative_to(ROOT))] = [st.st_size, st.st_mtime_ns, st.st_mode]
    return rows


if __name__ == '__main__':
    mount = guard()
    assert not (LOCAL/'tree_before.json').exists(), 'baseline already exists'
    dump('tree_before.json', tree_state())
    dump('preflight.json', {'mount': mount, 'df': subprocess.check_output(
        ['df', '-h', '/Volumes/Workspace'], text=True), 'git_status': subprocess.check_output(
        ['git', 'status', '--porcelain=v1', '-uall'], cwd=ROOT, text=True),
        'python': sys.version, 'write_root': str(HERE)})
    print('mount, ignore rule, input-tree metadata baseline: OK')
