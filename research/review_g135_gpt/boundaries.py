from pathlib import Path
import os
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'
LOCAL = OUT / 'local/jobs' / os.environ.get('REVIEW_JOB', 'boundaries')
sys.tracebacklimit = 0
sys.path.insert(0, str(ROOT / 'research/review_g135'))
try:
    api = runpy.run_path(str(ROOT / 'research/review_g135/boundary_sweep.py'), run_name='review_boundaries')
    namespace = api['main'].__globals__
    namespace['WORK'] = OUT / 'evidence'
    namespace['LOCAL'] = LOCAL
    api['main']()
except BaseException as error:
    print(type(error).__name__, str(error)[:500], flush=True)
    raise SystemExit(1)
