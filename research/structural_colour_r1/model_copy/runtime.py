"""Read-only input adapter and output fence for host-only colour research."""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
HERE = Path(__file__).resolve().parents[1]
LOCAL = HERE / 'local'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/structural-colour-r1')
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['TMPDIR'] = str(SCRATCH)
os.environ['MPLCONFIGDIR'] = str(SCRATCH / 'mpl')
os.environ['GIT_OPTIONAL_LOCKS'] = '0'

import hashlib
import importlib.util
import json
import plistlib
import shutil
import subprocess
import time

UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
volume = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
assert Path('/Volumes/Workspace').is_mount()
assert volume.get('DiskUUID', volume.get('VolumeUUID')) == UUID
assert volume['FilesystemType'] == 'apfs'
assert volume.get('WritableVolume', False)
assert volume.get('WritableMedia', False)
LOCAL.mkdir(parents=True, exist_ok=True)
SCRATCH.mkdir(parents=True, exist_ok=True)

INPUTS = {}
_hashing = False

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def allowed_write(path):
    return any(path.is_relative_to(base) for base in (HERE, SCRATCH))

def audit(event, args):
    global _hashing
    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('Network is outside this study')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        p = Path(os.fsdecode(args[0])).absolute().resolve()
        if str(p).startswith('/Volumes/') and not p.is_relative_to(ROOT) and not p.is_relative_to(SCRATCH):
            raise PermissionError('Read outside named checkout/scratch: ' + str(p))
        if str(p).startswith('/dev/') and str(p) not in ('/dev/null', '/dev/urandom', '/dev/random'):
            raise PermissionError('Device access is outside this study')
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing and not allowed_write(p):
            raise PermissionError('Write outside look_ceiling_r1/scratch: ' + str(p))
        if not writing and not _hashing and p.is_relative_to(ROOT) and not p.is_relative_to(HERE):
            key = str(p.relative_to(ROOT))
            if key not in INPUTS and p.is_file() and '/.venv/' not in str(p):
                _hashing = True
                try:
                    INPUTS[key] = sha(p)
                finally:
                    _hashing = False
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename', 'os.symlink', 'os.link', 'os.chmod', 'os.utime'):
        for item in args[:2] if event in ('os.rename', 'os.link', 'os.symlink') else args[:1]:
            if isinstance(item, (str, bytes, Path)):
                p = Path(os.fsdecode(item)).absolute().resolve()
                if not allowed_write(p):
                    raise PermissionError('Mutation outside look_ceiling_r1/scratch: ' + str(p))

sys.addaudithook(audit)

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
    p = HERE / p if not p.is_absolute() else p
    assert allowed_write(p.resolve())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')

def read(path):
    return json.loads(Path(path).read_text())

def finish(tag):
    dump(LOCAL / ('input_hashes_' + tag + '.json'), INPUTS)
    dump(LOCAL / ('receipt_' + tag + '.json'), dict(input_count=len(INPUTS), writes_confined=True,
        no_network=True, no_device_access=True, monotonic=time.monotonic()))

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj

SNAPSHOT = SCRATCH / 'studio_snapshot'
if not SNAPSHOT.exists():
    archive=LOCAL/'studio_source_snapshot.tar.gz'
    if archive.exists():
        import tarfile
        SNAPSHOT.mkdir()
        with tarfile.open(archive,'r:gz') as source:
            for member in source.getmembers():
                path=(SNAPSHOT/member.name).resolve()
                assert path.is_relative_to(SNAPSHOT) and member.isfile(),member.name
                path.parent.mkdir(parents=True,exist_ok=True)
                with source.extractfile(member) as inp,path.open('wb') as out:shutil.copyfileobj(inp,out)
    else:
        shutil.copytree(ROOT / 'studio/src', SNAPSHOT / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
sys.path.insert(0, str(SNAPSHOT / 'src'))
sys.path.insert(0, str(ROOT / 'research/vlog_alchemy_eval'))
support = module('support', ROOT / 'research/vlog_alchemy_eval/support.py')
support.HERE, support.SCRATCH, support.BUILD_DATA = HERE, SCRATCH, LOCAL
support.STUDIO_SNAPSHOT = SNAPSHOT
support.check_time = lambda: None
# Do not call the legacy setup: this module already owns the narrower fence.
support.setup = lambda: None
import numpy as np
import data as upstream
from gxr_studio.engine.colour import lab_from_codes, delta_e00, de00_components
from gxr_studio.engine import matrix_model as mm
sys.path.insert(0, str(ROOT / 'research/film_look_routes'))
from camera import Camera
from convert import samples
from fit import Problem as LegacyProblem, weights
fit_adapter = module('ceiling_upstream_fit', ROOT / 'research/vlog_alchemy_eval/fit_candidates.py')

def stats(values):
    v = np.asarray(values, float).ravel()
    assert np.isfinite(v).all()
    if not len(v):
        return dict(n=0, median=None, p95=None, max=None, mean=None)
    return dict(n=len(v), median=float(np.median(v)), p95=float(np.percentile(v, 95)),
                max=float(v.max()), mean=float(v.mean()))

def score(base, prediction, desired):
    p = np.asarray(prediction, float)
    err = delta_e00(lab_from_codes(p), lab_from_codes(desired))
    den = delta_e00(lab_from_codes(base), lab_from_codes(desired))
    median = float(np.median(den))
    return dict(label='电脑预测', de00=stats(err), baseline_de00=stats(den),
        similarity_percent=None if median < .25 else 100 * (1 - float(np.median(err)) / median))

def camera_for_unit(ui=0):
    """Unit-specific original rows, transferred 50mm response kernel, not a new calibration."""
    camera=Camera()
    if ui==0:return camera
    import struct
    from gxr_studio.engine.knobs import dec
    _,dat,_=upstream.camera_model()
    entry=dat.entry_of(ui,4)
    camera.row=mm.MatrixRow.from_bytes(entry[216:244])
    camera.curve=mm.Curve([0,*struct.unpack_from('>31H',entry,20),4095],list(entry[82:115]))
    coeff=np.array([[dec(z,128) for z in entry[i:i+4]] for i in range(115,211,4)])
    camera.A,camera.B=coeff[:,0],coeff[:,1]
    camera.initial_z=camera.fs.Z_of_words(camera.A,camera.B,camera.E.ctx)
    return camera
