"""Generation 120 quality repair helpers and three-directory write fence."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
TREE = ROOT / 'firmware/engine_v42_ux'
PACKAGE = ROOT / 'firmware/package_v36_g120b'
WRITE_ROOTS = (OUT, TREE, PACKAGE)
START_UTC = '2026-10-27T14:49:00Z'
DEADLINE_UTC = '2026-10-27T17:49:00Z'
sys.dont_write_bytecode = True

def fence(event, args):
    paths = []
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)) and (
            isinstance(mode, str) and any(c in mode for c in 'wax+') or
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            paths.append(path)
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime'):
        paths.append(args[0])
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        paths.extend(args[:2])
    for path in paths:
        q = Path(os.fsdecode(path)).resolve()
        if not any(q.is_relative_to(root) for root in WRITE_ROOTS):
            raise PermissionError('QUALITY_WRITE_FENCE: ' + str(q))

sys.addaudithook(fence)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def save(name, value):
    p = (OUT / name).resolve()
    assert p.is_relative_to(OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
