"""Freeze and verify this task's read-only inputs. Run with python3 -I -B."""
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INPUTS = (
    'firmware/engine_v38_b36', 'firmware/resident_v36', 'firmware/image_v36',
    'firmware/package_v36_g117', 'tools/native_harness',
    'artifacts/downloads/gxr-151.zip', 'artifacts/firmware/gxr-1.51',
    'research/review_g117_container/REVIEW.md',
    'research/review_g117_codegen_r2/REVIEW.md', 'research/cpu_speed_r1',
    'firmware/engine_v36_r28/local/reproduced114',
    'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc',
    'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld',
    'research/tooling_m32r/prefix/bin/m32r-elf-objdump',
)

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def guard():
    info = plistlib.loads(subprocess.check_output(
        ['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['MountPoint'] == '/Volumes/Workspace'
    assert info['FilesystemType'] == 'apfs'
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['WritableVolume'] and info['WritableMedia']
    return {k: info[k] for k in ('MountPoint', 'FilesystemType', 'VolumeUUID',
                                'WritableVolume', 'WritableMedia')}

def main():
    volume = guard()
    before = HERE / 'inputs-before.json'
    if sys.argv[1:] == ['freeze']:
        assert not before.exists()
        paths = []
        for name in INPUTS:
            p = ROOT / name
            assert p.exists(), p
            paths.extend([p] if p.is_file() else sorted(p.rglob('*')))
        frozen = {str(p.relative_to(ROOT)): digest(p) for p in paths
                  if p.is_file() and not p.is_symlink()}
        before.write_text(json.dumps(frozen, indent=2, sort_keys=True) + '\n')
        (HERE / 'volume.json').write_text(json.dumps(volume, indent=2) + '\n')
        print('FROZEN', len(frozen))
    else:
        frozen = json.loads(before.read_text())
        changed = [p for p, h in frozen.items()
                   if not (ROOT / p).is_file() or digest(ROOT / p) != h]
        result = dict(files=len(frozen), changes=changed, volume=volume)
        (HERE / 'inputs-verification.json').write_text(json.dumps(result, indent=2) + '\n')
        assert not changed, changed
        print('PASS protected inputs', len(frozen))

if __name__ == '__main__':
    main()
