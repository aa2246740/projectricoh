import datetime as dt
import hashlib
import json
import os
import plistlib
import runpy
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_v38_g137'
PIN='78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8'
BODY='d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
load=lambda path:json.loads(path.read_text())

volume=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
assert volume['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
assert volume.get('MountPoint')=='/Volumes/Workspace' and os.path.ismount('/Volumes/Workspace')
assert volume.get('FilesystemType','').lower()=='apfs' and volume.get('WritableVolume') is True

process_text=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,command='],text=True)
active=[]
for line in process_text.splitlines():
    fields=line.strip().split(None,2)
    if len(fields)!=3:continue
    pid,parent,command=fields
    if int(pid) in (os.getpid(),os.getppid()):continue
    if 'review_v38_g137/' in command and any(name in command for name in ('resume_run.py','scheduler.py','legacy_call.py','focus_call.py','run_r3_job.py')):
        active.append({'pid':int(pid),'parent':int(parent),'command':command})
assert not active,active

before=load(OUT/'evidence/input-before.json')
changed=[];checked=0
for name,expected in before.items():
    path=ROOT/name
    if path.name=='decisions.tsv':continue
    checked+=1
    actual=digest(path) if path.is_file() else None
    if actual!=expected:changed.append({'path':name,'before':expected,'after':actual})
assert checked==790 and not changed,changed
source_artifacts=load(OUT/'evidence/source-resume.json')['artifacts']
assert load(OUT/'evidence/source-final.json')==load(OUT/'evidence/source-resume.json')
for name,expected in source_artifacts.items():
    assert digest(ROOT/name)==expected['sha256'],name
package=ROOT/'firmware/package_v38_g137/local/SD_ROOT'
assert digest(package/'GXRCE.DAT')==PIN
assert digest(package/'ilaunch3')==BODY

implementation=[]
for line in (ROOT/'research/emptystack_v38/SHA256SUMS').read_text().splitlines():
    expected,name=line.split(None,1);name=name.lstrip('*')
    actual=digest(ROOT/name)
    if actual!=expected:implementation.append({'path':name,'before':expected,'after':actual})
known=load(OUT/'evidence/implementation-result-audit.json')
assert len(implementation)==1
assert implementation[0]=={'path':known['path'],'before':known['expected_sha256'],'after':known['current_sha256']}

ledger=load(OUT/'regressions-final.json')
assert ledger['ready'] is True and ledger['closed']==11
assert (OUT/'REVIEW.md').read_text().splitlines()[0]=='可以刷机'
rules=runpy.run_path(str(OUT/'text_rules.py'),run_name='review_text_rules')
assert not rules['scan']()

cleanup=[]
for name in ('review-v38','review-v38-g137'):
    path=Path('/Volumes/Workspace/Scratch/tmp/projectricoh')/name
    assert not path.is_symlink()
    record={'path':str(path),'existed':path.exists()}
    if path.exists():
        assert path.resolve()==path
        files=[child for child in path.rglob('*') if child.is_file()]
        record.update(files=len(files),bytes=sum(child.stat().st_size for child in files))
        shutil.rmtree(path)
    record['absent_after']=not path.exists()
    assert record['absent_after']
    cleanup.append(record)

now=dt.datetime.now(dt.timezone.utc)
budget=load(OUT/'evidence/resume-budget.json')
within=now<=dt.datetime.fromisoformat(budget['deadline_utc'])
assert within
input_paths={ROOT/name for name in before if Path(name).name!='decisions.tsv'}
input_paths.update(ROOT/name for name in source_artifacts)
record={'status':'PASS_FINAL_CHECK','utc':now.isoformat(),'timebox':budget,'within_timebox':within,
        'volume_uuid':volume['VolumeUUID'],'filesystem':volume['FilesystemType'],
        'protected_inputs_checked':checked,'protected_inputs_changed':changed,
        'source_trees_equal_to_resume':True,
        'additional_build_artifacts_checked':len(source_artifacts),
        'dat_sha256':PIN,'body_sha256':BODY,'implementation_list_count':130,
        'implementation_list_matching':129,'implementation_list_known_change':implementation,
        'decisions_excluded':True,'remaining_review_workers':active,
        'external_input_manifest_entries':len(input_paths),
        'regression_groups_closed':ledger['closed'],'regression_groups_total':ledger['total'],
        'group_status_counts':{status:sum(row['status']==status for row in ledger['groups']) for status in ('PASS','CLOSED_KNOWN_P2')},
        'temporary_directories':cleanup,'text_rules':'PASS',
        'formal_outputs':{name:digest(OUT/name) for name in ('REVIEW.md','REGRESSIONS.md','regressions-final.json')}}
(OUT/'evidence/seal.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
assert not rules['scan']()
files=[]
for path in sorted(OUT.rglob('*')):
    assert not path.is_symlink(),str(path)
    if path.is_file() and path.name not in ('SHA256SUMS','decisions.tsv'):files.append(path)
files=sorted(set(files)|input_paths)
manifest=OUT/'SHA256SUMS'
manifest.write_text(''.join(f'{digest(path)}  {path.relative_to(ROOT)}\n' for path in files))
for line in manifest.read_text().splitlines():
    expected,name=line.split(None,1)
    assert digest(ROOT/name)==expected,name
print(json.dumps({'status':'PASS_FINAL_CHECK','manifest_files':len(files),'closed':ledger['closed'],
                  'review_sha256':digest(OUT/'REVIEW.md'),'manifest_sha256':digest(manifest),
                  'temporary_directories_absent':all(row['absent_after'] for row in cleanup)},ensure_ascii=False))
