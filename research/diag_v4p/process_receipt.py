"""Filter a read-only process listing to this task; retain no unrelated rows."""
from pathlib import Path
import os
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
s.enable()
rows=[]
for line in sys.stdin:
    parts=line.strip().split(None,2)
    if len(parts)<3 or int(parts[0])==os.getpid():continue
    if Path(parts[1]).name.lower() in ('python','python3') and 'research/diag_v4p/' in parts[2]:rows.append(line.strip())
s.save(s.HERE/'evidence/processes-before-cleanup.json',dict(active_test_processes=rows,created_unix=time.time(),collector_pid=os.getpid()))
print('Process receipt',len(rows))
