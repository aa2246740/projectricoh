"""Seal the three output directories and check standard SHA-256 manifests."""
from pathlib import Path
import hashlib,json,os,plistlib,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,TREE,PACKAGE,save,file_sha
info=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
assert info['MountPoint']=='/Volumes/Workspace' and info['FilesystemType']=='apfs'
assert info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and info['WritableVolume']
assert json.loads((OUT/'task-status.json').read_text())['status']=='STOPPED_NOT_ACCEPTED'
for name in ('input-integrity.json','name-input-integrity.json','data-name-equality.json','name-code-binding.json','zero-file-write-audit.json','neutral-language-check.json'):
 assert json.loads((OUT/name).read_text())['status']=='PASS',name
manifests=[]
for root,name in ((TREE,'EVIDENCE_SHA256SUMS'),(PACKAGE,'EVIDENCE_SHA256SUMS'),(OUT,'SHA256SUMS')):
 target=root/name;paths=[]
 for p in sorted(root.rglob('*')):
  assert not p.is_symlink(),str(p)
  if not p.is_file() or p==target or root==OUT and p==OUT/'checksum-selfcheck.json':continue
  paths.append(p)
 target.write_text(''.join(file_sha(p)+'  '+str(p.relative_to(root))+'\n' for p in paths))
 manifests.append((root,target,len(paths)))
card=PACKAGE/'CARD_SHA256SUMS';assert len(card.read_text().splitlines())==30
manifests.append((PACKAGE,card,30));records=[]
for root,path,count in manifests:
 command=['/usr/bin/shasum','-a','256','-c',path.name]
 result=subprocess.run(command,cwd=root,capture_output=True,text=True,check=True)
 ok=sum(line.endswith(': OK') for line in result.stdout.splitlines())
 assert ok==count and not result.stderr,(path.name,ok,count,result.stderr)
 records.append(dict(manifest=str(path.relative_to(ROOT)),sha256=file_sha(path),files=count,OK=ok,returncode=result.returncode,argv=command,cwd=str(root),stdout_sha256=hashlib.sha256(result.stdout.encode()).hexdigest()))
save('checksum-selfcheck.json',dict(status='PASS',manifests=records,excluded_from_research_manifest=['SHA256SUMS','checksum-selfcheck.json'],note='Each manifest excludes itself. The checksum result also remains outside its own research manifest.'))
print('PASS standard SHA-256 checks',[(r['manifest'],r['OK']) for r in records],flush=True)
