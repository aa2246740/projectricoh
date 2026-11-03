"""Verify the volume outside the sandbox, then run a bounded sandboxed check."""
import os, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common_review import *
os.environ.setdefault('GXR_HARNESS_BACKEND','c')
guard(False)
target=(HERE/sys.argv[1]).resolve()
assert target.parent==HERE and target.suffix=='.py'
command=['/usr/bin/nice','-n','10','/usr/bin/sandbox-exec','-f',str(HERE/'offline.sb'),'/usr/bin/python3','-I','-B',str(target),*sys.argv[2:]]
result=subprocess.run(command,cwd=ROOT,timeout=10800)
raise SystemExit(result.returncode)
