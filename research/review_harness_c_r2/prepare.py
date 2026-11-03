"""Create review-local copies and record the exact offline review inputs."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-harness-c-r2')

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def emit(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

copies = []
def copy(source, destination, replacements=()):
    raw = (ROOT/source).read_bytes()
    text = raw.decode()
    for old, new in replacements:
        if old not in text:
            raise ValueError('copy replacement absent: ' + old)
        text = text.replace(old, new)
    target = HERE/destination
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode())
    diff = ''.join(difflib.unified_diff(raw.decode().splitlines(True), text.splitlines(True),
                                      fromfile=source, tofile=destination))
    if diff:
        (HERE/'local'/(destination.replace('/','_')+'.diff')).write_text(diff)
    copies.append(dict(source=source, destination=destination, source_sha256=sha(ROOT/source),
                       copy_sha256=sha(target), byte_identical=not diff))

(HERE/'local').mkdir(parents=True, exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)
old_review = 'research/review_harness_c'
for name in ('scope_guard.py','run_entry.py','independent_cases.py','extended_cases.py',
             'trace_cases.py','default_cases.py','cache_cases.py','common.py','fixed_accept.py'):
    changes = [('review-harness-c\'','review-harness-c-r2\'')] if name=='scope_guard.py' else []
    copy(old_review+'/'+name, name, changes)
copy('tools/speedlab/content_cache.py','content_cache.py')
copy('tools/speedlab/adapters/accept_g137.py','adapters/accept_g137.py')
for name in ('write_tape.py','audit_tape.py'):
    copy('tools/speedlab/'+name,name)
copy('tools/speedlab/legacy_next.py','legacy_next.py',[
    ('HERE = ROOT / "research/speed_hillclimb"','HERE = ROOT / "research/review_harness_c_r2"'),
    ("sys.path.insert(0, str(ROOT / 'tools/speedlab'))","sys.path.insert(0, str(HERE))"),
    ("sys.path.remove(str(ROOT/'tools/speedlab'))","\n    while str(HERE) in sys.path:\n        sys.path.remove(str(HERE))"),
    ('/Volumes/Workspace/Scratch/tmp/projectricoh/speed-hillclimb',str(TMP)),
    (' or p.is_relative_to(ROOT / "tools/speedlab/harness_c_next")','')])
copy(old_review+'/legacy.py','legacy_a.py',[
    ('research/review_harness_c"','research/review_harness_c_r2"'),
    ('/Volumes/Workspace/Scratch/tmp/projectricoh/review-harness-c\'',str(TMP)+"'")])
fence = '(version 1)\n(allow default)\n(deny network*)\n(deny file-write*)\n' \
        '(allow file-write* (subpath "'+str(HERE)+'") (subpath "'+str(TMP)+'") (literal "/dev/null"))\n' \
        '(deny file-read* (subpath "/Volumes/RICOHDCX"))\n'
(HERE/'fence.sb').write_text(fence)
emit(HERE/'local/copied-inputs.json', copies)

manifest = ROOT/'research/speed_hillclimb/SHA256SUMS'
checks=[]
for row in manifest.read_text().splitlines():
    wanted, name=row.split(None,1)
    p=ROOT/name.lstrip('*')
    actual=sha(p) if p.is_file() else None
    checks.append(dict(path=name, expected=wanted, actual=actual, equal=actual==wanted))
emit(HERE/'local/implementation-manifest.json',dict(count=len(checks), passed=all(x['equal'] for x in checks),
     sha256=sha(manifest), mismatches=[x for x in checks if not x['equal']]))
frozen=json.loads((ROOT/'research/speed_hillclimb/INPUTS.json').read_text())['files']
paths=set(frozen)
for folder in ('tools/native_harness','tools/native_harness_c','tools/speedlab/harness_c_next',
               'research/review_g126','research/review_harness_c'):
    paths.update(str(p.relative_to(ROOT)) for p in (ROOT/folder).rglob('*')
                 if p.is_file() and 'local' not in p.relative_to(ROOT/folder).parts and '__pycache__' not in p.parts)
paths.update(x['source'] for x in copies)
paths.update(['tools/native_harness_c/local/ccore/build.json',
              'tools/speedlab/harness_c_next/local/ccore/build.json',
              'tools/speedlab/adapters/host_check.py','tools/speedlab/adapters/view_reference.py'])
for name in list(paths):
    if name.endswith('/local/ccore/build.json'):
        build=json.loads((ROOT/name).read_text())
        paths.add(str(Path(build['library']).relative_to(ROOT)))
before={name:sha(ROOT/name) for name in sorted(paths)}
emit(HERE/'local/inputs-before.json',before)
emit(HERE/'local/frozen-input-check.json',dict(count=len(frozen),passed=all(before[n]==v for n,v in frozen.items()),
     mismatches=[n for n,v in frozen.items() if before[n]!=v]))
(HERE/'decisions.tsv').write_text('ts\tphase\tdecision\twhy\tevidence\tresult\n')
print(json.dumps(dict(manifest_count=len(checks),manifest_passed=all(x['equal'] for x in checks),
      frozen_count=len(frozen),frozen_passed=all(before[n]==v for n,v in frozen.items()),
      execution_inputs=len(before),copies=len(copies))),flush=True)
