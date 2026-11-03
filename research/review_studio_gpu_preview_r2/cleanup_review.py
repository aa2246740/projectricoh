"""Remove only this review's initially absent, explicitly owned temporary root."""
import datetime
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2')
WT=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
volume=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
assert volume['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and volume['FilesystemType']=='apfs' and volume['Writable']
assert TEMP.is_dir() and not TEMP.is_symlink() and TEMP.resolve()==TEMP
assert (TEMP/'studio/app-home/flags.json').is_file() and (HERE/'frozen-inputs.json').is_file()
ps=subprocess.check_output(['ps','-Ao','pid=,ppid=,command=']).decode()
processes=[]
for line in ps.splitlines():
    fields=line.strip().split(None,2)
    if len(fields)==3:processes.append((int(fields[0]),int(fields[1]),fields[2]))
parents={p:parent for p,parent,_ in processes}
own=set();pid=os.getpid()
while pid and pid not in own:own.add(pid);pid=parents.get(pid,0)
live=[]
for pid,parent,cmd in processes:
    if pid in own:continue
    if (str(TEMP) in cmd or str(HERE) in cmd) and ('node ' in cmd or 'Python ' in cmd or '/python ' in cmd or 'chrome-headless-shell ' in cmd):
        live.append({'pid':pid,'command':cmd})
assert not live,live
listener=subprocess.run(['lsof','-nP','-iTCP:49761','-sTCP:LISTEN'],capture_output=True,text=True)
assert not listener.stdout,listener.stdout
frozen=json.loads((HERE/'frozen-inputs.json').read_text())
changed=[p for p,d in frozen['files'].items() if not (WT/p).is_file() or hashlib.sha256((WT/p).read_bytes()).hexdigest()!=d]
assert not changed
head=subprocess.check_output(['git','--no-optional-locks','-C',str(WT),'rev-parse','HEAD']).decode().strip()
status=subprocess.check_output(['git','--no-optional-locks','-C',str(WT),'status','--short','--untracked-files=all']).decode()
assert head==frozen['head'] and status==(HERE/'initial-status.txt').read_text()
private=[];count=0;size=0
for root,dirs,files in os.walk(TEMP,followlinks=False):
    for name in files:
        p=Path(root)/name
        if p.is_symlink():continue
        n=p.stat().st_size;count+=1;size+=n
        rel=p.relative_to(TEMP)
        if rel.parts[0] in ('studio','camdata-inputs','baseline-main','baseline-head') or rel.parts[0].startswith(('readbacks','baseline-responses')):
            private.append({'path':str(rel),'bytes':n,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(HERE/'private-temp-artifact-hashes.json').write_text(json.dumps({'scope':'hashes and sizes only; all real input and derived image bytes removed with the owned temporary root','files':private},indent=2)+'\n')
shutil.rmtree(TEMP)
assert not TEMP.exists()
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'temporary_root':str(TEMP),'temporary_root_removed':True,'removed_regular_files':count,'removed_bytes':size,'review_processes_remaining':live,'isolated_port_49761_listening':False,'source_head':head,'tracked_source_files':len(frozen['files']),'changed_tracked_source_files':changed,'git_status_unchanged':True,'preexisting_ignored_caches_preserved':'cache-boundary-deviation.json','no_git_or_pr_writes':True,'owner_studio_and_real_cards_untouched':True}
(HERE/'cleanup.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
