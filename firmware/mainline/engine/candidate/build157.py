from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[3]/'research/g157/build.py'),run_name='__main__')
