import difflib
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_v38_g137'
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def source_files(path):
    return {str(p.relative_to(path)): p for p in path.rglob('*')
            if p.is_file() and not any(v in p.parts for v in ('local', '__pycache__', '.git'))
            and p.suffix != '.pyc'}

rows = []
for before, after in [('firmware/resident_v37', 'firmware/resident_v38'),
                      ('firmware/engine_v53_g135', 'firmware/engine_v54_g137')]:
    old, new = source_files(ROOT / before), source_files(ROOT / after)
    changed, equal = [], 0
    for name in sorted(old.keys() | new.keys()):
        a, b = old.get(name), new.get(name)
        if a and b and digest(a) == digest(b):
            equal += 1
            continue
        row = {'path': name, 'before': digest(a) if a else None, 'after': digest(b) if b else None}
        if a and b and b.suffix in ('.c', '.h', '.S', '.ld'):
            matcher = difflib.SequenceMatcher(a=a.read_text().splitlines(), b=b.read_text().splitlines(), autojunk=False)
            row['line_changes'] = [{'kind': k, 'old': [i+1, j], 'new': [s+1, t]}
                                   for k, i, j, s, t in matcher.get_opcodes() if k != 'equal']
        changed.append(row)
    rows.append({'before_tree': before, 'after_tree': after, 'same_files': equal, 'changed_files': changed})

artifacts = {}
for name in ['firmware/engine_v54_g137/candidate/local/full-r13/engine.elf',
             'firmware/engine_v54_g137/candidate/local/full-r13/engine.bin',
             'firmware/resident_v38/local/resident/build/resident.elf',
             'firmware/engine_v54_g137/candidate/local/full-r13/manifest.json',
             'firmware/resident_v38/local/resident/patch-manifest.json']:
    p = ROOT / name
    artifacts[name] = {'bytes': p.stat().st_size, 'sha256': digest(p)}

result = {'source_pairs': rows, 'artifacts': artifacts}
(OUT / 'evidence' / (sys.argv[1] if len(sys.argv)>1 else 'source-review.json')).write_text(json.dumps(result, indent=2) + '\n')
for row in rows:
    print(row['after_tree'], 'same', row['same_files'])
    for file in row['changed_files']:
        print(file['path'], file.get('line_changes', 'metadata or script'))
