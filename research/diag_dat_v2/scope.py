"""Input identities and the three output directories for diag v2."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUTS = (ROOT/'firmware/engine_diag_v2', ROOT/'firmware/package_v36_diag2', HERE)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()

def save(path, value):
    p = Path(path).resolve()
    if not any(p == d or d in p.parents for d in OUTPUTS):
        raise ValueError('OUTSIDE_OUTPUT_DIRECTORIES')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)+'\n')

def freeze_check():
    records = json.loads((HERE/'inputs-before.json').read_text())
    changed = [p for p, v in records.items()
               if not (ROOT/p).is_file() or sha(ROOT/p) != v['sha256']]
    if changed:
        save(HERE/'input-changes.json', changed)
        raise RuntimeError('STOP_FROZEN_INPUT_CHANGED')
    return len(records)
