"""Verify the separately supplied name-data directory remains unchanged."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,save,file_sha
before=json.loads((OUT/'name-inputs-before.json').read_text())
paths=sorted(p for p in (ROOT/'research/three_module_audit_r1').rglob('*') if p.is_file())
after={str(p.relative_to(ROOT)).encode().hex():dict(bytes=p.stat().st_size,sha256=file_sha(p)) for p in paths}
save('name-inputs-after.json',after)
assert after==before
save('name-input-integrity.json',dict(status='PASS',files=len(before),changed=0,added=0,missing=0))
print('PASS name-data inputs',len(before),'unchanged',flush=True)
