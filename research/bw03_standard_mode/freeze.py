"""Incremental protected-input ledger; all outputs stay in this task directory."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
LEDGER = LOCAL / 'inputs.json'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify():
    records = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    for name, record in records.items():
        path = ROOT / name
        if not path.is_file() or digest(path) != record['sha256']:
            raise SystemExit('STOP: protected input changed: ' + name)
    return records


def add(paths):
    records = verify()
    for path in paths:
        path = Path(path).resolve()
        if path.name == 'decisions.tsv':
            continue
        name = str(path.relative_to(ROOT))
        if path.is_relative_to(HERE):
            raise ValueError('Task outputs are not protected inputs: ' + name)
        if name not in records:
            records[name] = {'sha256': digest(path), 'size': path.stat().st_size}
    LOCAL.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(records, indent=2, sort_keys=True) + '\n')
    return records


if __name__ == '__main__':
    import sys
    paths = []
    for item in sys.argv[1:]:
        path = ROOT / item
        paths.extend(p for p in path.rglob('*') if p.is_file()
                     and not any(part in ('local', '__pycache__', '.git')
                                 for part in p.relative_to(path).parts)) if path.is_dir() else paths.append(path)
    records = add(paths) if paths else verify()
    print(json.dumps({'protected_inputs': len(records), 'unchanged': True}))
