"""Read-only dependencies and a single, audited output boundary for this study."""
import sys
sys.dont_write_bytecode = True
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
TMP = LOCAL / 'tmp'
os.environ['TMPDIR'] = str(TMP)
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[key] = '1'


def audit(event, args):
    if event.startswith(('socket.connect', 'socket.bind', 'socket.getaddrinfo')):
        raise PermissionError('Offline study')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        path = Path(os.fsdecode(args[0])).resolve()
        if str(path).startswith('/Volumes/') and not path.is_relative_to(Path('/Volumes/Workspace')):
            raise PermissionError('Other volume is forbidden')
        mode, flags = args[1:3]
        write = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if write and not path.is_relative_to(HERE):
            raise PermissionError('Write outside gr_hdfchart: ' + str(path))
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename'):
        for item in args[:2 if event == 'os.rename' else 1]:
            if isinstance(item, (str, bytes, Path)) and not Path(os.fsdecode(item)).resolve().is_relative_to(HERE):
                raise PermissionError('Mutation outside gr_hdfchart: ' + str(item))


sys.addaudithook(audit)
import hashlib
import json
import plistlib
import subprocess
import importlib.util
import numpy as np

PROTECTED = ('captures', 'research/hue_ring', 'research/color_fit_v2',
             'research/gr_pairs', 'research/gr_webpairs', 'research/closed_loop',
             'research/contrib_gr_analysis', 'research/gr4_modes',
             'research/color_references', 'research/gr_evalsets',
             'artifacts/downloads/bastibe-gr3')


def guard():
    d = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert d['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert d['FilesystemType'] == 'apfs' and d['WritableVolume']
    assert (HERE / '.gitignore').read_text() == 'local/\n'
    q = subprocess.check_output(['git', 'check-ignore', '-v', str(LOCAL / 'probe')], cwd=ROOT, text=True)
    assert 'research/gr_hdfchart/.gitignore:1:local/' in q
    TMP.mkdir(parents=True, exist_ok=True)
    return q.strip()


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
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    return v


def dump(path, value):
    path = Path(path).resolve()
    assert path.is_relative_to(LOCAL), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def snapshot():
    guard()
    hashes = {str(p.relative_to(ROOT)): sha(p) for folder in PROTECTED
              for p in sorted((ROOT / folder).rglob('*')) if p.is_file()}
    dest = LOCAL / 'protected_before.json'
    if dest.exists():
        assert read(dest) == hashes, 'Protected inputs changed'
    else:
        dump(dest, hashes)
    source = ROOT / 'captures/contrib/2026-10-22-gr4hdf-screenchart'
    lines = (source / 'SHA256SUMS').read_text().splitlines()
    for line in lines:
        digest, rel = line.split(maxsplit=1)
        assert sha(source / rel.lstrip('*')) == digest, rel
    dump(LOCAL / 'preflight.json', dict(protected_files=len(hashes), source_manifest_entries=len(lines),
                                      source_manifest_sha256=sha(source / 'SHA256SUMS'), ignore=guard()))
    print(json.dumps(dict(protected_files=len(hashes), source_hashes_ok=len(lines))))


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


def runtime():
    common = load('common', ROOT / 'research/gr_pairs/common.py')
    common.modules = modules
    common.guard = guard
    # Model files remain read-only at their established paths; the extractor's
    # cache and all dump calls have our local boundary.
    extract = load('extract', ROOT / 'research/gr_pairs/extract.py')
    extract.LOCAL, extract.TMP, extract.dump = LOCAL, TMP, dump
    common.dump = dump
    # Supply the web scoring module's small host interface without installing
    # its directory-specific audit hook.
    import types
    core = types.ModuleType('core')
    for name in ('ROOT', 'HERE', 'LOCAL', 'guard', 'read', 'dump', 'load', 'modules'):
        setattr(core, name, globals()[name])
    sys.modules['core'] = core
    web = load('chart_web_score', ROOT / 'research/gr_webpairs/score.py')
    r = web.runtime()
    r.web, r.extract = web, extract
    r.ring = load('chart_ring', ROOT / 'research/hue_ring/analyze_ring.py')
    return r


if __name__ == '__main__':
    snapshot()
