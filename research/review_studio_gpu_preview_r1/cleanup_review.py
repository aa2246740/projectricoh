"""Stop only this review's server, verify inputs, and delete its owned scratch."""
import datetime,hashlib,json,os,plistlib,select,shutil,signal,subprocess
from pathlib import Path

REPORT=Path(__file__).resolve().parent
SCRATCH=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r1')
WT=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
volume=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
assert volume['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and volume['FilesystemType']=='apfs' and volume['Writable']
assert not SCRATCH.is_symlink() and SCRATCH.resolve()==SCRATCH
commands=subprocess.check_output(['ps','-axo','pid=,args='],text=True).splitlines()
servers=[];unexpected=[]
for line in commands:
    parts=line.strip().split(None,1)
    if len(parts)!=2:continue
    pid=int(parts[0]);cmd=parts[1]
    if str(REPORT/'prepare_session.py') in cmd:
        comm=subprocess.check_output(['ps','-p',str(pid),'-o','comm='],text=True).strip()
        if Path(comm).name.lower().startswith('python'):servers.append(pid)
    if str(SCRATCH) in cmd and ('chrome-headless-shell' in cmd or 'gxr_studio.lut.worker' in cmd):unexpected.append({'pid':pid,'command':cmd})
assert not unexpected,unexpected
stopped=[]
for pid in servers:
    queue=select.kqueue()
    try:
        event=select.kevent(pid,filter=select.KQ_FILTER_PROC,flags=select.KQ_EV_ADD|select.KQ_EV_ENABLE,fflags=select.KQ_NOTE_EXIT)
        try:
            queue.control([event],0,0)
            os.kill(pid,signal.SIGINT)
        except ProcessLookupError:
            stopped.append({'pid':pid,'already_exited':True});continue
        events=queue.control(None,1,30)
        assert events,'Review server did not exit within 30 seconds'
        stopped.append({'pid':pid,'signal':'SIGINT','exit_event':True})
    finally:
        queue.close()
frozen=json.loads((REPORT/'frozen-inputs.json').read_text())
changed=[p for p,sha in frozen['files'].items() if not (WT/p).is_file() or hashlib.sha256((WT/p).read_bytes()).hexdigest()!=sha]
private=json.loads((REPORT/'real-inputs.json').read_text())['files']
private_changed=[x['path'] for x in private if hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()!=x['sha256']]
head=subprocess.check_output(['git','--no-optional-locks','rev-parse','HEAD'],cwd=WT,text=True).strip()
status=subprocess.check_output(['git','--no-optional-locks','status','--porcelain=v1','--untracked-files=all'],cwd=WT,text=True)
assert not changed and not private_changed and head==frozen['head'] and not status
stability={'head':head,'tracked_files':len(frozen['files']),'tracked_changed':changed,'private_inputs':len(private),'private_inputs_changed':private_changed,'git_status':status}
(REPORT/'source-stability-final.json').write_text(json.dumps(stability,indent=2)+'\n')
if SCRATCH.exists():shutil.rmtree(SCRATCH)
result={'complete':not SCRATCH.exists(),'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scratch':str(SCRATCH),'scratch_deleted':not SCRATCH.exists(),'stopped_servers':stopped,'remaining_owned_chromium_or_lut_workers':unexpected,'volume_uuid':volume['VolumeUUID'],'source_stability':stability,'preserved':'Report, scripts, JSON/XML/text receipts, coverage database, rebuilt project-owned engine; no original media, DAT bytes, calibration arrays or third-party LUT files.'}
(REPORT/'cleanup.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
