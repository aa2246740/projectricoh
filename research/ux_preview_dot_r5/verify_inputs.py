"""Recheck every protected input and reject added or missing protected files."""
from pathlib import Path
import concurrent.futures,json,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,file_sha,save
before=json.loads((OUT/'inputs-before.json').read_text())
roots=json.loads((OUT/'protected-roots.json').read_text())
paths=[]
for name in roots:
 root=ROOT/name
 paths.extend([root] if root.is_file() else [q for q in root.rglob('*') if q.is_file()])
paths=sorted(set(paths))
def record(q):
 return str(q.relative_to(ROOT)).encode().hex(),dict(bytes=q.stat().st_size,sha256=file_sha(q))
started=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
 after=dict(executor.map(record,paths))
changed=[k for k in before if k in after and before[k]!=after[k]]
added=sorted(set(after)-set(before));missing=sorted(set(before)-set(after))
save('inputs-after.json',after)
save('input-integrity.json',dict(status='PASS' if not changed and not added and not missing else 'FAIL',files=len(before),after_files=len(after),changed=changed,added=added,missing=missing,seconds=time.monotonic()-started))
assert not changed and not added and not missing,(len(changed),len(added),len(missing))
print('PASS protected input files',len(before),'unchanged',flush=True)
