"""Complete the directory checks and preserve precise audit semantics."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parent/'probe_paths.py'),run_name='__main__')
