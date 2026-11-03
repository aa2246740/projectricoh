#!/usr/bin/python3
"""Verify frozen inputs, remove only this task's temporary directory, seal output."""
import datetime
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-body-reclaim')

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    assert HERE==ROOT/'research/review_body_reclaim' and not HERE.is_symlink()
    volume=subprocess.run(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace'],capture_output=True,check=True,timeout=60)
    volume=plistlib.loads(volume.stdout)
    assert volume['MountPoint']=='/Volumes/Workspace' and volume['FilesystemType']=='apfs'
    assert volume['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and volume['Writable']
    before=json.loads((HERE/'inputs-before.json').read_text())['files']
    extra=json.loads((HERE/'inputs-extra.json').read_text())['files']
    for group in [before,extra]:
        changed=[name for name,value in group.items() if digest(ROOT/name)!=value]
        assert not changed,changed
    manifest=[]
    for line in (ROOT/'research/body_next_steps/SHA256SUMS').read_text().splitlines():
        expected,name=line.split(None,1);name=name.strip()
        assert digest(ROOT/name)==expected,name
        manifest.append(name)
    assert len(manifest)==26
    report=(HERE/'REVIEW.md').read_text()
    assert report.splitlines()[0]=='修改后再实现'
    assert not TMP.is_symlink()
    temp_existed=TMP.exists()
    if temp_existed:shutil.rmtree(TMP)
    assert not TMP.exists()
    result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'volume_uuid':volume['VolumeUUID'],'filesystem':'apfs','volume_writable':True,
            'original_manifest_items_verified':len(manifest),
            'initial_frozen_files_unchanged':len(before),'supplementary_files_unchanged':len(extra),
            'changed_frozen_files':[],
            'tmp_path':str(TMP),'tmp_existed_before_cleanup':temp_existed,'tmp_exists_after_cleanup':False,
            'write_scope':str(HERE),'temporary_write_exception':str(TMP),
            'network_used':False,'camera_or_storage_card_accessed':False,'git_write_operations':False,
            'subagents_started':0,'body_image_or_update_package_generated':False,
            'checksum_scope':'All regular review-directory files except SHA256SUMS itself.'}
    (HERE/'cleanup.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for name in re.findall(r'\]\(([^)]+)\)',report):
        if '://' not in name:assert (HERE/name).exists(),name
    files=sorted(path for path in HERE.rglob('*') if path.is_file() and path.name!='SHA256SUMS')
    assert not any(path.is_symlink() for path in files)
    rows=[(digest(path),str(path.relative_to(ROOT))) for path in files]
    target=HERE/'SHA256SUMS'
    target.write_text(''.join(f'{value}  {name}\n' for value,name in rows))
    for line in target.read_text().splitlines():
        value,name=line.split(None,1);assert digest(ROOT/name.strip())==value,name
    print(json.dumps({'verdict':report.splitlines()[0],'manifest_items':len(rows),
                      'all_manifest_items_verified':True,'report_sha256':digest(HERE/'REVIEW.md'),
                      'review_bytes':sum(path.stat().st_size for path in files),
                      'initial_inputs_unchanged':len(before),'supplementary_inputs_unchanged':len(extra),
                      'tmp_exists':TMP.exists()},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
