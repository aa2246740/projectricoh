"""Run bounded audit work sequentially in one nice-15 compute slot."""
from pathlib import Path
import json
import os
import runpy
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
for name in ['static_audit.py','receipt_audit.py','history_audit.py','old_fixture.py']:
    print('RUN',name,flush=True)
    runpy.run_path(str(C.HERE/name),run_name='__main__')
raw_path=C.HERE/'evidence/review-test-50mm-reference.json'
raw=json.loads(raw_path.read_text())
assert raw['status']=='FAIL'and raw['error']['type']=='KeyboardInterrupt'
C.save(C.HERE/'evidence/reference-normal-interrupted.json',dict(status='INTERRUPTED',
    raw_receipt=str(raw_path.relative_to(C.ROOT)),raw_sha256=C.sha(raw_path.read_bytes()),
    reason='Reviewer sent SIGINT to narrow independent reference sampling to old-record rejection. No assertion failed.',
    accepted_as_PASS=False,product_failure=False,final_steps=raw['final_steps'],completed_keys=len(raw['keys'])))
C.save(C.HERE/'evidence/audit-process.json',dict(status='PASS',pid=os.getpid(),nice=os.getpriority(os.PRIO_PROCESS,0),
    sequential_scripts=['static_audit.py','receipt_audit.py','history_audit.py','old_fixture.py']))
