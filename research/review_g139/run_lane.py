"""Run an explicit sequential job list using foreground waits."""
from pathlib import Path
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
plan=json.loads((HERE/sys.argv[1]).read_text())
results=[]
for job in plan:
    command=['/usr/bin/python3','-I','-B',str(HERE/'run_case.py'),'--job',job['job'],
             '--timeout',str(job['timeout']),'--outputs',*job['outputs'],'--',*job['command']]
    result=subprocess.run(command,cwd=ROOT,timeout=job['timeout']+180)
    results.append(dict(job=job['job'],returncode=result.returncode))
    print('LANE_RESULT',json.dumps(results[-1]),flush=True)
(HERE/'evidence'/('lane-'+Path(sys.argv[1]).stem+'.json')).write_text(json.dumps(results,indent=2)+'\n')
raise SystemExit(any(r['returncode'] for r in results))
