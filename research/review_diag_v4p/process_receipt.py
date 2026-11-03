"""Read process state without changing any process or system setting."""
from datetime import datetime, timezone
from pathlib import Path
import json
import shlex
import subprocess

HERE=Path(__file__).resolve().parent
TEMP='/Volumes/Workspace/Scratch/tmp/projectricoh/review-diag-v4p-r1'
listing=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,ni=,args='],text=True)
active=[]
for line in listing.splitlines():
    parts=line.split(None,3)
    if len(parts)<4:continue
    try:argv=shlex.split(parts[3])
    except ValueError:continue
    if not argv:continue
    python=Path(argv[0]).name.lower().startswith('python')
    review=any(Path(arg).name=='review_checks.py' for arg in argv)
    compiler=Path(argv[0]).name.startswith(('m32r-elf-','cc1','lto1','lto-wrapper'))
    scratch=any(TEMP in arg for arg in argv)
    if python and review or compiler and scratch:
        active.append(dict(pid=int(parts[0]),ppid=int(parts[1]),nice=int(parts[2]),argv=argv))
result=dict(read_only=True,date_utc=datetime.now(timezone.utc).isoformat(),active=active)
(HERE/'processes-before-cleanup.json').write_text(json.dumps(result,indent=2)+'\n')
assert not active,active
print('PASS active review tests:',len(active))
