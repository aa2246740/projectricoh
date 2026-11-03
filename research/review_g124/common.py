"""Generation 124 paths, write fence and reproducible command records."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g124'
TREE = ROOT / 'firmware/engine_v46_ui'
PACKAGE = ROOT / 'firmware/package_v36_g124'
DAT = PACKAGE / 'SD_ROOT/GXRCE.DAT'
ELF = TREE / 'candidate/local/full-r13/engine.elf'
START_UTC = '2026-10-28T10:49:32Z'
DEADLINE_UTC = '2026-10-28T13:49:32Z'
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
        raise PermissionError('NETWORK_DISABLED')
    for path in paths:
        q = Path(os.fsdecode(path)).resolve()
        if not any(q.is_relative_to(root) for root in (OUT,)):
            raise PermissionError('WRITE_FENCE: ' + str(q))

sys.addaudithook(fence)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def save(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def run(args, label, timeout=1800, check=True):
    temporary = OUT / 'local/tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMPDIR=str(temporary), PYTHONDONTWRITEBYTECODE='1',
               LC_ALL='C', CLANG_MODULE_CACHE_PATH=str(temporary / 'modules'))
    result = subprocess.run([str(a) for a in args], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=timeout)
    (OUT / 'local' / (label + '.log')).write_text(result.stdout + result.stderr)
    with (OUT / 'commands.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(argv=[str(a) for a in args], label=label,
                                     returncode=result.returncode)) + '\n')
    if check and result.returncode:
        raise RuntimeError(label + ': ' + result.stdout[-1000:] + result.stderr[-2500:])
    return result
