"""Freeze or verify all material inputs without writing to those inputs."""
from pathlib import Path
import hashlib
import json
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

target=OUT/'inputs-before.json'
if '--check' in sys.argv:
    data=json.loads(target.read_text())
    changed=[str(p) for p,h in data.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    (OUT/'integrity.json').write_text(json.dumps(dict(files=len(data),changed=changed),indent=2)+'\n')
    print('Protected inputs',len(data),'changed',len(changed))
    assert not changed,changed
else:
    assert not target.exists()
    paths={ROOT/line.split('  ',1)[1] for line in (ROOT/'research/g124_ui_v2/SHA256SUMS').read_text().splitlines()}
    for folder in ('research/review_g122','research/review_g123','research/ui_v2_design',
                   'firmware/engine_v43_fix','firmware/engine_v45_verify','firmware/resident_v36',
                   'tools/native_harness'):
        base=ROOT/folder
        paths.update(p for p in base.rglob('*') if p.is_file() and
                     ('local' not in p.relative_to(base).parts or p.suffix in ('.elf','.bin')))
    paths.add(ROOT/'research/g124_ui_v2/SHA256SUMS')
    data={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
    target.write_text(json.dumps(data,indent=2)+'\n')
    print('Protected inputs',len(data))
