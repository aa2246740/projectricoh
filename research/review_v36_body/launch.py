"""A bounded command runner retaining stdout, stderr, exit code and duration."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
label, *argv = sys.argv[1:]
assert argv and label.replace("-", "").replace("_", "").isalnum()
start = time.monotonic()
with (HERE / (label + ".stdout.log")).open("w") as out, (HERE / (label + ".stderr.log")).open("w") as err:
    p = subprocess.run(argv, cwd=ROOT, stdout=out, stderr=err,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(HERE / "tmp")))
record = dict(argv=argv, returncode=p.returncode, seconds=round(time.monotonic()-start, 3))
(HERE / (label + ".execution.json")).write_text(json.dumps(record, indent=2)+"\n")
print(label, "exit", p.returncode, "seconds", record["seconds"], flush=True)
raise SystemExit(p.returncode)
