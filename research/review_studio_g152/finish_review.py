"""Record final artifact receipts and remove only this review's scratch."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tarfile
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_review as r

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name,value):(HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def packages():
    rows=[]
    for p in sorted((r.SCRATCH/'preflight-dist').iterdir()):
        if not p.is_file() or not (p.suffix=='.whl' or p.name.endswith('.tar.gz')):continue
        if p.suffix=='.whl':
            with zipfile.ZipFile(p) as z:
                names=[n for n in z.namelist() if n.endswith('/engine/data/final.json')]
                members={n:hashlib.sha256(z.read(n)).hexdigest() for n in names}
        else:
            with tarfile.open(p) as z:
                members={m.name:hashlib.sha256(z.extractfile(m).read()).hexdigest() for m in z.getmembers() if m.isfile() and m.name.endswith('/engine/data/final.json')}
        rows.append({'name':p.name,'bytes':p.stat().st_size,'sha256':digest(p),'table_members':members})
    save('package-receipts.json',rows)
    print(json.dumps(rows,ensure_ascii=False))

def cleanup():
    info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['FilesystemType']=='apfs' and info['WritableVolume'] and info['MountPoint']=='/Volumes/Workspace'
    raw=subprocess.check_output(['ps','-axo','pid=,ppid=,command='],text=True)
    processes={}
    for line in raw.splitlines():
        pieces=line.strip().split(None,2)
        if len(pieces)==3:processes[int(pieces[0])]=(int(pieces[1]),pieces[2])
    ancestors={os.getpid()};pid=os.getpid()
    while pid in processes and processes[pid][0] not in ancestors:
        pid=processes[pid][0];ancestors.add(pid)
    matching=[{'pid':pid,'command':cmd} for pid,(_,cmd) in processes.items() if pid not in ancestors and (str(r.SCRATCH)+'/' in cmd or 'review_studio_g152/verify_ui_review.mjs' in cmd)]
    assert not matching,matching
    clones=[];profiles=[]
    if r.SCRATCH.exists():
        assert not r.SCRATCH.is_symlink() and r.SCRATCH.resolve()==r.SCRATCH
        for parent,dirs,_ in os.walk(r.SCRATCH,followlinks=False):
            for name in dirs:
                if 'code_sign_clone' in name:clones.append(str(Path(parent)/name))
                if 'playwright_chromiumdev_profile' in name:profiles.append(str(Path(parent)/name))
        shutil.rmtree(r.SCRATCH)
    after=r.snapshot('after')
    before=json.loads((HERE/'snapshot-before.json').read_text())
    assert before==after
    receipt={'finished_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'scratch':str(r.SCRATCH),'scratch_exists':r.SCRATCH.exists(),
             'remaining_task_processes':matching,'code_sign_clone_dirs_found':clones,'browser_profile_dirs_remaining_before_root_removal':profiles,
             'source_and_git_unchanged':True,'source_files':len(after['source']),'git_files':len(after['git']),
             'volume':{k:info[k] for k in ('VolumeUUID','FilesystemType','WritableVolume','MountPoint')}}
    save('cleanup.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':{'packages':packages,'cleanup':cleanup}[sys.argv[1]]()
