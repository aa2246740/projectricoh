"""Read-only repository snapshot; outputs stay in this review directory."""
import hashlib
import json
import os
import pathlib
import plistlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def snapshot():
    result = {}
    for directory, dirs, names in os.walk(ROOT, followlinks=False):
        base = pathlib.Path(directory)
        dirs[:] = sorted(d for d in dirs if d != '.git'
                         and base / d != HERE and not (base / d).is_symlink())
        for name in sorted(names):
            p = base / name
            rel = p.relative_to(ROOT).as_posix()
            if rel == 'decisions.tsv':
                continue
            if p.is_symlink():
                result[rel] = {'link': os.readlink(p)}
            elif p.is_file():
                result[rel] = {'bytes': p.stat().st_size, 'sha256': digest(p)}
    return result


def write(name, data):
    (LOCAL / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def main():
    mode = sys.argv[1]
    if mode == 'freeze':
        assert not (LOCAL / 'inputs-before.json').exists(), 'Never overwrite the initial freeze'
        raw = subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace'])
        v = plistlib.loads(raw)
        assert v['MountPoint'] == '/Volumes/Workspace'
        assert v['FilesystemType'].lower() == 'apfs'
        assert v['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
        assert v['WritableVolume'] and v['WritableMedia']
        LOCAL.mkdir(exist_ok=True)
        (LOCAL / 'volume.plist').write_bytes(raw)
        (LOCAL / 'df-h.txt').write_bytes(subprocess.check_output(['/bin/df', '-h', '/Volumes/Workspace']))
        (LOCAL / 'git-tracked-before.txt').write_bytes(subprocess.check_output(['git', 'status', '--porcelain=v1', '--untracked-files=no'], cwd=ROOT))
        s = snapshot()
        write('inputs-before.json', s)
        print('Frozen files:', len(s), 'bytes:', sum(x.get('bytes', 0) for x in s.values()))
    elif mode == 'check':
        before = json.loads((LOCAL / 'inputs-before.json').read_text())
        after = snapshot()
        changes = [p for p in sorted(before.keys() | after.keys()) if before.get(p) != after.get(p)]
        tracked_before = (LOCAL / 'git-tracked-before.txt').read_text().splitlines()
        tracked_after = subprocess.check_output(['git', 'status', '--porcelain=v1', '--untracked-files=no'], cwd=ROOT).decode().splitlines()
        tracked_equal = [x for x in tracked_before if x[3:] != 'decisions.tsv'] == [x for x in tracked_after if x[3:] != 'decisions.tsv']
        write('scope-check.json', {'files': len(before), 'changes': changes, 'tracked_equal': tracked_equal, 'excluded': ['.git/', 'decisions.tsv', str(HERE.relative_to(ROOT)) + '/']})
        assert not changes, changes
        assert tracked_equal
        print('Unchanged:', len(before), 'files; decisions.tsv excluded')
    else:
        raise SystemExit('freeze | check')


if __name__ == '__main__':
    main()
