"""Local-only research helpers. All writes stay in this research directory."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.dont_write_bytecode = True


def fence(event, args):
    paths = []
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)) and (
            isinstance(mode, str) and any(c in mode for c in 'wax+') or
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            paths.append(path)
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime', 'os.truncate'):
        paths.append(args[0])
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        paths.extend(args[:2])
    elif event.startswith('socket.') and event not in ('socket.__new__',):
        raise PermissionError('NETWORK_DISABLED: ' + event)
    for path in paths:
        target = Path(os.fsdecode(path)).resolve()
        if not target.is_relative_to(OUT):
            raise PermissionError('WRITE_FENCE: ' + str(target))


sys.addaudithook(fence)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return sha(Path(path).read_bytes())


def save(name, value):
    path = OUT / name
    assert path.resolve().is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if path.exists() and path.read_text() != body:
        old = path.read_bytes()
        history = OUT / 'local/history'
        history.mkdir(parents=True, exist_ok=True)
        (history / (path.stem+'-'+sha(old)[:16]+path.suffix)).write_bytes(old)
    path.write_text(body)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def native_modules():
    folder = ROOT / 'firmware/engine_v44_keep/native_harness'
    sys.path.insert(0, str(folder))
    import python_backend
    python_backend.CACHE = OUT / 'local/decode'
    import image_loader
    import harness
    return image_loader, python_backend, harness
