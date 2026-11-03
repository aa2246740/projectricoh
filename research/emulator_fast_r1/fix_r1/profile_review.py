"""Separate native sample target; excluded from reported timings."""
import json
import os
from pathlib import Path
import signal
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_runner as R
R.setup('native')
signal.alarm(600)
ctx=R.construct('main','profile-review-01')
c=ctx.machine.cpu
assert c.run(1000000).reason=='max_steps'
print(json.dumps({'pid':os.getpid(),'ready':True,'steps':c.steps}),flush=True)
try:
    stop=c.run(600000000)
    c.materialize_native()
    rec={'stop':stop.to_dict(),'steps':c.steps,'native':c._native_driver.stats(),
         'state':R.fingerprint(ctx),'timing_use':'excluded'}
    (R.RUNS/'profile-review-01.json').write_text(json.dumps(rec,indent=2)+'\n')
finally:
    ctx.machine.close()
    signal.alarm(0)
