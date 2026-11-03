"""Host-only evidence fence for the structural colour study."""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
HERE = Path(__file__).resolve().parent
LOCAL = HERE / 'local'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/structural-colour-r1')
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['TMPDIR'] = str(SCRATCH)
os.environ['GIT_OPTIONAL_LOCKS'] = '0'

import hashlib
import json
import plistlib
import subprocess
import time

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as src:
        for block in iter(lambda: src.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

assert os.getpriority(os.PRIO_PROCESS, 0) >= 15, 'Run with nice -n 15'
volume = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
assert Path('/Volumes/Workspace').is_mount()
assert volume.get('DiskUUID') == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
assert volume['FilesystemType'] == 'apfs' and volume['WritableVolume'] and volume['WritableMedia']
LOCAL.mkdir(parents=True, exist_ok=True)
SCRATCH.mkdir(parents=True, exist_ok=True)
INPUTS = {}
_hashing = False

def confined(path):
    return path.is_relative_to(HERE) or path.is_relative_to(SCRATCH)

def audit(event, args):
    global _hashing
    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('Network outside this study')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        p = Path(os.fsdecode(args[0])).absolute().resolve()
        if str(p).startswith('/Volumes/') and not p.is_relative_to(ROOT) and not p.is_relative_to(SCRATCH):
            raise PermissionError('Volume read outside study: ' + str(p))
        if str(p).startswith('/dev/') and str(p) not in ('/dev/null', '/dev/urandom', '/dev/random'):
            raise PermissionError('Device outside this study')
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing and not confined(p):
            raise PermissionError('Write outside task: ' + str(p))
        if not writing and not _hashing and p.is_relative_to(ROOT) and not p.is_relative_to(HERE):
            key = str(p.relative_to(ROOT))
            if key not in INPUTS and p.is_file() and '/.venv/' not in str(p):
                _hashing = True
                try:
                    INPUTS[key] = sha(p)
                finally:
                    _hashing = False
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename', 'os.symlink', 'os.link', 'os.chmod', 'os.utime'):
        count = 2 if event in ('os.rename', 'os.symlink', 'os.link') else 1
        for arg in args[:count]:
            if isinstance(arg, (str, bytes, Path)) and not confined(Path(os.fsdecode(arg)).absolute().resolve()):
                raise PermissionError('Mutation outside task')
    if event == 'subprocess.Popen':
        executable = str(args[0])
        allowed = (str(ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'), '/usr/sbin/diskutil')
        if executable not in allowed:
            raise PermissionError('Subprocess outside static tool allowlist: ' + executable)

sys.addaudithook(audit)

def dump(path, obj):
    p = Path(path)
    if not p.is_absolute():
        p = HERE / p
    assert confined(p.resolve())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

def finish(tag):
    changed = [key for key, value in INPUTS.items() if sha(ROOT / key) != value]
    dump(LOCAL / ('inputs_' + tag + '.json'), INPUTS)
    dump(LOCAL / ('receipt_' + tag + '.json'), dict(input_count=len(INPUTS), changed=changed,
        nice=os.getpriority(os.PRIO_PROCESS, 0), threads=1, no_network=True, no_device_access=True,
        writes_confined=True, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())))
    assert not changed, changed
