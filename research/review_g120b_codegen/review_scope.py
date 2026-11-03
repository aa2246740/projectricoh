"""Read-only inputs and one output directory for the generation 120 review."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SOURCE = ROOT / 'research/ux_preview_dot_r5'
READS = set()
sys.dont_write_bytecode = True


def fence(event, args):
    paths = []
    if event == 'open':
        path, mode, flags = args
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        writing = ((isinstance(mode, str) and any(c in mode for c in 'wax+')) or
                   (isinstance(flags, int) and flags &
                    (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)))
        if writing:
            paths.append(path)
        else:
            READS.add(str(Path(os.fsdecode(path)).resolve()))
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime'):
        paths.append(args[0])
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        paths.extend(args[:2])
    elif event in ('socket.connect', 'socket.bind'):
        raise PermissionError('NETWORK_DISABLED')
    for path in paths:
        resolved = Path(os.fsdecode(path)).resolve()
        if not resolved.is_relative_to(OUT):
            raise PermissionError('REVIEW_WRITE_FENCE: ' + str(resolved))


sys.addaudithook(fence)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(name, value):
    path = (OUT / name).resolve()
    assert path.is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def record_inputs(name):
    rows = []
    for text in sorted(READS):
        path = Path(text)
        if path.is_relative_to(ROOT) and not path.is_relative_to(OUT) and path.is_file():
            rows.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                             sha256=file_sha(path)))
    save(name, rows)
