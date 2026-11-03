"""Local offline review boundary and JSON helpers."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-diag147-r3')
OUTPUTS = (HERE, SCRATCH)


def fence(event, args):
    if event.startswith('socket.'):
        raise PermissionError('REVIEW_NETWORK_DISABLED')
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path, mode, flags = args
        p = Path(os.fsdecode(path)).resolve()
        old = ROOT / 'research/review_diag147'
        older = ROOT / 'research/review_diag147_r2'
        if p == older or older in p.parents or (p == old or old in p.parents) and p != old / 'cache_review.py':
            raise PermissionError('REVIEW_READ_LIMIT: ' + str(p))
        if str(p).startswith('/Volumes/') and not (p == Path('/Volumes/Workspace') or Path('/Volumes/Workspace') in p.parents):
            raise PermissionError('REVIEW_VOLUME_LIMIT: ' + str(p))
        writing = isinstance(mode, str) and any(x in mode for x in 'wax+')
        writing = writing or isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        paths = [p] if writing else []
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime', 'os.truncate'):
        paths = [args[0]]
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        paths = list(args[:2])
    else:
        paths = []
    for path in paths:
        p = Path(os.fsdecode(path)).resolve()
        if p != Path('/dev/null') and not any(p == d or d in p.parents for d in OUTPUTS):
            raise PermissionError('REVIEW_WRITE_LIMIT: ' + str(p))


def enable_fence():
    sys.dont_write_bytecode = True
    sys.addaudithook(fence)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    p = Path(path).resolve()
    if not any(p == d or d in p.parents for d in OUTPUTS):
        raise PermissionError('REVIEW_WRITE_LIMIT: ' + str(p))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def freeze_check():
    rows = json.loads((HERE / 'inputs-before.json').read_text())
    changed = [name for name, row in rows.items() if sha(ROOT / name) != row['sha256']]
    assert not changed, changed
    return len(rows)
