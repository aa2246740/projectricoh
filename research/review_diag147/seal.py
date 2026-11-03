"""Recheck frozen inputs, remove the dedicated temporary directory, and seal files."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import plistlib
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
import scope
scope.enable_fence()

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):
            h.update(block)
    return h.hexdigest()

files={}
groups={}
volume=plistlib.loads(subprocess.run(
    ['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace'],
    capture_output=True,check=True,timeout=30).stdout)
assert volume['MountPoint']=='/Volumes/Workspace'
assert volume['FilesystemType']=='apfs' and volume['WritableVolume']
assert volume['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
for name in ('inputs-before.json','support-inputs-before.json'):
    group=json.loads((HERE/name).read_text())['files']
    groups[name]=len(group)
    for relative,digest in group.items():
        if relative in files:
            assert files[relative]==digest
        files[relative]=digest
changed=[relative for relative,digest in files.items()
         if not (ROOT/relative).is_file() or sha(ROOT/relative)!=digest]
assert not changed,changed
trees=['firmware/engine_diag_v38_g147','firmware/package_v38_diag147','research/diag147',
       'firmware/engine_diag_v38_g146','research/g140_entries_design',
       'research/user_storage_r2','firmware/resident_v38','research/review_diag146/native-listings']
initial=json.loads((HERE/'inputs-before.json').read_text())['files']
before={p for p in initial if any(p.startswith(tree+'/') for tree in trees)}
after={str(p.relative_to(ROOT)) for tree in trees for p in (ROOT/tree).rglob('*') if p.is_file()}
added=sorted(after-before)
removed=sorted(before-after)
assert not added and not removed,(added,removed)
process_audit=json.loads((HERE/'process-audit.json').read_text())
assert process_audit['status']=='PASS'
processes=process_audit['active_review_processes']
assert not processes,processes
tmp=scope.SCRATCH
assert str(tmp)=='/Volumes/Workspace/Scratch/tmp/projectricoh/review-diag147' and tmp.resolve()==tmp
removed=[]
if tmp.exists():
    for path in sorted(tmp.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        assert path.is_relative_to(tmp)
        removed.append(str(path.relative_to(tmp)))
        if path.is_file() or path.is_symlink():
            path.unlink()
        else:
            path.rmdir()
    tmp.rmdir()
assert not tmp.exists()
scope.save(HERE/'seal.json',dict(
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    status='PASS',input_groups=groups,unique_frozen_inputs=len(files),changed_inputs=changed,
    added_input_files=added,removed_input_files=removed,
    volume={k:volume[k] for k in ('MountPoint','FilesystemType','VolumeUUID','WritableVolume')},
    scratch=str(tmp),scratch_removed=True,temporary_entries_removed=removed,
    active_review_processes=processes,
    process_audit='research/review_diag147/process-audit.json',
    reviewed_directories_modified=False,network_used=False,card_access=False,
    git_write=False,subagents=False))
outputs=sorted(p for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
assert not any(p.is_symlink() for p in outputs)
(HERE/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(ROOT))+'\n' for p in outputs))
for line in (HERE/'SHA256SUMS').read_text().splitlines():
    digest,relative=line.split('  ',1)
    assert sha(ROOT/relative)==digest,relative
print(json.dumps(dict(status='PASS',unique_frozen_inputs=len(files),output_files=len(outputs),
                      scratch_removed=True,manifest_sha256=sha(HERE/'SHA256SUMS')),ensure_ascii=False),flush=True)
