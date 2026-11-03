"""Verify the frozen inputs, close-state receipts and remove only this review's scratch root."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess

OUT = Path(__file__).resolve().parent
WORKTREE = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r5')
disk = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
assert disk['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and disk['WritableVolume']
before = json.loads((OUT/'source-before.json').read_text())
after = {name: hashlib.sha256((WORKTREE/name).read_bytes()).hexdigest() for name in before}
changed = [name for name in before if before[name] != after[name]]
prior = json.loads((OUT/'prior-input-hashes.json').read_text())
prior_changes = [name for name, value in prior.items() if hashlib.sha256(Path(name).read_bytes()).hexdigest() != value]
status = subprocess.check_output(['git', '--no-optional-locks', '-C', str(WORKTREE), 'status', '--porcelain=v1', '--untracked-files=all'], text=True)
head = subprocess.check_output(['git', '-C', str(WORKTREE), 'rev-parse', 'HEAD'], text=True).strip()
assert not changed and not prior_changes and status == (OUT/'worktree-before.log').read_text()
assert head == '652847c0ea570ba4bc1e5e635055e3a1543ec996'
sessions = [json.loads(p.read_text()) for p in sorted((OUT/'cases').glob('*/browser-receipt.json'))]
assert len(sessions) == 3 and all(s['browserClosed'] for s in sessions)
processes = subprocess.check_output(['ps', '-axo', 'pid,ppid,ni,args'], text=True)
remaining = [line for line in processes.splitlines() if str(TMP) in line]
assert not remaining, remaining
files = [p for p in TMP.rglob('*') if p.is_file() and not p.is_symlink()]
bytes_removed = sum(p.stat().st_size for p in files)
count = len(files)
shutil.rmtree(TMP)
assert not TMP.exists()
(OUT/'source-after.json').write_text(json.dumps(after, indent=2)+'\n')
(OUT/'worktree-after.log').write_text(status)
(OUT/'source-stability.json').write_text(json.dumps({'head': head, 'source_files': len(before), 'source_changes': changed, 'prior_input_files': len(prior), 'prior_input_changes': prior_changes, 'git_state_unchanged': True}, indent=2)+'\n')
receipt = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'nice': os.getpriority(os.PRIO_PROCESS, 0),
           'temporary_root': str(TMP), 'temporary_root_removed': True, 'browser_sessions_closed': len(sessions),
           'task_processes_remaining': remaining, 'files_removed': count, 'bytes_removed': bytes_removed,
           'volume_uuid': disk['VolumeUUID']}
(OUT/'cleanup.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
