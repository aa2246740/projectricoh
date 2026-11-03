from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'
sys.tracebacklimit = 0
sys.argv = [str(OUT / 'bridge.py'), '--reference-proof']
runpy.run_path(str(OUT / 'bridge.py'), run_name='__main__')
