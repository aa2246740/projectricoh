"""Read-only inputs and bounded local research output."""
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
GROUPS = (
    'artifacts/downloads/gxr-151.zip',
    'artifacts/firmware/gxr-1.51',
    'firmware/resident_v36',
    'firmware/image_v36',
    'firmware/package_v36_g117',
    'firmware/engine_v38_b36',
    'firmware/engine_v42_ux',
    'tools/native_harness',
    'research/emulator_feasibility_r1/prototype/boot_probe.py',
    'research/firmware/ilaunch3-sections.csv',
    'research/tooling_m32r/prefix/bin/m32r-elf-objdump',
    'research/review_v36_body',
    'research/review_v35_body',
    'research/ux_preview_dot_r2',
    'research/ux_preview_dot_r4',
)
PINS = {
    'artifacts/downloads/gxr-151.zip': '3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898',
    'artifacts/firmware/gxr-1.51/ilaunch3': 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
    'firmware/image_v36/local/package/SD_ROOT/ilaunch3': '50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008',
    'firmware/resident_v36/local/resident/build/resident.elf': '5d66184ce33f280aa370ebfc1753fe74e8ad398f01558406909733cec779acff',
    'firmware/package_v36_g117/SD_ROOT/GXRCE.DAT': '35ce20ac843764b9cdd452785683ebf99004c47b77ae90720c2e3dc716c31211',
    'firmware/engine_v38_b36/candidate/local/full-r13/engine.elf': '75a262a0ad91f605762a75350ba0a8905baaf2e116300e945609eb0d2d6711fc',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(name, value):
    target = OUT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        old = target.read_bytes()
        old_path = target.with_name(target.stem+'.previous-'+sha(old)[:12]+target.suffix)
        if not old_path.exists():
            old_path.write_bytes(old)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def inside(path):
    if isinstance(path, int):
        return True
    return Path(os.fsdecode(path)).resolve().is_relative_to(OUT)


def audit(event, args):
    if event == 'open':
        path, mode, flags = args
        writable = isinstance(mode, str) and any(c in mode for c in 'wax+')
        writable |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if writable and not inside(path):
            raise PermissionError('research output boundary')
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.chown', 'os.utime'):
        if not inside(args[0]):
            raise PermissionError('research output boundary')
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        if not all(inside(p) for p in args[:2]):
            raise PermissionError('research output boundary')
    elif event.startswith('socket.'):
        raise PermissionError('offline research')
    elif event == 'subprocess.Popen':
        executable = str(args[0])
        if Path(executable).resolve() != (ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump').resolve():
            raise PermissionError('only existing disassembler is permitted')


sys.addaudithook(audit)


def verify_pins():
    rows = []
    for name, expected in PINS.items():
        raw = (ROOT / name).read_bytes()
        actual = sha(raw)
        assert actual == expected, name
        rows.append(dict(path=name, bytes=len(raw), sha256=actual))
    with zipfile.ZipFile(ROOT / 'artifacts/downloads/gxr-151.zip') as z:
        names = [n for n in z.namelist() if n.rsplit('/', 1)[-1] == 'ilaunch3']
        assert len(names) == 1
        raw = z.read(names[0])
        assert sha(raw) == PINS['artifacts/firmware/gxr-1.51/ilaunch3']
        rows.append(dict(path='official ZIP member ilaunch3', bytes=len(raw), sha256=sha(raw)))
    return rows


def snapshot():
    files = {}
    groups = []
    for number, name in enumerate(GROUPS):
        base = ROOT / name
        paths = sorted(base.rglob('*')) if base.is_dir() else [base]
        count = total = 0
        for p in paths:
            if not p.is_file():
                continue
            rel = str(p.relative_to(ROOT))
            key = sha(rel.encode())
            raw = p.read_bytes()
            files[key] = dict(bytes=len(raw), sha256=sha(raw))
            count += 1
            total += len(raw)
        groups.append(dict(path=name, files=count, bytes=total))
    return dict(groups=groups, files=files, file_count=len(files))


def freeze():
    pins = verify_pins()
    save('input-pins.json', pins)
    before = OUT / 'inputs-before.json'
    if before.exists():
        raise FileExistsError('initial snapshot already exists')
    value = snapshot()
    save('inputs-before.json', value)
    print(json.dumps(dict(status='PASS', files=value['file_count'], groups=value['groups'])))


def check_inputs():
    verify_pins()
    before = json.loads((OUT / 'inputs-before.json').read_text())
    after = snapshot()
    save('inputs-after.json', after)
    old, new = before['files'], after['files']
    changed = [k for k in sorted(old.keys() | new.keys()) if old.get(k) != new.get(k)]
    result = dict(status='PASS' if not changed else 'FAIL', before=before['file_count'],
                  after=after['file_count'], changed_file_ids=changed)
    save('input-integrity.json', result)
    print(json.dumps(result))
    assert not changed


if __name__ == '__main__':
    {'freeze': freeze, 'check': check_inputs}[sys.argv[1]]()
