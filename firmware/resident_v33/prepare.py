"""One-time source copy and immutable input inventory for the host-only v3.3 fix."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guard():
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['MountPoint'] == '/Volumes/Workspace' and info['FilesystemType'] == 'apfs'
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['WritableVolume'] and info['WritableMedia'] and os.access(HERE, os.W_OK)
    assert HERE == ROOT / 'firmware/resident_v33'
    assert not HERE.is_symlink() and not LOCAL.is_symlink()


def check():
    guard()
    before = json.loads((LOCAL / 'inputs-before.json').read_text())
    changes = [p for p, digest in before.items() if not (ROOT / p).is_file() or sha(ROOT / p) != digest]
    assert not changes, 'STOP_PROTECTED_INPUT_CHANGED: ' + repr(changes)
    return len(before)


def copy_sources(source, target):
    for path in source.rglob('*'):
        relative = path.relative_to(source)
        if any(p in ('local', '__pycache__', '.DS_Store') for p in relative.parts) or not path.is_file():
            continue
        assert not path.is_symlink()
        destination = target / relative
        assert not destination.exists(), str(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)


def main():
    guard()
    assert not (LOCAL / 'inputs-before.json').exists(), 'Never replace the initial inventory'
    subprocess.run(['/bin/df', '-h', '/Volumes/Workspace'], check=True)
    paths = {ROOT / p for p in subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0') if p}
    for relative in ('firmware/resident_v32', 'firmware/image_v3', 'firmware/engine_v33d',
                     'firmware/engine_v33c', 'research/review_full_r6', 'research/review_full_r7',
                     'research/review_flash_v32', 'artifacts/firmware/gxr-1.51',
                     'artifacts/v32-trial/full-r3-20261024'):
        paths.update((ROOT / relative).rglob('*'))
    for inventory in ('firmware/resident_v32/local/inputs-before.json',
                      'research/review_full_r7/local/inputs-before.json'):
        paths.update(ROOT / p for p in json.loads((ROOT / inventory).read_text()))
    paths.discard(ROOT / 'decisions.tsv')
    frozen = {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)
              if p.is_file() and not p.is_symlink() and HERE not in p.parents and ROOT / 'firmware/image_v33' not in p.parents}
    LOCAL.mkdir()
    (LOCAL / 'inputs-before.json').write_text(json.dumps(frozen, indent=2) + '\n')
    (LOCAL / 'initial-git-status.txt').write_bytes(subprocess.check_output(['git', 'status', '--short'], cwd=ROOT))
    copy_sources(ROOT / 'firmware/resident_v32', HERE)
    copy_sources(ROOT / 'firmware/image_v3', ROOT / 'firmware/image_v33')
    copy_sources(ROOT / 'firmware/engine_v33d', HERE / 'acceptance')
    # Only relocate the copied tooling. Retain the ABI salt and all C headers.
    for path in HERE.rglob('*.py'):
        if LOCAL in path.parents or HERE / 'acceptance' in path.parents or path.name == 'prepare.py':
            continue
        source = path.read_text().replace('resident_v32', 'resident_v33')
        source = source.replace("b'RV resident_v33 ABI 1", "b'RV resident_v32 ABI 1")
        path.write_text(source)
    for path in (ROOT / 'firmware/image_v33').glob('*.py'):
        path.write_text(path.read_text().replace('image_v3', 'image_v33'))
    (LOCAL / 'resident').mkdir()
    shutil.copyfile(ROOT / 'firmware/resident_v32/local/resident/hooks.json', LOCAL / 'resident/hooks.json')
    print('PASS frozen protected inputs:', check())


if __name__ == '__main__':
    main()
