"""Task write fence and offline helpers. Run with /usr/bin/python3 -I -B."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
ENGINE = ROOT / 'firmware/engine_diag_v1'
PACKAGE = ROOT / 'firmware/package_v36_diag1'
ALLOWED = (OUT, ENGINE, PACKAGE)
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
    elif event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('DIAG_NETWORK_DISABLED')
    for path in paths:
        p = Path(os.fsdecode(path)).resolve()
        if not any(p == base or p.is_relative_to(base) for base in ALLOWED):
            raise PermissionError('DIAG_WRITE_FENCE: ' + str(p))


sys.addaudithook(fence)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def freeze_check():
    before = json.loads((OUT / 'inputs-before.json').read_text())
    changed = [p for p, digest in before.items() if not (ROOT / p).is_file() or sha(ROOT / p) != digest]
    # This shared orchestration log is observed, never consumed by the build.
    external = [p for p in changed if p == 'decisions.tsv']
    protected = [p for p in changed if p != 'decisions.tsv']
    if external:
        save(OUT / 'external-coordination-drift.json', {p:dict(before=before[p],after=sha(ROOT/p)) for p in external})
    assert not protected, protected
    return len(before) - 1
