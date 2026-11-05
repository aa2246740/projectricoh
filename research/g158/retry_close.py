"""Cold replay of the exact close input, retaining its intermediate sample."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();out=C.LOCAL/'accept-r2'
old='r2-critical-release-50mm-P';label='r2c-critical-release-50mm-P'
result=json.loads((C.LOCAL/'runs'/old/'result.json').read_text())
assert result['status']=='ERROR' and result['failure_state']['state']==56 and result['failure_state']['rows']==7
assert not (C.LOCAL/'runs'/label).exists()
jobs=json.loads((out/'jobs.json').read_text());source=next(j for j in jobs if j['id']==old)
job=dict(source,id=label,script='research/g158/local/accept-r2/run_close_r2c.py',args=[label if a==old else a for a in source['args']],log=str(out/'logs'/(label+'.log')))
C.save(out/'jobs.before-close-retry.json',jobs);C.save(out/'jobs.json',[job]+jobs)
print(json.dumps(dict(status='COLD_CLOSE_REPLAY_QUEUED',original=old,label=label,extra_keys=0,original_window_budget=90)))
