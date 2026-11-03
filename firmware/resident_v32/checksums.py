#!/usr/bin/env python3
"""Generate or verify the complete task manifest without changing inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert info['MountPoint']=='/Volumes/Workspace' and info['FilesystemType']=='apfs'
    assert info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and info['WritableVolume'] and info['WritableMedia']
    ignored=subprocess.check_output(['git','check-ignore','-v','firmware/resident_v32/local/check'],cwd=ROOT,text=True)
    assert 'firmware/resident_v32/.gitignore:1:/local/' in ignored
    manifest=HERE/'SHA256SUMS'
    paths=sorted(p for p in HERE.rglob('*') if p.is_file() and p!=manifest)
    assert not any(p.is_symlink() for p in paths)
    if args.verify:
        expected={name:digest for digest,name in (line.split('  ',1) for line in manifest.read_text().splitlines())}
        actual={str(p.relative_to(HERE)):sha(p) for p in paths}
        assert actual==expected,'manifest differs, rerun build/verify then regenerate intentionally'
        print(f'PASS SHA256SUMS files={len(actual)}')
    else:
        manifest.write_text(''.join(sha(p)+'  '+str(p.relative_to(HERE))+'\n' for p in paths))
        print(f'WROTE SHA256SUMS files={len(paths)}')
if __name__=='__main__':main()
