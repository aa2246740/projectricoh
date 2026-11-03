"""Local review boundary and input identity checks for generation 142."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
HERE = ROOT / 'research/review_diag142'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-diag142')
OUTPUTS = (HERE, SCRATCH)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def fence(event, args):
    paths = []
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)):
            resolved = Path(os.fsdecode(path)).resolve()
            if resolved == Path('/Volumes/RICOHDCX') or Path('/Volumes/RICOHDCX') in resolved.parents:
                raise PermissionError('REVIEW_CARD_ACCESS_DISABLED')
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                    isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
                paths.append(path)
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime', 'os.truncate'):
        paths.append(args[0])
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        paths.extend(args[:2])
    elif event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('REVIEW_NETWORK_DISABLED')
    for path in paths:
        if isinstance(path, int):
            continue
        p = Path(os.fsdecode(path)).resolve()
        if p != Path('/dev/null') and not any(p == base or base in p.parents for base in OUTPUTS):
            raise PermissionError('REVIEW_WRITE_FENCE: ' + str(p))


def enable_fence():
    sys.dont_write_bytecode = True
    os.environ['TMPDIR'] = str(SCRATCH)
    sys.addaudithook(fence)
    SCRATCH.mkdir(exist_ok=True)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(path, value):
    p = Path(path).resolve()
    if not any(p == base or base in p.parents for base in OUTPUTS):
        raise PermissionError('REVIEW_SAVE_FENCE: ' + str(p))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def inputs():
    files = set()
    trees = ('firmware/engine_diag_v38', 'firmware/resident_v38/resident',
             'firmware/engine_v54_g137/candidate/containers/product', 'tools/native_harness')
    for name in trees:
        for path in (ROOT / name).rglob('*'):
            if path.is_file() and 'local' not in path.relative_to(ROOT / name).parts and '__pycache__' not in path.parts:
                files.add(path)
    for name in ('research/unit28_stock',):
        files.update(p for p in (ROOT / name).iterdir() if p.is_file())
    names = ('firmware/package_v38_diag/SD_ROOT/GXRCE.DAT',
             'firmware/package_v38_diag/SHA256SUMS',
             'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT',
             'firmware/package_v38_g137/local/SD_ROOT/ilaunch3',
             'firmware/package_v38_g137/local/SD_ROOT/jlaunch3',
             'firmware/package_v38_g137/local/SD_ROOT/qlaunch3',
             'firmware/package_v38_g137/local/SD_ROOT/l08firm3',
             'firmware/engine_diag_v38/candidate/local/full-r1/GXRCE.DAT',
             'firmware/engine_diag_v38/candidate/local/full-r1/engine.bin',
             'firmware/engine_diag_v38/candidate/local/full-r1/engine.elf',
             'firmware/engine_diag_v38/candidate/local/full-r1/layout.json',
             'firmware/resident_v38/local/resident/trust.json',
             'firmware/resident_v38/local/resident/build/resident.elf')
    files.update(ROOT / name for name in names)
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)}


def freeze_check():
    records = json.loads((HERE / 'inputs-before.json').read_text())
    changed = [name for name, digest in records.items() if sha(ROOT / name) != digest]
    if changed:
        raise RuntimeError('REVIEW_INPUT_CHANGED: ' + repr(changed))
    return len(records)


if __name__ == '__main__':
    enable_fence()
    if len(sys.argv) > 1 and sys.argv[1] == 'check':
        print('INPUTS_UNCHANGED', freeze_check())
    else:
        save(HERE / 'inputs-before.json', inputs())
        print('INPUTS_FROZEN', len(json.loads((HERE / 'inputs-before.json').read_text())))
