"""Keep only this review's test processes from a read-only ps listing."""
from pathlib import Path
import json
import sys
import time

out=Path(__file__).resolve().parent
active=[]
for line in sys.stdin:
    fields=line.strip().split(maxsplit=4)
    if len(fields)!=5: continue
    pid,ppid,nice,state,command=fields
    executable=Path(command.split(maxsplit=1)[0]).name.lower()
    if executable.startswith('python') and 'research/review_g152/run.py' in command:
        active.append(dict(pid=int(pid),ppid=int(ppid),nice=int(nice),state=state,command=command))
record=dict(checked_ns=time.time_ns(),active_tests=active,source='ps -axo pid=,ppid=,ni=,state=,command=',scope='Only this review test runner; unrelated process commands are discarded.')
(out/'processes-final.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
assert not active,active
