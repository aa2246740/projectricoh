"""Audit complete RPC records with the retained nine-row protocol checker."""
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
DAT = ROOT / 'firmware/package_v38_g138/SD_ROOT/GXRCE.DAT'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def has_stream(value):
    if isinstance(value, dict):
        return any(has_stream(item) for item in value.values())
    if isinstance(value, list):
        if value and all(isinstance(item, dict) and {'cmd', 'value', 'page', 'result', 't'} <= item.keys() for item in value):
            return True
        return any(has_stream(item) for item in value)
    return False


registry = {sha(DAT): DAT}
for folder in [OUT / 'local', OUT / 'legacy/local']:
    for path in folder.rglob('*'):
        if path.is_file() and path.suffix.upper() == '.DAT':
            registry[sha(path)] = path
groups = {}
missing = []
for path in (OUT / 'legacy/local/jobs').rglob('*.json'):
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or not has_stream(value):
        continue
    pin = value.get('dat_sha256') or value.get('artifact', {}).get('dat_sha256')
    if pin not in registry:
        missing.append(str(path.relative_to(ROOT)))
    else:
        groups.setdefault(pin, []).append(path)
assert not missing, missing
assert sha(DAT) in groups
source = ROOT / 'research/g122_keep_list/audit_records.py'
spec = importlib.util.spec_from_file_location('g138_rpc_auditor', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
results = []
for pin, paths in sorted(groups.items()):
    output = OUT / 'evidence' / ('rpc-' + pin[:12] + '.json')
    error = None
    try:
        module.main(registry[pin], paths, output, base=ROOT)
    except AssertionError as failure:
        error = repr(failure)
    value = json.loads(output.read_text())
    totals = Counter()
    for counts in value['unit_totals'].values():
        totals.update(counts)
    results.append(dict(dat_sha256=pin, status=value['status'], files=len(paths),
                        units=value['units'], totals=dict(totals), error=error,
                        evidence=str(output.relative_to(OUT))))
result = dict(status='PASS' if all(row['status'] == 'PASS' for row in results) else 'FAIL',
              dat_sha256=sha(DAT), auditor_sha256=sha(source), groups=results, missing=missing)
(OUT / 'evidence/rpc-summary.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
assert result['status'] == 'PASS', results
