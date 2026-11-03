"""Close this review's own temporary tree and seal its retained evidence."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import plistlib
import shlex
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-diag-v4p-r1')
START=datetime(2026,11,1,17,47,40,tzinfo=timezone.utc)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    info=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['FilesystemType']=='apfs' and info['WritableVolume'] and info['WritableMedia']
    before=json.loads((HERE/'inputs-before.json').read_text())
    changed=[name for name,value in before.items() if sha(ROOT/name)!=value]
    assert not changed,changed
    extra=json.loads((HERE/'receipt-audit.json').read_text())
    for name,value in extra['legacy_programs'].items():assert sha(ROOT/name)==value
    assert sha(ROOT/extra['native_trace']['path'])==extra['native_trace']['sha256']
    process_path=HERE/'processes-before-cleanup.json'
    processes=json.loads(process_path.read_text())
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(processes['date_utc'])).total_seconds()
    assert processes['read_only'] and 0<=age<60
    active=processes['active']
    assert not active,active
    assert TEMP.parent==Path('/Volumes/Workspace/Scratch/tmp/projectricoh') and not TEMP.is_symlink()
    files=[p for p in TEMP.rglob('*') if p.is_file()]
    count=len(files);size=sum(p.stat().st_size for p in files)
    if TEMP.exists():shutil.rmtree(TEMP)
    assert not TEMP.exists()
    assert (HERE/'REVIEW.md').read_text().splitlines()[0]=='修改后再上机'
    now=datetime.now(timezone.utc)
    receipt=dict(status='PASS',start_utc=START.isoformat(),end_utc=now.isoformat(),
        total_seconds=round((now-START).total_seconds(),3),volume_uuid=info['VolumeUUID'],
        fixed_inputs=len(before),changed=changed,additional_legacy_and_trace_checks=3,
        active_test_processes=active,removed=str(TEMP),absent_after=True,
        process_receipt_sha256=sha(process_path),
        files=count,bytes=size,review_verdict='修改后再上机',p1=['P1-01'],
        dat_sha256=sha(ROOT/'firmware/package_v39_diagv4p/GXRCE.DAT'))
    (HERE/'cleanup.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    paths=sorted(p for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    text=''.join(sha(p)+'  '+str(p.relative_to(ROOT))+'\n' for p in paths)
    (HERE/'SHA256SUMS').write_text(text)
    for line in text.splitlines():
        value,name=line.split('  ',1);assert sha(ROOT/name)==value
    print(json.dumps(dict(status='PASS',retained_files=len(paths),active_tests=0,
        scratch_absent=True,total_seconds=receipt['total_seconds'],files_removed=count,bytes_removed=size)))


if __name__=='__main__':main()
