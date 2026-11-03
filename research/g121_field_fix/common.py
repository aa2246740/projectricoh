"""Generation 121 paths and a process-local write fence."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
TREE = ROOT / 'firmware/engine_v43_fix'
PACKAGE = ROOT / 'firmware/package_v36_g121'
DAT = PACKAGE / 'SD_ROOT/GXRCE.DAT'
BASE_DAT = ROOT / 'firmware/package_v36_g120b/SD_ROOT/GXRCE.DAT'
DAT_SHA = hashlib.sha256(DAT.read_bytes()).hexdigest() if DAT.exists() else ''
START_UTC = '2026-10-28T00:44:36Z'
DEADLINE_UTC = '2026-10-28T03:44:36Z'
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
    elif event in ('socket.connect', 'socket.bind'):
        raise PermissionError('NETWORK_DISABLED')
    for path in paths:
        q = Path(os.fsdecode(path)).resolve()
        if not any(q.is_relative_to(root) for root in (OUT, TREE, PACKAGE)):
            raise PermissionError('WRITE_FENCE: ' + str(q))

sys.addaudithook(fence)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    return sha(Path(path).read_bytes())

def save(name, value):
    p = (OUT / name).resolve()
    assert p.is_relative_to(OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    guard = sys.modules.get('runtime_guard')
    if isinstance(value, dict) and guard:
        value = dict(value, native_state_audits=guard.AUDITS)
    body=json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if p.exists() and p.read_text()!=body:
        history=OUT/'history';history.mkdir(exist_ok=True)
        old=p.read_bytes()
        (history/(p.stem+'-'+sha(old)[:16]+p.suffix)).write_bytes(old)
    p.write_text(body)

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
