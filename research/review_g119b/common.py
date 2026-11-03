"""Read-only gen119 acceptance review. One write root, no device or build."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
START_UTC = '2026-10-27T10:24:36Z'
DEADLINE_UTC = '2026-10-27T13:24:36Z'

def fence(event, args):
    targets = []
    if event == 'open':
        p, mode, flags = args
        if isinstance(p, (str, bytes, os.PathLike)) and (
            (isinstance(mode, str) and any(c in mode for c in 'wax+')) or
            (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))):
            targets.append(p)
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime'):
        targets.append(args[0])
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        targets.extend(args[:2])
    for p in targets:
        q = Path(os.fsdecode(p)).resolve()
        if not q.is_relative_to(OUT):
            raise PermissionError('REVIEW_WRITE_FENCE: ' + str(q))
    if event == 'subprocess.Popen':
        argv = args[1]
        command = Path(str(argv[0])).name if isinstance(argv, (list, tuple)) else str(argv)
        if command not in ('m32r-elf-objdump', 'm32r-elf-readelf', 'm32r-elf-nm', 'python3', 'shasum', 'expand'):
            raise PermissionError('REVIEW_NO_BUILD_OR_DEVICE: ' + command)

sys.dont_write_bytecode = True
sys.addaudithook(fence)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def save(name, value):
    p = (OUT / name).resolve()
    assert p.is_relative_to(OUT), p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m
