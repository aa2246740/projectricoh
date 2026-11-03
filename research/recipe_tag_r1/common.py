"""Shared paths and write fences for this offline research only."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/recipe-tag-r1')
sys.dont_write_bytecode = True
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['TMPDIR'] = str(TMP)
os.environ['GXR_HARNESS_BACKEND'] = os.environ.get('GXR_HARNESS_BACKEND', 'c')
os.environ['GXR_RENDER_WORKERS'] = '1'
INPUTS: dict[str, str] = {}
_hashing = False


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def writable(path):
    p = Path(os.path.abspath(os.fsdecode(path))).resolve()
    return p.is_relative_to(HERE) or p.is_relative_to(TMP)


def audit(event, args):
    global _hashing
    if event.startswith('socket.') or event in ('subprocess.Popen', 'os.system', 'os.posix_spawn'):
        raise PermissionError('Offline research does not start network or child processes')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        p = Path(os.path.abspath(os.fsdecode(args[0])))
        if str(p).startswith('/Volumes/') and not p.is_relative_to(Path('/Volumes/Workspace')):
            raise PermissionError('Other volumes are outside the research input scope')
        p = p.resolve()
        if str(p).startswith('/Volumes/') and not p.is_relative_to(Path('/Volumes/Workspace')):
            raise PermissionError('Resolved path is outside Workspace')
        protected = (Path.home()/'Pictures/GXR Studio', Path.home()/'Library/Application Support/GXR Studio')
        if any(p.is_relative_to(q) for q in protected):
            raise PermissionError('Owner Studio data is outside the research input scope')
        mode, flags = args[1:3]
        write = isinstance(mode, str) and any(c in mode for c in 'wax+')
        write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if write and not writable(p):
            raise PermissionError('Write outside research output scope: '+str(p))
        if not write and not _hashing and p.is_relative_to(ROOT) and not writable(p) and p.is_file():
            rel = str(p.relative_to(ROOT))
            if rel not in INPUTS:
                _hashing = True
                try:
                    INPUTS[rel] = sha(p)
                finally:
                    _hashing = False
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename'):
        for p in args[:2 if event == 'os.rename' else 1]:
            if isinstance(p, (str, bytes, Path)) and not writable(p):
                raise PermissionError('Mutation outside research output scope: '+str(p))


def guard(seconds=1800, require_tmp=True):
    if not Path('/Volumes/Workspace').is_mount() or (require_tmp and not TMP.is_dir()):
        raise RuntimeError('Check the Workspace volume and create the declared scratch directory first')
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Research time budget exceeded')))
    signal.alarm(seconds)
    sys.addaudithook(audit)


def plain(v):
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if isinstance(v, Path):
        return str(v)
    if hasattr(v, 'tolist'):
        return plain(v.tolist())
    return v


def dump(name, value):
    p = HERE/name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def finish(name):
    changed = [p for p, h in INPUTS.items() if sha(ROOT/p) != h]
    dump(name+'-receipt.json', dict(time_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
         python=sys.version, executable=sys.executable, inputs=INPUTS, changed=changed,
         research_scripts={p.name:sha(p) for p in sorted(HERE.glob('*.py'))},
         offline=True, write_scope='research/recipe_tag_r1 and declared scratch only'))
    if changed:
        raise RuntimeError('Read inputs changed during execution: '+str(changed))
