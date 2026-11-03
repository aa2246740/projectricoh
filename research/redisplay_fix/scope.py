"""Offline write fence and input identity for the redisplay investigation."""
from pathlib import Path
import atexit
import hashlib
import importlib.util
import json
import os
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ALLOWED = tuple(ROOT / x for x in (
    'research/redisplay_fix', 'firmware/resident_v37',
    'firmware/engine_v52_redisplay', 'firmware/package_v37_redisplay'))
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
        raise PermissionError('REDISPLAY_NETWORK_DISABLED')
    for path in paths:
        p = Path(os.fsdecode(path)).resolve()
        if p != Path('/dev/null') and not any(p == base or p.is_relative_to(base) for base in ALLOWED):
            raise PermissionError('REDISPLAY_WRITE_FENCE: ' + str(p))


sys.addaudithook(fence)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    p = HERE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def freeze():
    p = HERE / 'inputs-before.json'
    if p.exists():
        return
    paths = set()
    for tree in ('tools/native_harness', 'firmware/resident_v36', 'firmware/image_v36',
                 'firmware/engine_v48_own', 'firmware/engine_v43_fix', 'research/g127_fix'):
        base = ROOT / tree
        paths.update(x for x in base.rglob('*') if x.is_file() and
                     not any(t in ('local', '__pycache__') for t in x.relative_to(base).parts))
    for name in ('firmware/package_v36_g120b/SD_ROOT/ilaunch3',
                 'firmware/package_v36_g127/SD_ROOT/GXRCE.DAT',
                 'firmware/resident_v36/local/resident/build/resident.elf',
                 'firmware/resident_v36/local/resident/trust.json',
                 'firmware/engine_v48_own/candidate/local/full-r13/engine.elf',
                 'research/emulator_feasibility_r1/prototype/boot_probe.py',
                 'research/tooling_m32r/prefix/bin/m32r-elf-objdump',
                 'captures/diag-v3-field-20261029/READINGS.txt',
                 'research/redisplay_fix/BRIEF.md'):
        paths.add(ROOT / name)
    save('inputs-before.json', {str(x.relative_to(ROOT)): sha(x) for x in sorted(paths)})


def check_inputs():
    before = json.loads((HERE / 'inputs-before.json').read_text())
    changed = {name: {'before': value, 'after': sha(ROOT / name) if (ROOT / name).is_file() else None}
               for name, value in before.items() if not (ROOT / name).is_file() or sha(ROOT / name) != value}
    save('inputs-after.json', {'protected': len(before), 'changed': changed})
    return changed


def dependencies():
    files = {Path(m.__file__).resolve() for m in tuple(sys.modules.values())
             if getattr(m, '__file__', None) and Path(m.__file__).is_file()
             and Path(m.__file__).resolve().is_relative_to(ROOT)}
    save('local/dependencies-' + str(os.getpid()) + '.json',
         {str(p.relative_to(ROOT)): sha(p) for p in sorted(files) if p.suffix == '.py'})


atexit.register(dependencies)


if __name__ == '__main__':
    freeze()
    profile = '(version 1)\n(allow default)\n(deny network*)\n(deny file-write*)\n'
    profile += '\n'.join('(allow file-write* (subpath ' + json.dumps(str(p)) + '))' for p in ALLOWED)
    profile += '\n(allow file-write* (literal "/dev/null"))\n'
    (HERE / 'offline.sb').write_text(profile)
    save('session.json', {'start_utc': '2026-10-29T06:59:41Z',
                         'deadline_utc': '2026-10-29T09:29:41Z',
                         'process_policy': 'one serial Python job and at most one child process',
                         'network': False, 'devices': False,
                         'allowed': [str(p) for p in ALLOWED]})
    print('Protected inputs frozen; offline write fence ready.')
