"""Hash the final files relative to the repository root and verify them."""
from pathlib import Path
import json
import plistlib
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import ROOT,OUT,TREE,PACKAGE,DAT,file_sha

volume=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
identity=volume.get('VolumeUUID',volume.get('DiskUUID'))
assert identity=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
assert volume['MountPoint']=='/Volumes/Workspace' and volume['FilesystemType']=='apfs' and volume['WritableVolume']
roots=(TREE,PACKAGE,OUT)
manifest=OUT/'SHA256SUMS';receipt=OUT/'checksum-selfcheck.json'

def files():return sorted(p for root in roots for p in root.rglob('*') if p.is_file())

card_rows=[line.split('  ',1) for line in (PACKAGE/'CARD_SHA256SUMS').read_text().splitlines()]
assert len(card_rows)==30
for digest,name in card_rows:assert file_sha(PACKAGE/name)==digest
fixed=[]
for p in sorted(DAT.parent.iterdir()):
    if p.is_file() and p!=DAT:
        assert p.read_bytes()==(ROOT/'firmware/package_v36_g120b/SD_ROOT'/p.name).read_bytes()
        fixed.append(p.name)
assert len(fixed)==29
existing=[p for p in files() if p not in (manifest,receipt)]
receipt.write_text(json.dumps(dict(status='PASS',files=len(existing)+1,
    roots=[str(p.relative_to(ROOT)) for p in roots],manifest='research/g122_keep_list/SHA256SUMS',
    manifest_excludes_itself=True,card_sha256=file_sha(DAT),card_files=30,fixed_files_unchanged=29,
    volume_uuid=identity,verification='All listed files are read back using hashlib and shasum -a 256 -c; CARD_SHA256SUMS covers all 30 card files.'),indent=2)+'\n')
rows=[(file_sha(p),str(p.relative_to(ROOT))) for p in files() if p!=manifest]
manifest.write_text(''.join(digest+'  '+name+'\n' for digest,name in rows))
for digest,name in rows:assert file_sha(ROOT/name)==digest,name
checked=subprocess.run(['/usr/bin/shasum','-a','256','-c',str(manifest)],cwd=ROOT,capture_output=True,text=True)
assert checked.returncode==0,checked.stderr
assert len(checked.stdout.splitlines())==len(rows) and all(s.endswith(': OK') for s in checked.stdout.splitlines())
checked_card=subprocess.run(['/usr/bin/shasum','-a','256','-c',str(PACKAGE/'CARD_SHA256SUMS')],cwd=PACKAGE,capture_output=True,text=True)
assert checked_card.returncode==0 and len(checked_card.stdout.splitlines())==30
assert all(s.endswith(': OK') for s in checked_card.stdout.splitlines())
print('PASS SHA256SUMS',len(rows),'/',len(rows),'; CARD_SHA256SUMS 30 / 30; fixed files 29 / 29',flush=True)
print('SHA256SUMS SHA256',file_sha(manifest),flush=True)
