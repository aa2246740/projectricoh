"""Seal the task and all read-only repository inputs, then verify the seal."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import datetime
import json
import platform
import subprocess
import support as s


def r1_snapshot():
    expected = json.loads((s.LOCAL/'r1_snapshot.json').read_text())
    r1 = s.ROOT/'research/knobs_v2_r1'
    actual = {str(p.relative_to(s.ROOT)):s.sha(p) for p in sorted(r1.rglob('*')) if p.is_file()}
    assert expected == actual, 'read-only r1 snapshot changed'
    for line in (r1/'SHA256SUMS').read_text().splitlines():
        h, rel = line.split('  ', 1)
        assert s.sha(s.ROOT/rel) == h, 'r1 original manifest mismatch: '+rel
        if rel in expected:
            assert expected[rel] == h
        expected[rel] = h
    return expected


def inputs():
    result = r1_snapshot()
    for name in ('protected_inputs.json', 'model_inputs_calibration.json',
                 'model_inputs_verification.json', 'model_inputs_previews.json'):
        for rel, h in json.loads((s.LOCAL/name).read_text()).items():
            assert rel not in result or result[rel] == h, 'conflicting input hash'
            assert s.sha(s.ROOT/rel) == h, 'input changed: '+rel
            result[rel] = h
    return result


def check():
    manifest = s.HERE/'SHA256SUMS'
    recorded = {}
    for line in manifest.read_text().splitlines():
        h, rel = line.split('  ', 1)
        p = (s.ROOT/rel).resolve()
        assert p.is_relative_to(s.ROOT) and rel not in recorded
        assert p.is_file() and s.sha(p) == h, 'SHA256 mismatch: '+rel
        recorded[rel] = h
    outputs = {str(p.relative_to(s.ROOT)) for p in s.HERE.rglob('*') if p.is_file() and p != manifest}
    assert outputs.issubset(recorded), 'unsealed task outputs: '+str(outputs-set(recorded))
    assert all(p.suffix.upper() != '.DAT' for p in s.HERE.rglob('*') if p.is_file()), 'generated DAT'
    for rel, h in inputs().items():
        assert recorded[rel] == h
    verification = json.loads((s.LOCAL/'verification.json').read_text())
    calculation_sources = ('knobs.c', 'knobs.h', 'knobs.py', 'menu.c', 'menu.h', 'menu.py',
                           'checks.py', 'model_adapter.py', 'bridge.py', 'support.py', 'verify.py',
                           'test_goldens.py', 'test_sanitized.c', 'dump_tables.c',
                           'calibrate.py', 'cap_evidence.py', 'export_tables.py', 'comparisons.py', 'previews.py')
    for name in calculation_sources:
        p = s.HERE/'src'/name
        assert verification['source_sha256'][str(p.relative_to(s.ROOT))] == s.sha(p), 'verified source changed: '+name
    domain = json.loads((s.LOCAL/'domain_parity.json').read_text())
    assert domain['status'] == 'PASS'
    for rel, h in domain['source_sha256'].items():
        assert s.sha(s.ROOT/rel) == h, 'domain-parity source changed: '+rel
    roundtrip = json.loads((s.LOCAL/'header_roundtrip.json').read_text())
    assert roundtrip == json.loads((s.HERE/'tables/final.json').read_text())
    import export_tables
    assert export_tables.render(roundtrip) == (s.HERE/'tables/knobs_v2_r2_tables.h').read_text()
    with (s.LOCAL/'previews/index.csv').open() as f:
        import csv
        expected_pngs = {Path(r['path']).name for r in csv.DictReader(f)}
    assert expected_pngs == {p.name for p in (s.LOCAL/'previews').glob('*.png')}, 'unexpected/missing preview files'
    s.verify_inputs()
    print('PASS SHA256SUMS:', len(recorded), 'files;', len(outputs), 'task outputs; r1 unchanged; no generated DAT', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    s.guard()
    if args.check:
        check()
        return
    s.dependencies()
    import numpy, scipy, PIL
    s.dump(s.LOCAL/'environment.json', dict(python=sys.version, executable='/usr/bin/python3',
           platform=platform.platform(), numpy=numpy.__version__, scipy=scipy.__version__, pillow=PIL.__version__,
           compiler=subprocess.check_output(['/usr/bin/clang', '--version'], text=True),
           process_policy='run.py is serial; manual previews overlapped input recheck and domain parity; BLAS threads=1; compilation stages serial',
           output_fence=str(s.HERE), finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
           font_sha256=s.sha('/System/Library/Fonts/Supplemental/Songti.ttc')))
    actual_inputs = inputs()
    s.dump(s.LOCAL/'all_inputs.json', actual_inputs)
    import generate_report
    generate_report.main()
    sources = {str(p.relative_to(s.ROOT)):s.sha(p) for p in sorted((s.HERE/'src').glob('*')) if p.is_file()}
    s.dump(s.LOCAL/'algorithm_manifest.json', dict(schema='knobs-v2-r2/sealed-host/1', sources=sources,
           tables_sha256=s.sha(s.HERE/'tables/final.json'), header_sha256=s.sha(s.HERE/'tables/knobs_v2_r2_tables.h'),
           calibration_sha256=s.sha(s.LOCAL/'calibration.json'), verification_sha256=s.sha(s.LOCAL/'verification.json'),
           previews_sha256=s.sha(s.LOCAL/'preview_verification.json')))
    merged = dict(actual_inputs)
    merged.update({str(p.relative_to(s.ROOT)):s.sha(p) for p in sorted(s.HERE.rglob('*'))
                   if p.is_file() and p != s.HERE/'SHA256SUMS'})
    (s.HERE/'SHA256SUMS').write_text(''.join(f'{merged[rel]}  {rel}\n' for rel in sorted(merged)))
    check()


if __name__ == '__main__':
    main()
