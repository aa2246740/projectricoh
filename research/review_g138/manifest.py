"""Write or verify this local review's complete SHA256 inventory."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess

OUT = Path(__file__).resolve().parent
MANIFEST = OUT / 'SHA256SUMS'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def files():
    result = {}
    for path in OUT.rglob('*'):
        assert not path.is_symlink(), path
        assert path.name != '__pycache__' and path.suffix != '.pyc', path
        if path == MANIFEST or path.name == '.DS_Store' or not path.is_file():
            continue
        name = str(path.relative_to(OUT))
        assert '\n' not in name and '\r' not in name
        result[name] = path
    return result


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--write', action='store_true')
    action.add_argument('--check', action='store_true')
    args = parser.parse_args()
    volume = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert volume['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert volume['MountPoint'] == '/Volumes/Workspace' and volume['FilesystemType'] == 'apfs'
    assert volume['WritableVolume'] and volume['WritableMedia']
    with (OUT / 'local/scheduler.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = files()
        if args.write:
            MANIFEST.write_text(''.join(digest(current[name]) + '  ' + name + '\n' for name in sorted(current)))
            status = 'WROTE_SHA256'
        else:
            expected = dict(line.split('  ', 1)[::-1] for line in MANIFEST.read_text().splitlines())
            assert set(current) == set(expected), dict(missing=sorted(set(expected)-set(current)), extra=sorted(set(current)-set(expected)))
            different = [name for name, path in current.items() if digest(path) != expected[name]]
            assert not different, different
            status = 'PASS_SHA256'
    print(json.dumps(dict(status=status, files=len(current), manifest=str(MANIFEST))), flush=True)


if __name__ == '__main__':
    main()
