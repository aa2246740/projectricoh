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
IMAGE = ROOT / 'firmware/image_v34c'
SCOPES = (
    'artifacts/firmware/gxr-1.51', 'artifacts/v32-trial/full-r3-20261024',
    'firmware/resident_v33', 'firmware/image_v33', 'firmware/resident_v32',
    'firmware/image_v3', 'firmware/engine_fix_r2', 'firmware/resident_v34', 'firmware/image_v34', 'firmware/engine_v33d', 'firmware/full_r5', 'firmware/full_r4',
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
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/resident_v34c')
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
        if out.exists():
            assert out.read_bytes()==p.read_bytes(), str(out)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, out)


if __name__ == '__main__':
    check()
