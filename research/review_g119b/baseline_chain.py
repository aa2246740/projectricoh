"""Bind the current delta to the completed gen117 to gen118 review."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,save,file_sha
base=ROOT/'research/review_g118'
identity=json.loads((base/'identity.json').read_text())
current=json.loads((OUT/'identity.json').read_text())
assert identity['117']['dat']=='35ce20ac843764b9cdd452785683ebf99004c47b77ae90720c2e3dc716c31211'
assert identity['118']['dat']==current['118']['dat'] and identity['118']['elf']==current['118']['elf']
closure=json.loads((base/'codegen-closure.json').read_text())
branches=json.loads((base/'branch-closure.json').read_text())
assert closure['all_changed_accounted'] and not closure['unresolved']
assert all(row['status']=='ACCOUNTED' and not row['unexplained'] for row in branches.values())
checks=0;fail=[]
manifest=base/'SHA256SUMS'
for line in manifest.read_text().splitlines():
    expected,name=line.split('  ',1);target=(base/name).resolve();assert target.is_relative_to(base)
    checks+=1
    if file_sha(target)!=expected:fail.append(name.encode().hex())
assert not fail,fail
save('codegen-baseline-chain.json',dict(status='PASS_BASELINE_BOUND',
    baseline_dat=identity['117']['dat'],intermediate_dat=identity['118']['dat'],intermediate_elf=identity['118']['elf'],
    manifest_sha256=file_sha(manifest),manifest_files=checks,manifest_failed=[],
    previous_obligations=len(closure['symbol_obligations']),previous_changed_shared=closure['changed_shared'],
    previous_all_changed_accounted=True,previous_branch_functions=sorted(branches),
    files={name:file_sha(base/name) for name in ('REVIEW.md','identity.json','codegen-closure.json','branch-closure.json')},
    scope='Gen117 to gen118 closure reuses the user-supplied completed baseline after full manifest and artifact binding checks. Gen118 to gen119 is newly reviewed here; no interrupted gen119 result is used.'))
print('PASS gen117 to gen118 baseline binding; manifest',checks,'/',checks,'OK',flush=True)
