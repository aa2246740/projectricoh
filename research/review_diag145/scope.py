"""g145 复审的写入边界与输入身份核对。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
HERE = ROOT / 'research/review_diag145'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-diag145')
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
            p = Path(os.fsdecode(path)).resolve()
            if p == Path('/Volumes/RICOHDCX') or Path('/Volumes/RICOHDCX') in p.parents:
                raise PermissionError('禁止访问卡')
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
                paths.append(path)
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime', 'os.truncate'):
        paths.append(args[0])
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        paths.extend(args[:2])
    elif event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('复审禁用网络')
    for path in paths:
        if isinstance(path, int):
            continue
        p = Path(os.fsdecode(path)).resolve()
        if p != Path('/dev/null') and not any(p == base or base in p.parents for base in OUTPUTS):
            raise PermissionError('复审写入边界: ' + str(p))

def enable_fence():
    sys.dont_write_bytecode = True
    os.environ.update(TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
    sys.addaudithook(fence)
    SCRATCH.mkdir(parents=True, exist_ok=True)

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def save(path, value):
    p = Path(path).resolve()
    assert any(p == b or b in p.parents for b in OUTPUTS)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')

def inputs():
    files = set()
    for name in ('firmware/engine_diag_v38_g144', 'firmware/engine_diag_v38_g145',
                 'firmware/package_v38_diag144', 'firmware/package_v38_diag145',
                 'firmware/resident_v38/resident', 'tools/gxr_emulator', 'tools/native_harness'):
        files.update(p for p in (ROOT / name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.update(p for p in (ROOT / 'research/unit28_stock').iterdir() if p.is_file())
    for name in ('firmware/package_v38_g137/local/SD_ROOT/ilaunch3',
                 'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT',
                 'artifacts/firmware/gxr-1.51/ilaunch3',
                 'firmware/resident_v38/local/resident/trust.json',
                 'firmware/resident_v38/local/resident/build/resident.elf',
                 'firmware/package_v36_g121/SD_ROOT/GXRCE.DAT',
                 'research/review_diag144/REVIEW.md', 'research/review_diag142/REVIEW.md'):
        files.add(ROOT / name)
    for run in ('run1', 'run2'):
        files.update(p for p in (ROOT / 'research/emulator_m2d/local/unit28-g145' / run).iterdir() if p.is_file())
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)}

def freeze_check():
    records = json.loads((HERE / 'inputs-before.json').read_text())
    changed = [p for p, h in records.items() if not (ROOT / p).is_file() or sha(ROOT / p) != h]
    if changed:
        raise RuntimeError('输入身份变化: ' + repr(changed))
    return len(records)

if __name__ == '__main__':
    enable_fence()
    if len(sys.argv) > 1 and sys.argv[1] == 'check':
        save(HERE / 'inputs-after.json', inputs())
        print('输入核对通过', freeze_check())
    else:
        save(HERE / 'inputs-before.json', inputs())
        print('已封存输入', len(json.loads((HERE / 'inputs-before.json').read_text())))
