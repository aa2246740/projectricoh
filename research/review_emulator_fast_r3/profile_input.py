"""Separate native input-driver profile, excluded from every timing pair."""
import cProfile
import json
import os
from pathlib import Path
import pstats
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review as V

assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
sys.addaudithook(V.fence)
os.environ['TMPDIR'] = str(V.TEMP)
profiler = cProfile.Profile()
profiler.enable()
V.recipe('input_case', ['--backend', 'native', '--name', 'profile-input-native', '--steps', '50000000'])
profiler.disable()
profiler.dump_stats(str(V.RUNS / 'profile-input.prof'))
stats = pstats.Stats(profiler)
rows = [dict(file=key[0], line=key[1], name=key[2], primitive_calls=value[0], calls=value[1],
             self_seconds=value[2], cumulative_seconds=value[3]) for key, value in stats.stats.items()]
rows.sort(key=lambda r: r['cumulative_seconds'], reverse=True)
(V.RUNS / 'profile-input-functions.json').write_text(json.dumps(rows, indent=2) + '\n')
print(json.dumps(dict(status='PASS', profile='profile-input.prof', functions=len(rows))))
