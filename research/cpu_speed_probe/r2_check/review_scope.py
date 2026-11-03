"""Copy of research/review_cpuprobe_r2/review_scope.py for the implementer's rerun of the second review's
boundary cases (paths changed: output research/cpu_speed_probe/r2_check, temp .../cpuprobe/r2)."""
from pathlib import Path
import hashlib
import json
import os
import sys

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/cpu_speed_probe/r2_check'
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/cpuprobe/r2')
ALLOWED = (OUT, TEMP)
PROTECTED = ('firmware/engine_cpuprobe_v38', 'firmware/package_v38_cpuprobe',
             'research/cpu_speed_probe/accept_cpuprobe.py', 'research/cpu_speed_probe/scope.py',
             'research/cpu_speed_probe/cache_native_probe.py', 'research/cpu_speed_probe/cache_effect_probe.py',
             'research/cpu_speed_probe/emu_boot.py', 'research/cpu_speed_probe/static_check.py',
             'firmware/resident_v38',
             'tools/gxr_emulator_batch', 'tools/native_harness',
             'firmware/package_v38_g137/local/SD_ROOT/ilaunch3',
             'firmware/package_v36_g121/SD_ROOT/GXRCE.DAT',
             'firmware/package_v36_g120b/SD_ROOT/l08firm3',
             'artifacts/firmware/gxr-1.51/ilaunch3',
             'artifacts/firmware/gxr-1.51/jlaunch3',
             'artifacts/firmware/gxr-1.51/qlaunch3')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    p = Path(path).resolve()
    assert any(p.is_relative_to(base) for base in ALLOWED), str(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + '\n')


def fence(event, args):
    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('REVIEW_NETWORK_DISABLED')
    paths = []
    if event == 'open':
        path, mode, flags = args
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        raw = os.fsdecode(path)
        if raw.startswith('/Volumes/') and not raw.startswith('/Volumes/Workspace/'):
            raise PermissionError('REVIEW_VOLUME_LIMIT')
        p = Path(raw).resolve()
        previous = ROOT / 'research/review_cpuprobe'
        if p == previous or p.is_relative_to(previous):
            raise PermissionError('REVIEW_READ_LIMIT')
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            paths.append(path)
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime', 'os.truncate'):
        paths.append(args[0])
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        paths.extend(args[:2])
    for path in paths:
        p = Path(os.fsdecode(path)).resolve()
        if p != Path('/dev/null') and not any(p == base or p.is_relative_to(base) for base in ALLOWED):
            raise PermissionError('REVIEW_WRITE_LIMIT: ' + str(p))


def enable():
    sys.dont_write_bytecode = True
    os.environ['TMPDIR'] = str(TEMP)
    os.environ['GXR_EMULATOR_BATCH'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.addaudithook(fence)


def files():
    result = {}
    for name in PROTECTED:
        p = ROOT / name
        assert p.exists(), str(p)
        entries = [p] if p.is_file() else sorted(p.rglob('*'))
        for item in entries:
            if item.is_file():
                result[str(item.relative_to(ROOT))] = dict(bytes=item.stat().st_size, sha256=digest(item))
    return result


def verify():
    before = json.loads((OUT / 'inputs-before.json').read_text())
    after = files()
    changes = [p for p in set(before) | set(after) if before.get(p) != after.get(p)]
    assert not changes, changes
    return len(before)


if __name__ == '__main__':
    enable()
    if sys.argv[1] == 'freeze':
        assert not (OUT / 'inputs-before.json').exists()
        records = files()
        save(OUT / 'inputs-before.json', records)
        print('frozen', len(records), 'bytes', sum(v['bytes'] for v in records.values()))
    else:
        print('unchanged', verify())
