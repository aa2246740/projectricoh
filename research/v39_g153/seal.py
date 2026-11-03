"""Hash the allowed output trees after the final process and cleanup receipts."""
from pathlib import Path
import hashlib
import json
import plistlib
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUTS = (ROOT / 'firmware/engine_v62_g153', ROOT / 'firmware/package_v39_g153',
           ROOT / 'firmware/package_v39_g153_test', HERE)


def main():
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['FilesystemType'] == 'apfs' and info['WritableVolume']
    cleanup = json.loads((HERE / 'evidence/cleanup.json').read_text())
    assert cleanup['alive'] == [] and cleanup['temporary_directory_removed']
    target = HERE / 'SHA256SUMS'
    paths = set()
    for folder in OUTPUTS:
        assert folder.is_dir() and not folder.is_symlink()
        for path in folder.rglob('*'):
            if path.is_file() and not path.is_symlink() and path != target:
                paths.add(path)
    records = [(hashlib.sha256(path.read_bytes()).hexdigest(), path.relative_to(ROOT)) for path in sorted(paths)]
    target.write_text(''.join(f'{digest}  {path}\n' for digest, path in records))
    for digest, path in records:
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    print(json.dumps(dict(status='PASS', files=len(records), sums=str(target.relative_to(ROOT)))))


if __name__ == '__main__':
    main()
