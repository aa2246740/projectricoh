"""Verify frozen inputs, remove only this review's Scratch, and seal outputs."""
from pathlib import Path
import datetime
import json
import os
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
before=json.loads((scope.HERE/'inputs-before.json').read_text())
after=scope.inputs()
changed=sorted(k for k in before.keys()|after.keys() if before.get(k)!=after.get(k))
scope.save(scope.HERE/'inputs-after.json',after)
assert not changed,changed
processes=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,ni=,command='],text=True)
active=[]
for line in processes.splitlines():
    if str(scope.HERE)+'/' in line and 'python' in line:
        fields=line.strip().split(None,3)
        pid=int(fields[0])
        if pid not in (os.getpid(),os.getppid()):
            active.append(line.strip())
assert not active,active
removed=0
for p in sorted(scope.SCRATCH.rglob('*'),key=lambda p:len(p.parts),reverse=True):
    if p.is_dir() and not p.is_symlink():
        p.rmdir()
    else:
        p.unlink()
    removed+=1
scope.SCRATCH.rmdir()
scope.save(scope.HERE/'seal.json',dict(
    status='SEALED',finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    frozen_inputs=len(before),frozen_input_changes=changed,
    remaining_review_test_processes=active,
    scratch=str(scope.SCRATCH),scratch_exists_after_cleanup=scope.SCRATCH.exists(),
    scratch_entries_removed=removed,
    write_outputs=[str(scope.HERE),str(scope.SCRATCH)],
    network_or_card_access_initiated=False,git_write_commands=False,subagents_started=0))
files=sorted(p for p in scope.HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
lines=['%s  %s\n'%(scope.sha(p),p.relative_to(scope.ROOT)) for p in files]
(scope.HERE/'SHA256SUMS').write_text(''.join(lines))
for p,line in zip(files,lines):
    assert scope.sha(p)==line.split()[0]
print('SEALED',len(before),'inputs unchanged',len(files),'output checksums','scratch_removed',flush=True)
