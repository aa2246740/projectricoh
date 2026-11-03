"""Verify frozen inputs, remove only this task's temporary root, and seal files."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import plistlib
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g139')

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            value.update(block)
    return value.hexdigest()

mount=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
assert mount['MountPoint']=='/Volumes/Workspace' and mount['FilesystemType']=='apfs'
assert mount['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and mount['WritableVolume']
live=[]
for line in subprocess.check_output(['/bin/ps','-axo','pid=,command='],text=True).splitlines():
    if 'research/review_g139/' not in line and 'tmp/projectricoh/review-g139' not in line:
        continue
    if 'seal.py' in line:
        continue
    live.append(line.strip())
assert not live,live
inputs=json.loads((HERE/'evidence/input-before.json').read_text())['entries']
inputs+=json.loads((HERE/'evidence/input-extra-before.json').read_text())
unique={row['path']:row['sha256'] for row in inputs}
changed=[name for name,expected in unique.items() if not (ROOT/name).is_file() or digest(ROOT/name)!=expected]
assert not changed,changed
assert (HERE/'REVIEW.md').read_text().splitlines()[0] in ('不能上卡','可以上卡')
assert TMP.parent==Path('/Volumes/Workspace/Scratch/tmp/projectricoh') and not TMP.is_symlink()
removed_files=sum(path.is_file() for path in TMP.rglob('*')) if TMP.exists() else 0
if TMP.exists():
    assert TMP.resolve()==TMP
    shutil.rmtree(TMP)
assert not TMP.exists()
seal_path=HERE/'evidence/seal.json'
files=[p for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS']
expected_count=len(files)+(0 if seal_path.is_file() else 1)
result=dict(status='PASS_SEAL',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            mount_uuid=mount['VolumeUUID'],frozen_files=len(unique),changed_files=changed,
            related_processes=live,tmpdir=str(TMP),temporary_files_removed=removed_files,
            tmpdir_absent=True,review_files=expected_count)
seal_path.write_text(json.dumps(result,indent=2)+'\n')
files=sorted(p for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
assert len(files)==expected_count
lines=['%s  %s'%(digest(path),path.relative_to(ROOT)) for path in files]
manifest=HERE/'SHA256SUMS'
manifest.write_text('\n'.join(lines)+'\n')
for line in lines:
    expected,name=line.split('  ',1)
    assert digest(ROOT/name)==expected,name
print(json.dumps(dict(**result,manifest_sha256=digest(manifest)),indent=2))
