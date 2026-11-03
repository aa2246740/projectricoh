"""Task-scoped I/O and read-only reuse of the existing 50 mm converter."""
from pathlib import Path
import hashlib
import json
import os
import plistlib
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
DOWNLOAD = LOCAL / 'artifacts/downloads/vlog-alchemy-20261024'
ORIGINAL = ROOT / 'artifacts/downloads/huzi-panasonic-std-luts-20261024/original'
UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'


def preflight():
    v = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    if (v.get('MountPoint') != '/Volumes/Workspace' or not Path('/Volumes/Workspace').is_mount()
            or v.get('FilesystemType') != 'apfs' or v.get('VolumeUUID') != UUID
            or not all(v.get(k) for k in ('Writable', 'WritableMedia', 'WritableVolume'))):
        raise RuntimeError('Workspace identity, APFS or writable check failed')
    if HERE.is_symlink() or LOCAL.is_symlink():
        raise RuntimeError('Task and local directories must not be symlinks')
    subprocess.run(['git', 'check-ignore', '-q', str(LOCAL / 'probe')], cwd=ROOT, check=True)
    return {'volume_uuid': UUID, 'filesystem': 'apfs', 'writable': True}


def install_fence():
    sys.dont_write_bytecode = True
    for k in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[k] = '1'
    os.environ['TMPDIR'] = str(LOCAL / 'tmp')

    def audit(event, args):
        if event == 'exec' and isinstance(args[0].co_filename, str):
            if str(DOWNLOAD) in args[0].co_filename:
                raise PermissionError('Downloaded files are data, never executable')
        if event == 'open' and isinstance(args[0], (str, bytes, Path)):
            p = Path(os.fsdecode(args[0])).resolve()
            if str(p).startswith('/Volumes/') and not p.is_relative_to('/Volumes/Workspace'):
                raise PermissionError('Other volumes forbidden: ' + str(p))
            mode, flags = args[1:3]
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            if writing and not p.is_relative_to(HERE):
                raise PermissionError('Outside task write fence: ' + str(p))
        if event in ('os.remove', 'os.rmdir', 'os.rename', 'os.mkdir'):
            p = Path(os.fsdecode(args[0])).resolve()
            if not p.is_relative_to(HERE):
                raise PermissionError('Outside task filesystem mutation: ' + str(p))
    sys.addaudithook(audit)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def jsonable(value):
    import numpy as np
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def dump(path, value):
    path = Path(path).resolve()
    if not path.is_relative_to(LOCAL):
        raise PermissionError('Numerical and derived outputs must stay in local/')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def converter():
    sys.path.insert(0, str(ROOT / 'research/lut_convert'))
    import guard
    # Rebind only this interpreter's output destination, never the reused files.
    guard.LOCAL = LOCAL
    from camera import Camera
    from fit import Problem, score, stats
    from cube import Cube
    from convert import samples, sector_rows
    from spaces import xyz_to_encoded
    return Camera, Problem, score, stats, Cube, samples, sector_rows, xyz_to_encoded
