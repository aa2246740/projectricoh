"""Freeze inputs and copy v3.3 sources. Writes stay inside the two v3.4 trees."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
IMAGE = ROOT / 'firmware/image_v34'
SCOPES = (
    'artifacts/firmware/gxr-1.51', 'artifacts/v32-trial/full-r3-20261024',
    'firmware/resident_v33', 'firmware/image_v33', 'firmware/resident_v32',
    'firmware/image_v3', 'firmware/engine_fix_r2',
    'research/boot_inert_v34', 'research/iso100_fix', 'research/gxr_deep_access',
    'research/review_full_r4', 'research/review_full_r6', 'research/review_full_r7',
    'research/review_flash_v33', 'research/bw03_standard_mode',
    'research/tooling_m32r/prefix/bin/m32r-elf-objdump',
    'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc',
    'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld',
)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def guard():
    raw = subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace'])
    v = plistlib.loads(raw)
    assert v['MountPoint'] == '/Volumes/Workspace' and v['FilesystemType'] == 'apfs'
    assert v['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert v['WritableVolume'] and v['WritableMedia'] and os.access(HERE, os.W_OK)
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/resident_v34')
    assert not HERE.is_symlink() and not IMAGE.is_symlink()
    return raw


def inventory():
    paths = {ROOT / p for p in subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0') if p}
    for rel in SCOPES:
        path = ROOT / rel
        assert path.exists(), rel
        paths.update(path.rglob('*') if path.is_dir() else [path])
    # Include the historical protected set, without changing its old ledger.
    for manifest in ('research/boot_inert_v34/local/inputs-start.json',
                     'research/boot_inert_v34/local/extra-inputs.json',
                     'research/review_flash_v33/local/inputs-before.json'):
        path = ROOT / manifest
        if path.exists():
            paths.update(ROOT / p for p in json.loads(path.read_text()))
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)
            if p.is_file() and not p.is_symlink() and p.name != 'decisions.tsv'
            and '__pycache__' not in p.parts and HERE not in p.parents and IMAGE not in p.parents}


def check():
    guard()
    frozen = json.loads((LOCAL / 'inputs-before.json').read_text())
    changes = [p for p, digest in frozen.items()
               if not (ROOT / p).is_file() or sha(ROOT / p) != digest]
    assert not changes, 'STOP_PROTECTED_INPUT_CHANGED: ' + repr(changes)
    print('PASS protected inputs unchanged:', len(frozen), '; decisions.tsv excluded')
    return len(frozen)


def copy_source(source, target):
    for p in sorted(source.rglob('*')):
        rel = p.relative_to(source)
        if not p.is_file() or any(x in ('local', '__pycache__', '.DS_Store') for x in rel.parts):
            continue
        assert not p.is_symlink()
        out = target / rel
        assert not out.exists(), str(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, out)


def main():
    if len(sys.argv) == 2 and sys.argv[1] == 'check':
        check()
        return
    raw = guard()
    space = subprocess.check_output(['/bin/df', '-h', '/Volumes/Workspace'])
    assert not (LOCAL / 'inputs-before.json').exists(), 'Never replace the initial inventory'
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / 'preflight.plist').write_bytes(raw)
    (LOCAL / 'df-h.txt').write_bytes(space)
    (LOCAL / 'inputs-before.json').write_text(json.dumps(inventory(), indent=2) + '\n')
    (LOCAL / 'initial-git-status.txt').write_bytes(subprocess.check_output(
        ['git', 'status', '--short'], cwd=ROOT, env=dict(os.environ, GIT_OPTIONAL_LOCKS='0')))
    base = ROOT / 'firmware/resident_v33'
    for name in ('resident', 'engine_services'):
        copy_source(base / name, HERE / name)
    (LOCAL / 'resident').mkdir()
    shutil.copyfile(base / 'local/resident/hooks.json', LOCAL / 'resident/hooks.json')
    (LOCAL / 'controls').mkdir()
    for p in (ROOT / 'research/boot_inert_v34/local/controls').iterdir():
        shutil.copyfile(p, LOCAL / 'controls' / p.name)
    shutil.copyfile(ROOT / 'research/boot_inert_v34/local/formats.py', LOCAL / 'formats.py')
    shutil.copyfile(ROOT / 'research/boot_inert_v34/local/receipt-schema.json', LOCAL / 'receipt-schema.json')
    for p in (HERE / 'resident').glob('*.py'):
        p.write_text(p.read_text().replace('resident_v33', 'resident_v34'))
    (HERE / 'PROGRESS.md').write_text(
        '2026-10-25 P1 开始。卷身份、可写 APFS、df 已核实；冻结输入排除 decisions.tsv。\n'
        '基线 resident payload 7800 B，root 256 B，窗口 8340 B，实余 284 B。\n'
        '覆盖决定：默认启用；仅有效 CRC 的 CTL OFF 锁定停用；RPC 仅明确应用时准许。\n'
        'H09 packet mutation 保持关闭。未构建机身镜像，未访问相机或卡。\n')
    check()


if __name__ == '__main__':
    main()
