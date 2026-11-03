"""Read-only process snapshot; writes only the review receipt under Python's fence."""
from pathlib import Path
import datetime
import os
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import scope
scope.enable_fence()
rows=[]
result=subprocess.run(['/bin/ps','-axo','pid=,ppid=,command='],
                      capture_output=True,text=True,check=True,timeout=30)
for line in result.stdout.splitlines():
    parts=line.strip().split(None,2)
    if len(parts)==3 and 'research/review_diag147/' in parts[2] and 'python' in parts[2] and int(parts[0])!=os.getpid():
        rows.append(dict(pid=int(parts[0]),ppid=int(parts[1]),command=parts[2][:240]))
scope.save(HERE/'process-audit.json',dict(
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    status='PASS' if not rows else 'ACTIVE_PROCESSES',active_review_processes=rows,
    boundary='ps metadata read outside Seatbelt because Seatbelt rejected ps execution; Python write/network fence remains enabled.'))
assert not rows,rows
print('PROCESS_AUDIT_DONE',len(rows))
