"""Independent review: no network/devices; all writes confined to this directory."""
from pathlib import Path
import fcntl
import hashlib
import importlib.util
import json
import os
import plistlib
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ORIGINAL = ROOT / 'research/g156'
LOCAL = HERE / 'local'
TMP = LOCAL / 'tmp'
ENGINE = ROOT / 'firmware/engine_v68_g156'
BASE = ROOT / 'firmware/engine_v67_g155c'
RECORDS = ROOT / 'research/recipe_redo_r1'
PACKAGES = {p: ROOT / ('firmware/package_v310_g156' + ('_test' if p == 'test' else ''))
            for p in ('release', 'test')}
UNITS = ('a12-50', 'a12-28', 'mount-a12')
BUILTINS = ('01 GRPos', '02 GRNeg', '03 HC BW', '04 Std',
            '05 F-CC', '06 F-CN', '07 L-Chr', '08 L-Viv')
_LOCK = None
_READY = False

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

digest = sha

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

def save(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def guard(event, args):
    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('review: network forbidden')
    paths = []
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(path)).resolve()
            if str(p).startswith(('/dev/disk', '/dev/rdisk')):
                raise PermissionError('review: physical device forbidden')
        if ((isinstance(mode, str) and any(c in mode for c in 'wax+')) or
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            paths = [path]
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.truncate', 'os.utime'):
        paths = [args[0]]
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        paths = list(args[:2])
    for p in paths:
        if isinstance(p, (str, bytes, os.PathLike)):
            target = Path(os.fsdecode(p)).resolve()
            if target != Path('/dev/null') and not target.is_relative_to(HERE):
                raise PermissionError('review: out-of-scope write: ' + str(target))

def setup():
    global _LOCK, _READY
    if _READY:
        return
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
    assert not HERE.is_symlink()
    info=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert info['MountPoint']=='/Volumes/Workspace'and info['FilesystemType']=='apfs'
    assert info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['WritableVolume']and os.path.ismount('/Volumes/Workspace')
    sys.dont_write_bytecode = True
    sys.addaudithook(guard)
    for slot in range(2):
        lock = (LOCAL / ('process-slot-' + str(slot) + '.lock')).open('a')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _LOCK = lock
            break
        except BlockingIOError:
            lock.close()
    else:
        raise RuntimeError('review: two compute processes already active')
    TMP.mkdir(parents=True, exist_ok=True)
    os.environ.update(TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1',
                      CLANG_MODULE_CACHE_PATH=str(TMP / 'clang'), GIT_OPTIONAL_LOCKS='0')
    _READY = True

DF = load(ROOT / 'research/v39_g153/dat_format.py', 'review_g156_dat_format')
