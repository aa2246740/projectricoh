"""Regenerate the engine-local evidence list and read back every entry."""
from pathlib import Path
import json
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import OUT,TREE,DAT,save,file_sha

manifest=TREE/'EVIDENCE_SHA256SUMS'
paths=sorted(p for p in TREE.rglob('*') if p.is_file() and p!=manifest)
rows=[(file_sha(p),str(p.relative_to(TREE))) for p in paths]
manifest.write_text(''.join(digest+'  '+name+'\n' for digest,name in rows))
for digest,name in rows:assert file_sha(TREE/name)==digest,name
checked=subprocess.run(['/usr/bin/shasum','-a','256','-c',str(manifest)],cwd=TREE,capture_output=True,text=True)
log=OUT/'r2/evidence-selfcheck.log';log.write_text(checked.stdout+checked.stderr)
assert checked.returncode==0 and len(checked.stdout.splitlines())==len(rows)
assert all(s.endswith(': OK') for s in checked.stdout.splitlines())
save('r2/evidence-manifest.json',dict(status='PASS',entries=len(rows),dat_sha256=file_sha(DAT),
    manifest='firmware/engine_v44_keep/EVIDENCE_SHA256SUMS',manifest_sha256=file_sha(manifest),
    paths_relative_to='firmware/engine_v44_keep',excludes_only_itself=True,
    previous_manifest='r2/before/EVIDENCE_SHA256SUMS',previous_mismatches=100,
    log='r2/evidence-selfcheck.log'))
print('PASS regenerated EVIDENCE_SHA256SUMS',len(rows),'entries',flush=True)
