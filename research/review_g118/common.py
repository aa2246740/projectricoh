"""Read-only review helpers. All generated files must stay under this directory."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
START_UTC = '2026-10-27T04:56:26Z'
DEADLINE_UTC = '2026-10-27T07:26:26Z'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def save(name, data):
    p = (OUT / name).resolve()
    assert p.is_relative_to(OUT), p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

PROTECTED = (
    'firmware/engine_v39_ux', 'firmware/package_v36_g118',
    'firmware/engine_v38_b36', 'firmware/package_v36_g117',
    'firmware/resident_v36', 'firmware/image_v36',
    'research/ux_preview_dot_r1', 'research/review_g117_container',
    'research/review_g117_codegen', 'research/review_g117_codegen_r2',
    'research/review_v36_body', 'research/review_v35_body',
    'research/cpu_speed_r1', 'tools/native_harness',
    'artifacts/downloads/gxr-151.zip', 'artifacts/firmware/gxr-1.51',
)

def snapshot():
    result = {}
    for name in PROTECTED:
        base = ROOT / name
        files = sorted(base.rglob('*')) if base.is_dir() else [base]
        for p in files:
            if p.is_file():
                result[str(p.relative_to(ROOT))] = [p.stat().st_size, file_sha(p)]
    return result

if __name__ == '__main__':
    if '--after' not in sys.argv:
        data = snapshot()
        save('inputs-before.json', data)
        save('scope.json', dict(start=START_UTC, deadline=DEADLINE_UTC,
             write_directory=str(OUT), protected=PROTECTED, files=len(data),
             no_camera=True, no_build=True, no_subagents=True))
        print('FROZEN', len(data), flush=True)
    else:
        before = json.loads((OUT / 'inputs-before.json').read_text())
        after = snapshot()
        changes = {k: dict(before=before.get(k), after=after.get(k))
                   for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
        save('inputs-after.json', after)
        save('input-integrity.json', dict(files=len(before), unchanged=not changes, changes=changes))
        print('INPUTS_UNCHANGED', not changes, len(before), flush=True)
        assert not changes, changes
