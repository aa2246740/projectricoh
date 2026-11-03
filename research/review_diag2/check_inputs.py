"""Read the submitted identities and retain a hash-only input record."""
from pathlib import Path
import datetime
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_common as c


def main():
    c.start()
    records = {}
    sums = c.ROOT / 'research/diag_dat_v2/SHA256SUMS'
    mismatches = []
    count = 0
    for line in sums.read_text().splitlines():
        digest, rel = line.split(maxsplit=1)
        rel = rel.lstrip('* ')
        path = c.ROOT / rel
        actual = c.sha(path)
        count += 1
        if actual != digest:
            mismatches.append(rel)
        records[rel] = actual
    assert count == 1788 and not mismatches
    manifest = json.loads((c.ROOT / 'firmware/package_v36_diag2/manifest.json').read_text())
    package = c.DAT.parent
    baseline = c.ROOT / 'firmware/package_v36_g120b/local/SD_ROOT'
    if not baseline.is_dir():
        baseline = c.ROOT / 'firmware/package_v36_g120b/SD_ROOT'
    fixed = 0
    for item in manifest['files']:
        path = package / item['name']
        assert path.stat().st_size == item['bytes'] and c.sha(path) == item['sha256']
        records[str(path.relative_to(c.ROOT))] = item['sha256']
        if item['name'] != 'GXRCE.DAT':
            assert c.sha(baseline / item['name']) == item['sha256']
            fixed += 1
    assert len(list(package.iterdir())) == 30 and fixed == 29
    first = c.ROOT / 'firmware/engine_diag_v1'
    second = c.ROOT / 'firmware/engine_diag_v2'
    def source_tree(base):
        return {str(path.relative_to(base)): path for path in base.rglob('*')
                if path.is_file() and not {'local', '__pycache__'}.intersection(path.relative_to(base).parts)}
    a, b = source_tree(first), source_tree(second)
    changes = []
    for rel in sorted(a.keys() | b.keys()):
        av = c.sha(a[rel]) if rel in a else None
        bv = c.sha(b[rel]) if rel in b else None
        if av != bv:
            changes.append({'path': rel, 'v1': av, 'v2': bv})
        for tree in (a, b):
            if rel in tree:
                records[str(tree[rel].relative_to(c.ROOT))] = c.sha(tree[rel])
    for base in ('research/diag_dat_v2', 'research/heap_headroom'):
        for path in (c.ROOT / base).rglob('*'):
            if path.is_file() and 'local' not in path.relative_to(c.ROOT / base).parts:
                records[str(path.relative_to(c.ROOT))] = c.sha(path)
    raw = c.DAT.read_bytes()
    code_at = int.from_bytes(raw[132:136], 'big')
    code_bytes = int.from_bytes(raw[136:140], 'big')
    engine = c.ROOT / 'firmware/engine_diag_v2/candidate/local/full-r13/engine.bin'
    assert raw[code_at:code_at + code_bytes] == engine.read_bytes()
    old = c.ROOT / 'firmware/package_v36_diag1/local/SD_ROOT/GXRCE.DAT'
    assert c.sha(old) == '38e3db6eacaf05a4ad8dbafbda608e3b5695485110014f7816f32d315b3f49a1'
    c.save('local/inputs.json', records)
    c.save('inputs.json', {'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'review_start_utc': sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'sum_entries': count, 'sum_mismatches': mismatches, 'package_files': 30,
        'fixed_files_identical': fixed, 'generation': int.from_bytes(raw[28:32], 'big'),
        'dat_bytes': len(raw), 'dat_sha256': c.sha(c.DAT), 'engine_bytes': code_bytes,
        'engine_matches_dat': True, 'source_changes': changes, 'frozen_files': len(records)})
    print('INPUTS RETURN 0 COUNT', count, 'FIXED', fixed, flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        c.fail('inputs', error)
        raise SystemExit(1)
