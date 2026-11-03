#!/usr/bin/python3 -I
"""Verify all firmware package manifests without changing their files."""
from pathlib import Path
import hashlib
import json

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
rows = []
for name, count in (('image_v39', 29), ('package_v39_body_only', 29), ('package_v39_g149', 31)):
    manifest = ROOT / 'firmware' / name / 'SHA256SUMS'
    files = []
    for line in manifest.read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        expected, relative = line.split(maxsplit=1)
        relative = relative.lstrip('*')
        path = ROOT / relative
        assert path.resolve().is_relative_to(ROOT)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, relative
        files.append({'path': relative, 'sha256': actual})
    assert len(files) == count and len({value['path'] for value in files}) == count
    rows.append({'manifest': str(manifest.relative_to(ROOT)), 'count': count, 'status': 'PASS', 'files': files})
out = ROOT / 'research/review_body_v39/evidence/package-manifests.json'
out.write_text(json.dumps(rows, indent=1) + '\n')
print(json.dumps({'status': 'PASS', 'entries': sum(row['count'] for row in rows)}))
