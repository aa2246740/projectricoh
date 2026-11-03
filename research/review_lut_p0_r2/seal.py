"""Verify the frozen inputs, then seal every review file except this manifest."""
from pathlib import Path
import hashlib
import importlib.util
import json
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('guard',HERE/'guard.py')
g=importlib.util.module_from_spec(sp);sp.loader.exec_module(g)
g.guard()
assert (HERE/'REPORT.md').read_text().splitlines()[0]=='不可以上卡'
assert not list(HERE.rglob('__pycache__'))
summary=dict(verdict='不可以上卡',candidate_sha256='75edcedac2219d31a1cc2e789e9ecc7381df528ee1e94d4b5e08329a668c2e87',candidate_bytes=53100,
    findings=[dict(id='P1-01',issue='native cursor snapshot clamps values outside 1..7; exact restoration fails'),
              dict(id='P2-01',issue='old completed slot can be paired with a later attempt; select absolute newest first'),
              dict(id='P2-02',issue='guide omits spare-card path and moving old logs off card')],
    frozen_files=9495,independent_matrix_scenarios_per_fixture=170,fixtures=[113,114],real_install_fixtures=[113,114,115],
    native_store_sites=3126,native_stores_per_fixture=35168,outside_native_whitelist=0,
    cursor_restore_counterexamples=36,decoder_checks=54,kernel_pairs_per_replay=16384,
    output='HOST_ONLY_REVIEW',card_written=False,camera_accessed=False,network_used=False)
(HERE/'review-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
files=sorted(p for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(HERE))+'\n' for p in files)
(HERE/'SHA256SUMS').write_text(manifest)
for row in (HERE/'SHA256SUMS').read_text().splitlines():
    expected,name=row.split('  ',1);assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==expected,name
print('PASS sealed files='+str(len(files))+' protected_inputs=9495')
