from pathlib import Path
import datetime
import json
import os
import plistlib
import subprocess

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch')


def main():
    volume = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert volume['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and volume['FilesystemType'] == 'apfs' and volume['WritableVolume']
    intake = json.loads((OUT / 'evidence/intake.json').read_text())
    assert intake['tmp'] == str(TMP)
    listing = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,command='], text=True)
    processes = {}
    for line in listing.splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) == 3:
            processes[int(fields[0])] = (int(fields[1]), fields[2])
    ancestors = set()
    current = os.getpid()
    while current and current not in ancestors:
        ancestors.add(current)
        current = processes.get(current, (0, ''))[0]
    remaining = [{'pid': pid, 'command': command} for pid, (_, command) in processes.items()
                 if pid not in ancestors and
                 any(value in command for value in [str(OUT), str(TMP), 'research/review_harness_c_switch/'])]
    if remaining:
        raise RuntimeError('Review processes still running: ' + json.dumps(remaining))
    files, size = 0, 0

    def remove(path):
        nonlocal files, size
        assert path == TMP or path.is_relative_to(TMP)
        for item in path.iterdir():
            if item.is_symlink():
                item.unlink()
                files += 1
            elif item.is_dir():
                remove(item)
            else:
                size += item.stat().st_size
                item.unlink()
                files += 1
        path.rmdir()
    if TMP.exists():
        assert not TMP.is_symlink() and TMP.resolve() == TMP
        remove(TMP)
    receipt = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'tmp': str(TMP), 'tmp_exists_after': TMP.exists(),
               'removed_files': files, 'removed_bytes': size,
               'remaining_review_processes': remaining,
               'volume_uuid': volume['VolumeUUID']}
    (OUT / 'evidence/cleanup.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
