"""Summarize retained evidence; produce the final dir-relative hash manifest."""
from pathlib import Path
import collections
import hashlib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit as a
here=a.HERE
runs=[json.loads(x) for x in (here/'isolated/candidate/local/v34c-host/runs.jsonl').read_text().splitlines()]
phases=json.loads((here/'host-stages.json').read_text())
extra=json.loads((here/'extra-results.json').read_text())
old=json.loads((a.ROOT/'firmware/engine_v36_r28/local/evidence-v34c/heap.json').read_text())
new=json.loads((here/'isolated/local/evidence-v34c/heap.json').read_text())
fields=('main_request','first_install_with_headers','first_install_with_existing_ui','steady_with_all_optional_allocations')
heap={k:{'gen115':old[k],'gen116':new[k],'delta':new[k]-old[k]} for k in fields}
assert all(p['returncode']==0 for p in phases) and all(x['returncode']==0 for x in extra)
assert len(phases)==22 and len(runs)==258
for rel in ('irom-duplicate-results.json','minimal-fix-readonly/host-results.json'):
 assert all(x['returncode']==0 for x in json.loads((here/rel).read_text()))
result=dict(host_stages=22,stage_status='PASS',host_runs=len(runs),host_cases=collections.Counter(x['case'] for x in runs),
 native_replay=json.loads((here/'native/replay-results.json').read_text())['status'],
 extra_units=3,extra_status='PASS',irom_duplicate_reproduced_units=3,readonly_containment_units=3,
 findings=['P0 SD ambiguous absence creates duplicate','P1 dirty close leaks wrapper count','P1 IROM ambiguous TEMP creates duplicate','P1 inherited cold cursor differs from live stock under literal requirement','P2 successful Fn2 missing witness','P2 stale builder report'],heap=heap,raw_stdout_files=['host-stages.stdout','history.stdout','extra.stdout','native-replay.stdout'])
a.dump('evidence-summary.json',result)
print(json.dumps(result,ensure_ascii=False,indent=2))
if '--hash' in sys.argv:
 files=sorted(p for p in here.rglob('*') if p.is_file() and p!=here/'SHA256SUMS' and not p.is_symlink())
 (here/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(here).as_posix()+'\n' for p in files))
 print('dir-relative SHA256SUMS entries',len(files))
