"""Verify frozen inputs, then remove only this review's temporary root."""
import datetime as dt
import fcntl
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g138')
info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
assert info['MountPoint'] == '/Volumes/Workspace' and info['FilesystemType'] == 'apfs'
assert info['WritableVolume'] and info['WritableMedia']
regressions = json.loads((OUT / 'REGRESSIONS.json').read_text())
assert regressions['final'] and regressions['completed'] == 81
for queue in ['queue', 'repair-queue', 'supplemental-queue', 'audit-queue']:
    assert (OUT / 'evidence' / (queue + '-complete.json')).is_file(), queue
before = json.loads((OUT / 'evidence/inputs-before.json').read_text())['files']
changed = []
for name, expected in before.items():
    path = ROOT / name
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    if actual != expected['sha256']:
        changed.append(dict(file=name, before=expected['sha256'], after=actual))
assert not changed, changed
with (OUT / 'local/scheduler.lock').open('a') as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    if TMP.exists():
        assert TMP.resolve() == TMP and not TMP.is_symlink()
        shutil.rmtree(TMP)
    assert not TMP.exists()
result = dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(), checked_files=len(before), changed=changed,
              temporary=str(TMP), temporary_removed=not TMP.exists(),
              volume=dict(mount=info['MountPoint'], filesystem=info['FilesystemType'], uuid=info['VolumeUUID']))
(OUT / 'evidence/seal.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
