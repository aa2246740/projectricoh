"""Offline review paths and Python audit boundary."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-harness-c-r2')

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def emit(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def enable(create_tmp=True):
    os.environ.update(TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1',
                      GIT_OPTIONAL_LOCKS='0', CLANG_MODULE_CACHE_PATH=str(TMP/'clang-modules'))
    tempfile.tempdir = str(TMP)
    if create_tmp:
        TMP.mkdir(parents=True, exist_ok=True)
    if os.getpriority(os.PRIO_PROCESS, 0) < 10:
        raise RuntimeError('run with nice -n 10')
    def check(value, writing=False):
        if value is None or isinstance(value, int):
            return
        path = Path(os.fsdecode(value)).resolve()
        if path.is_relative_to('/Volumes') and not path.is_relative_to('/Volumes/Workspace'):
            raise PermissionError('external medium access refused: ' + str(path))
        if writing and path != Path('/dev/null') and not any(path.is_relative_to(base) for base in (HERE, TMP)):
            raise PermissionError('review write boundary refused: ' + str(path))
    def audit(event, args):
        if event == 'open':
            path, mode, flags = args
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(
                (flags or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            check(path, writing)
        elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.truncate', 'os.utime'):
            check(args[0], True)
        elif event in ('os.rename', 'os.symlink', 'os.link'):
            check(args[0], True); check(args[1], True)
        elif event in ('os.listdir', 'os.scandir', 'os.chdir'):
            check(args[0])
        elif event.startswith('socket.'):
            raise PermissionError('network access refused')
    sys.addaudithook(audit)

def state(b):
    return dict(r=list(b.core.r), psw=b.core.psw, bpsw=b.core.bpsw,
                bbpsw=b.core.bbpsw, cr=dict(b.core.cr), acc=b.core.acc,
                current_pc=b.core.current_pc, pc=b.pc, ops=dict(b.core.ops),
                core_calls=list(b.core.calls), visits=dict(b.visits),
                tail=list(b.tail), total_steps=b.total_steps, running=b.running,
                writer_pc=b.writer_pc, origin=b.origin,
                regions=[dict(base=base, size=len(data), writable=writable,
                              sha256=hashlib.sha256(data).hexdigest())
                         for base, data, writable in b.regions])
