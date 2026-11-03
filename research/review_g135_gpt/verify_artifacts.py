from pathlib import Path
import collections
import hashlib
import json
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


report = {'status': 'PASS', 'checks': {}}
sample_file = OUT / 'evidence/sample300.json'
if sample_file.exists():
    summary = json.loads(sample_file.read_text())
    rows = [json.loads(line) for line in (OUT / 'evidence/sample300-cases.jsonl').read_text().splitlines()]
    assert summary['status'] == 'PASS' and summary['cases'] == len(rows) == 300
    assert len({(row['unit'], row['sample']) for row in rows}) == 300
    assert dict(collections.Counter(row['unit'] for row in rows)) == {'50mm': 100, '28mm': 100, 'mount': 100}
    assert len({(row['unit'], row['slot']) for row in rows}) == 24
    assert sum(row['steps'] for row in rows) == summary['instruction_steps']
    folder = OUT / 'local/jobs/sample300-final'
    binary = (folder / 'comparison.bin').read_bytes()
    assert len(binary) == 300 * 1132
    for index, row in enumerate(rows):
        record = binary[1132 * index:1132 * (index + 1)]
        unit, slot, *values = struct.unpack_from('>II10h', record)
        expected, observed = record[28:580], record[580:1132]
        assert ['50mm', '28mm', 'mount'][unit] == row['unit']
        assert slot == row['slot'] and values == row['values']
        assert expected == observed and len(observed) == row['bytes_compared'] == 552
        assert sha(expected) == row['expected_sha256'] == row['observed_sha256']
        assert row['status'] == 0 and row['steps'] > 0
    identities = list((folder / 'oracle/local/r2-reference').glob('identity-*.json'))
    assert len(identities) == 1
    reference = json.loads(identities[0].read_text())
    for name, expected in reference['sources'].items():
        assert sha((ROOT / 'research/knobs_v2_r2/src' / name).read_bytes()) == expected
    report['checks']['reference_identity'] = reference
    report['checks']['sample300'] = {'cases': 300, 'bytes_compared': 165600, 'binary_sha256': sha(binary), 'binary_path': str((folder / 'comparison.bin').relative_to(ROOT)), 'dat_sha256': summary['dat_sha256'], 'steps': summary['instruction_steps']}
else:
    report['status'] = 'INCOMPLETE'
    report['checks']['sample300'] = 'no complete 300-case artifact'

for name in ['static-review', 'layout-current', 'windows', 'boundary-sweep', 'reference-paths']:
    path = OUT / 'evidence' / (name + '.json')
    if path.exists():
        data = json.loads(path.read_text())
        assert data['status'] in ['PASS', 'PASS_STATIC']
        report['checks'][name] = {'status': data['status'], 'sha256': sha(path.read_bytes())}
    else:
        report['status'] = 'INCOMPLETE'
        report['checks'][name] = 'missing'

bindings = []
for path in (OUT / 'local/jobs').rglob('binding-*.json'):
    data = json.loads(path.read_text())
    assert data.get('generation') == 135
    assert data.get('dat_sha256') == '57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a'
    assert data.get('unscoped_integer_constants_replaced') == 0
    bindings.append(str(path.relative_to(ROOT)))
report['checks']['bindings'] = {'count': len(bindings), 'unscoped_integer_changes': 0}

binary_paths = [path for path in OUT.rglob('*') if path.is_file() and path.suffix in {'.DAT', '.bin', '.o', '.elf', '.dylib'}]
assert all(path.relative_to(OUT).parts[0] == 'local' for path in binary_paths)
paths = '\n'.join(str(path.relative_to(ROOT)) for path in binary_paths) + '\n'
checked = subprocess.run(['git', 'check-ignore', '--stdin'], input=paths, text=True, capture_output=True, cwd=str(ROOT))
assert checked.returncode == 0
assert len(checked.stdout.splitlines()) == len(binary_paths)
assert not list(OUT.rglob('*.pyc'))
report['checks']['local_binary_files'] = len(binary_paths)
report['checks']['new_python_bytecode_files'] = 0
(OUT / 'evidence/artifact-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'checks': list(report['checks']), 'binding_files': len(bindings)}))
