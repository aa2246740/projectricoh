"""Complete format observations after retaining the initial system comparison."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parent/'probe_format.py'),run_name='__main__')
