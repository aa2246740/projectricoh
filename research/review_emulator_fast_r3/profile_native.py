"""Untimed native limiter sample; separate from every reported benchmark pair."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review as V

assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
sys.addaudithook(V.fence)
os.environ['TMPDIR'] = str(V.TEMP)
R = V.runner(); R.setup('native')
ctx = R.construct('main', 'profile-native'); c = ctx.machine.cpu
with (V.RUNS / 'profile-sampler.log').open('x') as log:
    sampler = subprocess.Popen(['/usr/bin/sample', str(os.getpid()), '2', '10', '-file',
                                str(V.RUNS / 'profile-native.sample.txt')], stdout=log, stderr=subprocess.STDOUT)
    start = time.perf_counter(); stop = c.run(200000000)
    seconds = time.perf_counter() - start
    sampler_code = sampler.wait(timeout=30)
result = dict(pid=os.getpid(), sampler_returncode=sampler_code, steps=c.steps, stop=stop.to_dict(),
              seconds_not_for_benchmark=seconds, native=c._native_driver.stats(),
              state=V.fingerprint(ctx), library_sha256=V.sha_file(c.library_path))
(V.RUNS / 'profile-native.json').write_text(json.dumps(result, indent=2) + '\n')
ctx.machine.close()
print(json.dumps(dict(steps=result['steps'], stop=result['stop'], sampler_returncode=sampler_code)))
