"""Execute the original conformance entry point with its cache redirected."""
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools/native_harness"))
import python_backend
python_backend.CACHE = HERE / "local/integration/conformance-decode"
runpy.run_path(str(ROOT / "tools/native_harness/conformance.py"), run_name="__main__")
