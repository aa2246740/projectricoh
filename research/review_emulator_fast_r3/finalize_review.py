"""Validate the finished report and freeze every input and R3 output hash."""
import datetime
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review as V

assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
sys.addaudithook(V.fence)
initial = json.loads((V.OUT / 'inputs.initial.json').read_text())
changes = {name: [old, V.sha_file(V.ROOT / name)] for name, old in initial['files'].items()
           if V.sha_file(V.ROOT / name) != old}
assert not changes, changes
(V.OUT / 'inputs.final.json').write_text(json.dumps(dict(
    files=len(initial['files']), changes=changes,
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat()), indent=2) + '\n')

report = (V.OUT / 'REVIEW.md').read_text()
assert report.splitlines()[0] == '修改后再采用'
assert len(re.findall(r'^## P1-', report, re.M)) == 3
assert len(re.findall(r'^## P2-', report, re.M)) == 2
assert not any(marker in report for marker in ('待测速结束', '测速结果待', 'TODO', 'TBD'))
for target in re.findall(r'\]\(([^)]+)\)', report):
    if target == 'SHA256SUMS':
        continue
    assert (V.OUT / target).is_file(), target
assessment = json.loads((V.RUNS / 'assessment-review.json').read_text())
assert assessment['normal_flows_all_equal']
assert assessment['historical']['counts'] == {'ACCEPTED': 1, 'REJECTED': 70}
assert assessment['models']['points'] == 48 and assessment['models']['rejected_changes'] == 64
assert json.loads((V.RUNS / 'driver-independent-state-audit.json').read_text())['status'] == 'PASS'
for name in ('main', 'input'):
    data = json.loads((V.RUNS / ('benchmark-' + name + '.json')).read_text())
    assert data['status'] == 'PASS' and len(data['pairs']) == 5
for path in V.OUT.glob('*.py'):
    compile(path.read_bytes(), str(path), 'exec')

manifest = V.OUT / 'SHA256SUMS'
receipt_path = V.OUT / 'runs/manifest-verification.json'
paths = {V.ROOT / name for name in initial['files']}
paths.update(p for p in V.OUT.rglob('*') if p.is_file() and p not in (manifest, receipt_path))
hashes = {str(p.relative_to(V.ROOT)): V.sha_file(p) for p in sorted(paths)}
receipt = dict(status='PASS', frozen_inputs=len(initial['files']), frozen_input_changes=0,
               verified_files=len(hashes) + 1, report_links_valid=True,
               normal_flows_equal=True, historical_accepted=1, historical_rejected=70,
               model_combinations=16, model_state_points=48, stale_model_rejections=64,
               timing_pairs=dict(main=5, input=5), findings=dict(P1=3, P2=2),
               nice=os.getpriority(os.PRIO_PROCESS, 0),
               utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
hashes[str(receipt_path.relative_to(V.ROOT))] = V.sha_file(receipt_path)
manifest.write_text(''.join(value + '  ' + path + '\n' for path, value in sorted(hashes.items())))
failures = [name for name, expected in hashes.items() if V.sha_file(V.ROOT / name) != expected]
assert not failures, failures
print(json.dumps(dict(status='PASS', files=len(hashes), source_inputs=len(initial['files']),
    changes=0, manifest_sha256=V.sha_file(manifest), report_sha256=V.sha_file(V.OUT / 'REVIEW.md'))))
