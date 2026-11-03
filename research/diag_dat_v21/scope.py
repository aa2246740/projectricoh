from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUTPUTS=(ROOT/'firmware/engine_diag_v21',ROOT/'firmware/package_v36_diag21',HERE)
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def save(path,value):
    p=Path(path).resolve()
    if not any(p==d or d in p.parents for d in OUTPUTS):raise RuntimeError('WRITE_LIMIT')
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
def freeze_check():
    records=json.loads((HERE/'local/inputs-before.json').read_text())
    changed=[p for p,h in records.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    if changed:raise RuntimeError('FROZEN_INPUT_CHANGED')
    return len(records)
