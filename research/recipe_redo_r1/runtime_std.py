"""Local research I/O, a bounded process budget, and a device/write fence."""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
for _key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
HERE = Path(__file__).resolve().parent
LOCAL = HERE / 'local'
SOURCE = LOCAL / 'source'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/recipe-redo-r1')
DOWNLOADS = Path('/Users/wu/Downloads')
os.environ['TMPDIR'] = str(SCRATCH)
os.environ['GIT_OPTIONAL_LOCKS'] = '0'

import datetime
import fcntl
import hashlib
import importlib.util
import json
import plistlib
import subprocess

UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
volume = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
assert Path('/Volumes/Workspace').is_mount()
assert volume['DiskUUID'] == UUID and volume['FilesystemType'] == 'apfs'
assert volume['WritableVolume'] and volume['WritableMedia']
LOCAL.mkdir(exist_ok=True)
SCRATCH.mkdir(parents=True, exist_ok=True)
if os.getpriority(os.PRIO_PROCESS, 0) < 15:
    os.nice(15 - os.getpriority(os.PRIO_PROCESS, 0))
COMPUTE_BUDGET = 1
_authorization = LOCAL/'fast_switch_authorization.json'
if _authorization.is_file():
    _delivery = json.loads(_authorization.read_text())
    if _delivery.get('switch_notice') and _delivery.get('equivalence_passed') is True:
        COMPUTE_BUDGET = min(2, int(_delivery.get('max_compute_processes', 2)))
        assert COMPUTE_BUDGET >= 1
_lock = None
for COMPUTE_SLOT in range(COMPUTE_BUDGET):
    _candidate = (LOCAL/('.compute.lock' if COMPUTE_SLOT == 0 else f'.compute.{COMPUTE_SLOT}.lock')).open('a')
    try:
        fcntl.flock(_candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock = _candidate
        break
    except BlockingIOError:
        _candidate.close()
if _lock is None:
    raise RuntimeError(f'All {COMPUTE_BUDGET} authorized computation slots are occupied')


def write_ok(path):
    p = Path(path).resolve()
    return p.is_relative_to(HERE) or p.is_relative_to(SCRATCH)


def audit(event, args):
    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('Network is outside this local study')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        p = Path(os.fsdecode(args[0])).absolute().resolve()
        if p.is_relative_to(ROOT / 'studio'):
            raise PermissionError('Live owner Studio is outside this study')
        if str(p).startswith('/Volumes/') and not (p.is_relative_to(ROOT) or p.is_relative_to(SCRATCH)):
            raise PermissionError('Other volumes/paths are outside this study')
        if str(p).startswith('/dev/') and str(p) not in ('/dev/null', '/dev/urandom', '/dev/random'):
            raise PermissionError('Device access is outside this study')
        mode, flags = args[1:3]
        writing = isinstance(mode, str) and any(c in mode for c in 'wax+')
        writing |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing and not write_ok(p):
            raise PermissionError('Write outside recipe_redo_r1 or its Scratch')
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename', 'os.symlink', 'os.link', 'os.chmod', 'os.utime'):
        for item in args[:2] if event in ('os.rename', 'os.link', 'os.symlink') else args[:1]:
            if isinstance(item, (str, bytes, Path)) and not write_ok(os.fsdecode(item)):
                raise PermissionError('Mutation outside recipe_redo_r1 or its Scratch')


sys.addaudithook(audit)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, 'tolist'):
        return plain(value.tolist())
    if isinstance(value, Path):
        return str(value)
    return value


def dump(path, value):
    p = Path(path)
    if not p.is_absolute():
        p = HERE / p
    assert write_ok(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    from publication import atomic_bytes
    atomic_bytes(p, (json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode())


def read(path):
    return json.loads(Path(path).read_text())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def freeze_task_code():
    """Bind future optimization receipts to their exact task script revision."""
    files = {p.name: sha(p) for p in sorted(HERE.glob('*.py'))}
    identity = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    # Computation slots have distinct writers, even when several workers use
    # the same source revision concurrently.
    destination = LOCAL/'code_snapshots'/identity/f'slot{COMPUTE_SLOT}'
    destination.mkdir(parents=True, exist_ok=True)
    for name, digest in files.items():
        target = destination/name
        if not target.exists():
            target.write_bytes((HERE/name).read_bytes())
        assert sha(target)==digest
    manifest = destination/'manifest.json'
    if not manifest.exists():
        dump(manifest, dict(created_utc=utc(), identity=identity, files=files))
    return dict(identity=identity, files=files, folder=str(destination.relative_to(HERE)))


def assert_task_code(snapshot):
    assert all(sha(HERE/name)==digest for name, digest in snapshot['files'].items()), 'Task source changed during optimization'
