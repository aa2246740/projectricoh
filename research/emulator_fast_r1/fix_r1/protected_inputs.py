"""Reproduce the historical protected-input mismatch without changing it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
p=argparse.ArgumentParser()
p.add_argument('--name',required=True)
a=p.parse_args()
assert a.name.replace('-','').isalnum()
assert os.getpriority(os.PRIO_PROCESS,0)>=10
out=HERE/'runs'/(a.name+'.json')
assert not out.exists()
rows=json.loads((ROOT/'tools/gxr_emulator/local/protected-inputs.json').read_text())['files']
different=[]
for row in rows:
    path=(ROOT/row['path']).resolve()
    assert path.is_relative_to(ROOT)
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''):h.update(block)
    if h.hexdigest()!=row['sha256']:
        different.append({'path':row['path'],'expected':row['sha256'],'actual':h.hexdigest()})
old=next(row for row in rows if row['path']=='.gitignore')
raw=(ROOT/'.gitignore').read_bytes()
result={'protected_files':len(rows),'different':different,
        'historical_prefix_matches':hashlib.sha256(raw[:old['size']]).hexdigest()==old['sha256'],
        'appended_bytes':len(raw)-old['size'],'appended_text':raw[old['size']:].decode()}
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'protected_files':len(rows),'different_files':[r['path'] for r in different],
                  'historical_prefix_matches':result['historical_prefix_matches'],'appended_bytes':result['appended_bytes']}))
