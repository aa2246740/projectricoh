"""Read-only input inventory and strict task-local output boundary."""
import sys
sys.dont_write_bytecode = True
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
TMP = LOCAL / 'tmp'
os.environ['TMPDIR'] = str(TMP)
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[key] = '1'


def audit(event, args):
    if event.startswith(('socket.connect', 'socket.bind', 'socket.getaddrinfo')):
        raise PermissionError('Offline task')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing and not path.is_relative_to(HERE):
            raise PermissionError('Write outside research/gr4_positive: ' + str(path))
        if str(path).startswith('/Volumes/') and not path.is_relative_to(Path('/Volumes/Workspace')):
            raise PermissionError('Other volume: ' + str(path))


sys.addaudithook(audit)
import hashlib
import importlib.util
import json
import plistlib
import subprocess


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    path = Path(path).resolve()
    assert path.is_relative_to(HERE), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def guard():
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['MountPoint'] == '/Volumes/Workspace'
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['FilesystemType'] == 'apfs' and info['WritableVolume']
    assert (HERE / '.gitignore').read_text() == 'local/\n'
    ignored = subprocess.check_output(['git', 'check-ignore', '-v', str(LOCAL / 'probe')], cwd=ROOT, text=True)
    assert 'research/gr4_positive/.gitignore:1:local/' in ignored
    assert not subprocess.check_output(['git', 'ls-files', str(LOCAL)], cwd=ROOT)
    TMP.mkdir(parents=True, exist_ok=True)
    return {'volume_uuid': info['VolumeUUID'], 'ignore': ignored.strip()}


PROTECTED = ('captures', 'artifacts', 'research/color_fit_v2', 'research/gr_pairs',
             'research/gr_webpairs', 'research/gr_hdfchart', 'research/hue_ring',
             'research/gr4_modes', 'research/gr4_bench', 'research/closed_loop',
             'research/contrib_gr_analysis', 'research/matrix_test_onbody')


def inventory():
    files = {p for folder in PROTECTED for p in (ROOT / folder).rglob('*') if p.is_file()}
    files.update(ROOT / name for name in ('.gitignore', 'decisions.tsv') if (ROOT / name).is_file())
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)}


if __name__ == '__main__':
    meta = guard()
    dest = LOCAL / 'protected_before.json'
    if dest.exists():
        raise SystemExit('Baseline exists; use verify.py instead of overwriting it')
    before = inventory()
    dump(dest, before)
    dump(LOCAL / 'preflight.json', dict(meta, protected_files=len(before), manifest_sha256=sha(dest)))
    (LOCAL / 'git_before.txt').write_text(subprocess.check_output(
        ['git', 'status', '--short', '--untracked-files=normal'], cwd=ROOT, text=True))
    print(json.dumps(dict(meta, protected_files=len(before))))
