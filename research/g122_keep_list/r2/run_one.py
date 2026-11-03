"""Execute a requested model command without its result-reuse shortcut."""
from pathlib import Path
import runpy
import sys

OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OUT))
# Import with this wrapper as argv[0], before choosing the actual script.
# This avoids common.record_command's cache; the parent writes the receipt.
import common
import extra_once
extra_once.record = lambda: None
parts = sys.argv[1:]
sys.argv = [str(OUT / parts[0]), *parts[1:]]
runpy.run_path(sys.argv[0], run_name='__main__')
