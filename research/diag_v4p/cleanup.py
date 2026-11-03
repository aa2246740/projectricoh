"""Remove this task's temporary tree only after all test workers exit."""
from pathlib import Path
import os
import json
import plistlib
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s


def remove_tree(path):
    for child in path.iterdir():
        if child.is_symlink() or not child.is_dir():child.unlink()
        else:remove_tree(child)
    path.rmdir()


def main():
    s.enable()
    info=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert info['FilesystemType']=='apfs' and info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and info['WritableVolume']
    receipt=s.HERE/'evidence/processes-before-cleanup.json';snapshot=json.loads(receipt.read_text())
    assert 0<=time.time()-snapshot['created_unix']<=30,'process receipt is not fresh'
    running=snapshot['active_test_processes']
    assert not running,running
    s.verify_inputs();files=[path for path in s.TMP.rglob('*') if path.is_file() and not path.is_symlink()]
    count=len(files);size=sum(path.stat().st_size for path in files)
    remove_tree(s.TMP)
    assert not s.TMP.exists()
    s.save(s.HERE/'evidence/cleanup.json',dict(active_test_processes=running,removed=str(s.TMP),files=count,bytes=size,
        absent_after=True,volume_uuid=info['VolumeUUID'],frozen_inputs_unchanged=True,process_receipt_sha256=s.sha(receipt)))
    print('PASS temporary tree removed',count,size)


if __name__=='__main__':main()
