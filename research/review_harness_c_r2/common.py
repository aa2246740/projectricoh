"""Review-local paths for copied speedlab runners."""
import hashlib
import json
from pathlib import Path
import resource
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope_guard import HERE as WORK, ROOT, TMP as TEMP, emit, enable, load, sha

TOOLS=ROOT/'tools/speedlab'
LOCAL=WORK/'local'
PYTHON='/usr/bin/python3'

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def private(path):
    path=Path(path).resolve()
    if not path.is_relative_to(WORK):
        raise ValueError('review-local artifact required')
    return path

def verify_inputs():
    manifest=json.loads((ROOT/'research/speed_hillclimb/INPUTS.json').read_text())
    changed=[name for name,value in manifest['files'].items() if sha(ROOT/name)!=value]
    if changed:
        raise ValueError('frozen input identity differs: '+', '.join(changed[:8]))
    return digest(manifest)

def usage():
    own=resource.getrusage(resource.RUSAGE_SELF)
    child=resource.getrusage(resource.RUSAGE_CHILDREN)
    return dict(total_cpu_seconds=own.ru_utime+own.ru_stime+child.ru_utime+child.ru_stime)

def environment():
    import os
    import time
    return dict(load_average=list(os.getloadavg()),logical_cpus=os.cpu_count(),
                nice=os.getpriority(os.PRIO_PROCESS,0),python=sys.version,
                started_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'))
