"""Freeze every existing regular repository file outside the three write roots."""
from pathlib import Path
import hashlib
import json
import os
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
ALLOWED = ('firmware/engine_v40_ux', 'firmware/package_v36_g119', 'research/ux_preview_dot_r2')

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def snapshot():
    result={}
    for base, dirs, files in os.walk(ROOT, followlinks=False):
        base=Path(base)
        dirs[:]=[d for d in dirs if d!='.git' and not (base/d).is_symlink()
                 and str((base/d).relative_to(ROOT)) not in ALLOWED]
        for name in sorted(files):
            p=base/name
            if p.is_symlink():result[str(p.relative_to(ROOT))]=['symlink',os.readlink(p)]
            elif p.is_file():result[str(p.relative_to(ROOT))]=[p.stat().st_size,digest(p)]
    return result

if __name__=='__main__':
    after='--after' in sys.argv
    data=snapshot()
    (OUT/('inputs-after.json' if after else 'inputs-before.json')).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
    if after:
        before=json.loads((OUT/'inputs-before.json').read_text())
        changes={k:dict(before=before.get(k),after=data.get(k)) for k in before.keys()|data.keys() if before.get(k)!=data.get(k)}
        (OUT/'input-integrity.json').write_text(json.dumps(dict(files=len(before),unchanged=not changes,changes=changes),indent=2)+'\n')
        assert not changes,changes
    print('UNCHANGED' if after else 'FROZEN',len(data),flush=True)
