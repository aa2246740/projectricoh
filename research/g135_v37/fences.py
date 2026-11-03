"""Write limits and immutable input checks for this task."""
from pathlib import Path
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g135_v37'
ENGINE = ROOT / 'firmware/engine_v53_g135'
PACKAGE = ROOT / 'firmware/package_v37_g135'
ALLOWED = (WORK.resolve(), ENGINE.resolve(), PACKAGE.resolve())

def check_inputs():
    frozen=json.loads((WORK/'inputs.json').read_text())
    changed=[name for name,digest in frozen.items() if not (ROOT/name).is_file() or
             hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
    if changed: raise RuntimeError('STOP_FROZEN_INPUT_CHANGED: '+repr(changed))
    return len(frozen)

def writable(value):
    if isinstance(value,int):return
    p=Path(os.fsdecode(value)).resolve()
    if not any(p.is_relative_to(parent) for parent in ALLOWED):
        raise PermissionError('STOP_WRITE_SCOPE: '+str(p))

def enable():
    def audit(event,args):
        if event=='open':
            path,mode,flags=args
            if (mode and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
                writable(path)
        elif event in ('os.mkdir','os.remove','os.rmdir','os.chmod','os.utime'):
            writable(args[0])
        elif event in ('os.rename','os.replace','os.link','os.symlink'):
            writable(args[1])
            if event in ('os.rename','os.replace'):writable(args[0])
    sys.addaudithook(audit)
    temporary=WORK/'local/tmp';temporary.mkdir(parents=True,exist_ok=True)
    os.environ.update(TMPDIR=str(temporary),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0')
