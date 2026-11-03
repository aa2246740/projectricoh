from pathlib import Path
import runpy
import sys
sys.argv = [__file__, 'resident']
runpy.run_path(str(Path(__file__).resolve().parents[3] / 'research/emptystack_v38/build_tools.py'), run_name='__main__')
