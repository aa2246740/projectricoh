"""Offline web-pair analysis; all writes stay beside this script."""
import sys
sys.dont_write_bytecode = True
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
TMP = LOCAL / 'tmp'
os.environ['TMPDIR'] = str(TMP)
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[name] = '1'


def audit(event, args):
    if event.startswith(('socket.connect', 'socket.bind', 'socket.getaddrinfo')):
        raise PermissionError('No network in this analysis')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        p = Path(os.fsdecode(args[0])).resolve()
        if str(p).startswith('/Volumes/') and not p.is_relative_to(Path('/Volumes/Workspace')):
            raise PermissionError('Other volume: ' + str(p))
        mode, flags = args[1:3]
        write = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if write and not p.resolve().is_relative_to(HERE):
            raise PermissionError('Write outside research/gr_webpairs: ' + str(p))


sys.addaudithook(audit)
import hashlib
import importlib.util
import json
import plistlib
import subprocess
import numpy as np


def guard():
    d = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert d['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert d['FilesystemType'] == 'apfs' and d['WritableVolume']
    assert d['MountPoint'] == '/Volumes/Workspace'
    assert (HERE / '.gitignore').read_text() == 'local/\n'
    ignored = subprocess.check_output(['git', 'check-ignore', '-v', str(LOCAL / 'probe')],
                                      cwd=ROOT, text=True)
    assert 'research/gr_webpairs/.gitignore:1:local/' in ignored
    TMP.mkdir(parents=True, exist_ok=True)


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def plain(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, bytes):
        return {'bytes': len(v), 'sha256': hashlib.sha256(v).hexdigest()}
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    return v


def dump(path, value):
    path = Path(path).resolve()
    assert path.is_relative_to(HERE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def modules():
    for folder in ('gr4_modes', 'contrib_gr_analysis', 'color_references'):
        p = str(ROOT / 'research' / folder)
        if p not in sys.path:
            sys.path.insert(0, p)
    import gr4io
    import colour_math
    import measure
    import tiff_makernote
    gr4io.SCRATCH = TMP / 'decoder'
    gr4io.LOCAL = LOCAL / 'cache'
    return gr4io, colour_math, measure, tiff_makernote


def pair_modules():
    """Reuse the original extractor with explicitly relocated output globals."""
    common = load('common', ROOT / 'research/gr_pairs/common.py')
    common.LOCAL, common.TMP = LOCAL, TMP
    common.modules = modules
    common.guard = guard
    extract = load('extract', ROOT / 'research/gr_pairs/extract.py')
    return common, extract


def frames(data_root):
    data_root = Path(data_root).resolve()
    assert data_root.is_relative_to(ROOT / 'captures')
    out = []
    for directory, ident, family, body, mode in (
        ('5b', 'R0011392', 'gr3', 'gr3_hdf_web', 'positive'),
        ('5', 'SC0134', 'gr4', 'gr4_dpreview', 'positive'),
        ('5', 'SC0434', 'gr4', 'gr4_dpreview', 'positive'),
        ('3', 'Lecce', 'gr3x', 'gr3x_lecce', 'positive'),
        ('4', 'London', 'gr3x', 'gr3x_london', 'negative'),
    ):
        candidates = [p for p in (data_root / directory).rglob('*') if p.suffix.lower() == '.dng']
        if directory == '5':
            candidates = [p for p in candidates if ident in p.name]
        assert len(candidates) == 1, (ident, candidates)
        dng = candidates[0]
        jpgs = [p for p in dng.parent.iterdir() if p.suffix.lower() in ('.jpg', '.jpeg')]
        assert len(jpgs) == 1
        out.append(dict(id=ident, family=family, body=body, mode=mode,
                        dng=str(dng.relative_to(ROOT)), jpg=str(jpgs[0].relative_to(ROOT)),
                        scene=ident, standalone_jpeg=directory == '5'))
    return out


def protected_tree(folder):
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / folder).rglob('*'))
            if p.is_file() and not p.is_relative_to(HERE)}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('folder', choices=['captures', 'artifacts', 'firmware', 'research'])
    a = p.parse_args()
    guard()
    dest = LOCAL / ('protected_before_' + a.folder + '.json')
    assert not dest.exists(), 'Never overwrite a baseline'
    h = protected_tree(a.folder)
    dump(dest, h)
    print(json.dumps(dict(folder=a.folder, files=len(h), manifest_sha256=sha(dest))))
