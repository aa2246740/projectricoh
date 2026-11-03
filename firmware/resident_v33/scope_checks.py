#!/usr/bin/env python3
"""Recheck the protected inputs, volume, ignore rule and artifact locations."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    volume=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert volume['MountPoint']=='/Volumes/Workspace' and volume['FilesystemType']=='apfs'
    assert volume['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert volume['WritableVolume'] and volume['WritableMedia'] and os.access(HERE,os.W_OK)
    before=json.loads((HERE/'local/inputs-before.json').read_text())
    mismatches=[name for name,digest in before.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=digest]
    ignored=subprocess.check_output(['git','check-ignore','-v','firmware/resident_v33/local/check'],cwd=ROOT,text=True)
    assert 'firmware/resident_v33/.gitignore:1:/local/' in ignored
    misplaced=[]
    for p in HERE.rglob('*'):
        assert not p.is_symlink(),str(p)
        if p.is_file() and p.suffix.lower() in ('.dat','.bin','.elf','.o','.fixture','.log') and not (p.is_relative_to(HERE/'local') or p.is_relative_to(HERE/'acceptance/local')):
            misplaced.append(str(p.relative_to(HERE)))
    body_images=[str(p.relative_to(HERE)) for p in HERE.rglob('*') if p.is_file() and p.name.lower().startswith('ilaunch3')]
    result=dict(status='PASS' if not (mismatches or misplaced or body_images) else 'FAIL',checked_files=len(before),
                mismatches=mismatches,misplaced_derived_artifacts=misplaced,body_images=body_images,
                volume={k:volume[k] for k in ('MountPoint','VolumeUUID','FilesystemType','WritableVolume','WritableMedia')},
                ignore=ignored,protected_inputs=before)
    (HERE/'local/inputs-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    assert result['status']=='PASS',str(result)
    print('PASS scope: protected='+str(len(before))+' mismatches=0 derived_outside_local=0 body_images=0')
if __name__=='__main__':main()
