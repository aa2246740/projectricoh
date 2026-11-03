"""Verify frozen inputs and remove only this review's temporary root."""
from pathlib import Path
import ast,datetime,hashlib,json,os,plistlib,shutil,subprocess
r=Path(__file__).resolve().parent
w=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
t=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r4')
volume=subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']);(r/'volume.plist').write_bytes(volume);disk=plistlib.loads(volume)
assert disk['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and disk['FilesystemType']=='apfs' and disk['WritableVolume']
assert t.is_dir() and not t.is_symlink() and t.resolve()==t
assert json.loads((r/'pr-delivery-state.json').read_text())['headRefOid']=='fb6bacc51a35ee56736f9af4de5aa624cfd4ac14'
manifest=json.loads((r/'source-before.json').read_text());after={f:hashlib.sha256((w/f).read_bytes()).hexdigest() for f in manifest}
changed=[f for f,h in manifest.items() if after[f]!=h];copy_changed=[f for f,h in manifest.items() if hashlib.sha256((t/'source'/f).read_bytes()).hexdigest()!=h]
assert changed==copy_changed==[],(changed,copy_changed)
prior=json.loads((r/'prior-input-hashes.json').read_text());prior_changed=[p for p,h in prior.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h];assert not prior_changed
env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','TMPDIR':str(t)}
head=subprocess.check_output(['git','-C',str(w),'rev-parse','HEAD'],env=env,text=True).strip();assert head=='fb6bacc51a35ee56736f9af4de5aa624cfd4ac14'
status=subprocess.check_output(['git','-C',str(w),'status','--porcelain=v1','--untracked-files=all'],env=env,text=True);assert not status,status
(r/'final-status.txt').write_text(status);(r/'source-after.json').write_text(json.dumps(after,indent=2)+'\n')
start=datetime.datetime.fromisoformat(json.loads((r/'preflight.json').read_text())['utc']).timestamp();recent=[]
for directory in ['src','tests','scripts']:
 for p in (w/directory).rglob('*.pyc'):
  if p.stat().st_mtime>=start:recent.append(str(p.relative_to(w)))
assert recent==[],recent
(r/'source-stability.json').write_text(json.dumps({'head':head,'tracked_files':len(manifest),'tracked_files_changed':changed,'temporary_copy_tracked_files_changed':copy_changed,'prior_input_count':len(prior),'prior_inputs_changed':prior_changed,'worktree_status':status,'recent_worktree_bytecode':recent},indent=2)+'\n')
events=[json.loads(s) for s in (r/'browser-lifecycle.jsonl').read_text().splitlines()];started=[x['pid'] for x in events if x['event']=='start'];closed=[x['pid'] for x in events if x['event']=='closed'];assert sorted(started)==sorted(closed) and len(started)==3
ps=subprocess.run(['ps','-p',','.join(map(str,started)),'-o','pid=,command='],capture_output=True,text=True);remaining=[s for s in ps.stdout.splitlines() if str(r/'pinned_chrome.mjs') in s];assert not remaining,remaining
# Compile report generators before removing their temporary execution context.
for name in ['write_report.py','reproduce.py','analyze_ci.py']:ast.parse((r/name).read_text())
subprocess.run(['df','-h','/Volumes/Workspace'],stdout=(r/'df-final.txt').open('w'),check=True)
shutil.rmtree(t)
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'temporary_root':str(t),'temporary_root_removed':not t.exists(),'owned_browser_start_count':len(started),'owned_browser_close_count':len(closed),'owned_browser_processes_remaining':remaining,'worktree_head':head,'tracked_files_changed':changed,'prior_inputs_changed':prior_changed,'nice':os.getpriority(os.PRIO_PROCESS,0)}
assert receipt['temporary_root_removed'];(r/'cleanup.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
