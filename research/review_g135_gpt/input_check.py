from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


mode = sys.argv[1] if len(sys.argv) > 1 else 'before'
protected = {}
for folder in ['firmware/engine_v53_g135', 'firmware/package_v37_g135', 'firmware/resident_v37']:
    for path in sorted((ROOT / folder).rglob('*')):
        if path.is_file() and not path.is_symlink():
            protected[str(path.relative_to(ROOT))] = digest(path)
manifest = ROOT / 'research/review_g135/SHA256SUMS'
verified = 0
missing = 0
changed = 0
for row in manifest.read_text().splitlines():
    if not row.strip():
        continue
    expected, name = row.split(None, 1)
    path = ROOT / name.lstrip('* ')
    if not path.is_file():
        missing += 1
    elif digest(path) != expected:
        changed += 1
    else:
        verified += 1
summary = {'mode': mode, 'first_manifest_sha256': digest(manifest), 'first_manifest_verified': verified, 'first_manifest_missing': missing, 'first_manifest_changed': changed, 'protected_count': len(protected)}
(OUT / ('local/protected-' + mode + '.json')).write_text(json.dumps(protected, indent=2) + '\n')
if mode == 'after':
    previous = json.loads((OUT / 'local/protected-before.json').read_text())
    summary['protected_equal'] = previous == protected
(OUT / ('evidence/input-' + mode + '.json')).write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary))
