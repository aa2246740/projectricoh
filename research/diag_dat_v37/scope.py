"""Write fence and frozen-input check for the v3.7 diagnostic build."""
from pathlib import Path
import hashlib, importlib.util, json, os, sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUTS = (ROOT / 'firmware/engine_diag_v37', ROOT / 'firmware/package_v37_diag', HERE)
# Inputs the build reads; none of them may change while it runs.
FROZEN = ('firmware/package_v36_g121/SD_ROOT/GXRCE.DAT',
          'firmware/resident_v37/local/resident/trust.json',
          'firmware/package_v37_redisplay/SD_ROOT/ilaunch3',
          'firmware/package_v37_redisplay/SD_ROOT/GXRCE.DAT',
          'firmware/engine_v52_redisplay/candidate/local/full-r13/engine.elf',
          'firmware/resident_v37/local/resident/build/resident.elf')


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
        raise PermissionError('DIAG37_NETWORK_DISABLED')
    for path in paths:
        p = Path(os.fsdecode(path)).resolve()
        if p != Path('/dev/null') and not any(p == base or p.is_relative_to(base) for base in OUTPUTS):
            raise PermissionError('DIAG37_WRITE_FENCE: ' + str(p))


def enable_fence():
    sys.dont_write_bytecode = True
    sys.addaudithook(fence)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    p = Path(path).resolve()
    if not any(p == d or d in p.parents for d in OUTPUTS):
        raise RuntimeError('WRITE_LIMIT')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def freeze_check():
    records = json.loads((HERE / 'local/inputs-before.json').read_text())
    changed = [p for p, h in records.items() if not (ROOT / p).is_file() or sha(ROOT / p) != h]
    if changed:
        raise RuntimeError('FROZEN_INPUT_CHANGED ' + repr(changed))
    return len(records)


if __name__ == '__main__':
    save(HERE / 'local/inputs-before.json', {p: sha(ROOT / p) for p in FROZEN})
    print('froze', len(FROZEN))
