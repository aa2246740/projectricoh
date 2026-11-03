"""Record reviewed input identities and copy write-producing entry points."""
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, TMP, emit, enable, sha

enable()
copies = [
    ('tools/speedlab/adapters/accept_g137.py', 'adapters/accept_g137.py'),
]
records=[]
for source, destination in copies:
    target=HERE/destination
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT/source, target)
    records.append(dict(source=source, copy=destination, source_sha256=sha(ROOT/source), copy_sha256=sha(target)))
emit(HERE/'local/entry-copies.json', records)
manifest=ROOT/'research/speed_hillclimb/SHA256SUMS'
checks=[]
for row in manifest.read_text().splitlines():
    expected, name=row.split(None, 1)
    path=ROOT/name.lstrip('*')
    actual=sha(path) if path.is_file() else None
    checks.append(dict(path=str(path.relative_to(ROOT)), expected=expected, actual=actual, equal=actual==expected))
emit(HERE/'local/implementation-manifest.json', dict(manifest_sha256=sha(manifest), count=len(checks),
     passed=all(c['equal'] for c in checks), mismatches=[c for c in checks if not c['equal']]))
inputs=json.loads((ROOT/'research/speed_hillclimb/INPUTS.json').read_text())['files']
paths=set(inputs)
for folder in ('tools/native_harness','tools/native_harness_c','tools/speedlab','tools/gxr_emulator_batch'):
    paths.update(str(p.relative_to(ROOT)) for p in (ROOT/folder).rglob('*') if p.is_file())
paths.update(c['path'] for c in checks)
before={name:sha(ROOT/name) for name in sorted(paths)}
emit(HERE/'local/inputs-before.json', before)
emit(HERE/'local/frozen-input-check.json', dict(count=len(inputs), passed=all(before[n]==v for n,v in inputs.items()),
     mismatches=[n for n,v in inputs.items() if before[n]!=v]))
print(json.dumps(dict(manifest_count=len(checks), manifest_passed=all(c['equal'] for c in checks),
     recorded_inputs=len(before), frozen_inputs=len(inputs), frozen_passed=all(before[n]==v for n,v in inputs.items()))), flush=True)
