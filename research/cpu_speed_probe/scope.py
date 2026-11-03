"""Write fence and frozen-input check for the CPU speed probe build and acceptance."""
from pathlib import Path
import hashlib, importlib.util, json, os, sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/cpuprobe')
OUTPUTS = (ROOT / 'firmware/engine_cpuprobe_v38', ROOT / 'firmware/package_v38_cpuprobe', HERE, SCRATCH)
# Inputs the build and the acceptance read; none of them may change while they run.
FROZEN = ('firmware/package_v36_g121/SD_ROOT/GXRCE.DAT',
          'firmware/resident_v38/local/resident/trust.json',
          'firmware/resident_v38/local/resident/build/resident.elf',
          'firmware/package_v38_g137/local/SD_ROOT/ilaunch3',
          'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT',
          'firmware/package_v38_g137/local/SD_ROOT/qlaunch3',
          'firmware/package_v38_g137/local/SD_ROOT/jlaunch3',
          'firmware/package_v38_g137/SHA256SUMS',
          'firmware/engine_v54_g137/candidate/local/full-r13/engine.elf',
          'artifacts/firmware/gxr-1.51/jlaunch3',
          'artifacts/firmware/gxr-1.51/qlaunch3',
          'artifacts/firmware/gxr-1.51/ilaunch3',
          'firmware/package_v36_g120b/SD_ROOT/l08firm3')


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
        raise PermissionError('CPUPROBE_NETWORK_DISABLED')
    for path in paths:
        p = Path(os.fsdecode(path)).resolve()
        if p != Path('/dev/null') and not any(p == base or p.is_relative_to(base) for base in OUTPUTS):
            raise PermissionError('CPUPROBE_WRITE_FENCE: ' + str(p))


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
