"""Queue the close-replay proof and stage report, without altering case inputs."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();out=C.LOCAL/'accept-r2';jobs=json.loads((out/'jobs.json').read_text())
new=[dict(id='r2c-close-verify',script='research/g158/verify_close.py',args=[],needs=['r2c-critical-release-50mm-P'],log=str(out/'logs/r2c-close-verify.log')),
     dict(id='r2c-report-close',script='research/g158/finish_r2.py',args=[],needs=['r2c-close-verify','r2-report-S48'],log=str(out/'logs/r2c-report-close.log'))]
assert not set(j['id'] for j in jobs)&set(j['id'] for j in new)
C.save(out/'jobs.before-close-receipts.json',jobs);C.save(out/'jobs.json',new+jobs)
print(json.dumps(dict(status='CLOSE_PROOF_QUEUED',new_emulator_cases=0)))
