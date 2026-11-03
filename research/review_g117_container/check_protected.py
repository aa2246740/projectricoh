"""Rehash the frozen read inputs, without touching any protected tree."""
from pathlib import Path
import hashlib
import json
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
before = json.loads((OUT / 'protected-before.json').read_text())
after, changed = {}, []
for name, expected in before.items():
    p = ROOT / name
    digest = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    after[name] = digest
    if digest != expected:
        changed.append(dict(path=name, before=expected, after=digest))
(OUT / 'protected-after.json').write_text(json.dumps(after, indent=2) + '\n')
(OUT / 'protected-changes.json').write_text(json.dumps(dict(checked=len(before), changes=changed,
    checked_unix_time=time.time(), note='Other body work may run concurrently; changed inputs must be attributed explicitly.'), indent=2) + '\n')
print('Protected inputs:', len(before), 'content changes:', len(changed))
for row in changed:
    print(row['path'], row['before'], row['after'])
