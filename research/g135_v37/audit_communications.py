#!/usr/bin/python3
"""Review complete communication records against their exact DAT."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g135_v37'
RUNS = WORK / 'local/checks'
DAT = ROOT / 'firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def streams(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from streams(item)
    elif isinstance(value, list):
        if value and all(isinstance(item, dict) and {'cmd', 'value', 'page', 'result', 't'} <= item.keys() for item in value):
            yield value
        else:
            for item in value:
                yield from streams(item)

def main():
    registry = {sha(DAT): DAT}
    for path in RUNS.rglob('*'):
        if path.is_file() and path.suffix.upper() == '.DAT':
            registry[sha(path)] = path
    groups = {}
    missing = []
    record_count = 0
    group_records = {}
    for path in RUNS.rglob('*.json'):
        if path.name.startswith(('binding-', 'result-')):
            continue
        try:
            value = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(value, dict):
            continue
        records = list(streams(value))
        if not records:
            continue
        pin = value.get('dat_sha256') or value.get('artifact', {}).get('dat_sha256')
        if pin not in registry:
            missing.append(str(path.relative_to(ROOT)))
            continue
        groups.setdefault(pin, []).append(path)
        count = sum(len(record) for record in records)
        record_count += count
        group_records[pin] = group_records.get(pin, 0) + count
    assert not missing, missing
    results = []
    for pin, paths in groups.items():
        output = WORK / 'evidence' / ('rpc-' + pin[:12] + '.json')
        command = ['/usr/bin/python3', '-I', '-B', str(ROOT / 'research/g122_keep_list/audit_records.py'), '--dat', str(registry[pin]), '--records', *map(str, paths), '--output', str(output), '--base-dir', str(ROOT)]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=3600)
        results.append(dict(dat_sha256=pin, files=len(paths), complete_records=group_records[pin], returncode=completed.returncode, output=str(output.relative_to(ROOT))))
    assert groups and sha(DAT) in groups
    result = dict(dat_sha256=sha(DAT), groups=results, complete_records=record_count, final_dat_records=group_records[sha(DAT)], missing=missing, status='PASS' if all(row['returncode'] == 0 for row in results) else 'FAIL')
    (WORK / 'evidence/rpc-summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(name='communication-review', returncode=int(result['status'] != 'PASS'), counts=dict(groups=len(results), files=sum(row['files'] for row in results), records=record_count))))
    assert result['status'] == 'PASS'

if __name__ == '__main__':
    main()
