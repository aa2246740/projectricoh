"""One serial, offline, scoped reproduction of the complete host research."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import subprocess
import time
import json
import support as s


def main():
    s.guard();start=time.monotonic()
    for name in ('smoke','calibrate','verify','amount_fit','interactions','previews'):
        remaining=10800-(time.monotonic()-start)
        if remaining<=0:raise TimeoutError('three-hour reproduction limit')
        with (s.LOCAL/(name+'.log')).open('w') as log:
            subprocess.run(['/usr/bin/python3','-I','-B',str(s.HERE/'src'/(name+'.py'))],
                           cwd=s.ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=remaining,check=True)
        print('DONE analysis phase',name,flush=True)
    subprocess.run(['/usr/bin/python3','-I','-B',str(s.HERE/'src/finalize.py')],cwd=s.ROOT,check=True)
    cal=json.loads((s.LOCAL/'calibration.json').read_text())
    interactions=json.loads((s.LOCAL/'interaction_verification.json').read_text())
    failed=sum(not p['visible'] for g in cal['groups'] for p in g['pairs'])
    if failed or interactions['below_threshold']:
        print('FAIL_VISIBILITY: artifacts sealed; individual pairs below threshold',failed,
              '; interaction pairs below threshold',interactions['below_threshold'],flush=True)
        raise SystemExit(2)


if __name__=='__main__':main()
