"""Verify required results, freeze the final report, and verify every checksum."""
from pathlib import Path
import hashlib
import json
import re
import time
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(OUT))
import write_review


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    before = json.loads((OUT / 'protected-before.json').read_text())
    prefixes = ('firmware/engine_v38_ro/', 'firmware/package_v35_g117/', 'firmware/engine_v37/',
                'firmware/resident_v35/', 'firmware/image_v35/', 'tools/native_harness/',
                'artifacts/firmware/gxr-1.51/', 'artifacts/downloads/gxr-151.zip')
    selected = {name: digest for name, digest in before.items() if name.startswith(prefixes)}
    changed = [name for name, digest in selected.items() if not (ROOT / name).is_file() or sha(ROOT / name) != digest]
    assert len(selected) == 4737 and not changed, changed
    for name in ('GXRCE.DAT', 'engine.bin', 'reloc.bin', 'trust.bin'):
        assert (OUT / 'isolated/candidate/local/full-r13' / name).read_bytes() == (
            ROOT / 'firmware/engine_v38_ro/candidate/local/full-r13' / name).read_bytes()
    assert json.loads((OUT / 'differential-live-results.json').read_text())['cases'] == 72
    assert json.loads((OUT / 'empirical-rebind.json').read_text())['complete_payload_identical']
    assert json.loads((OUT / 'machine-gates.json').read_text())['status'] == 'PASS'
    official = json.loads((OUT / 'native/replay-results.json').read_text())
    assert len(official['cases']) == 29
    extra = (OUT / 'command-logs/extra-summary.stdout').read_text()
    assert extra.count('EXTRA stale generation=') == 72
    assert extra.count('OK independent-extra unit=') == 18
    assert 'Traceback' not in (OUT / 'command-logs/extra-summary.stderr').read_text()
    write_review.main()
    report = (OUT / 'REVIEW.md').read_text()
    assert report.startswith('不可以上卡。') and '__ACTUAL' not in report and '__HOST' not in report
    for label, target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', report):
        if target == 'SHA256SUMS':
            continue
        assert (OUT / target).is_file(), (label, target)
    (OUT / 'final-verification.json').write_text(json.dumps(dict(status='PASS_EVIDENCE_COMPLETE',
        current_input_files_rechecked=len(selected), changed_current_inputs=changed,
        required_host_phases=22, required_native_baseline_scenarios=20,
        current_native_scenarios=7, current_native_boots=9, official_machine_cases=29,
        differential_live_cases=72, independent_stale_matrix_cases=72,
        final_candidate_sha256=sha(ROOT / 'firmware/package_v35_g117/SD_ROOT/GXRCE.DAT'),
        report_sha256=sha(OUT / 'REVIEW.md'), verdict='不可以上卡',
        blocker='literal binary-freeze requirement not met; no demonstrated behavioral regression',
        hardware_access=False, card_access=False, flash=False, finalized_unix_time=time.time()),
        ensure_ascii=False, indent=2) + '\n')
    paths = []
    for p in sorted(OUT.rglob('*')):
        assert not p.is_symlink(), p
        if p.is_file() and p.name != 'SHA256SUMS':
            paths.append(p)
    # Nested historical SHA256SUMS are ordinary evidence and are included.
    for p in sorted(OUT.rglob('SHA256SUMS')):
        if p != OUT / 'SHA256SUMS':
            paths.append(p)
    paths = sorted(set(paths))
    lines = [sha(p) + '  ' + p.relative_to(OUT).as_posix() for p in paths]
    manifest = OUT / 'SHA256SUMS'
    manifest.write_text('\n'.join(lines) + '\n')
    for line in manifest.read_text().splitlines():
        digest, relative = line.split('  ', 1)
        assert not relative.startswith('/') and '..' not in Path(relative).parts
        assert sha(OUT / relative) == digest, relative
    print('PASS final evidence and relative SHA256SUMS:', len(lines), 'files')
    print('REVIEW.md sha256', sha(OUT / 'REVIEW.md'))
    print('SHA256SUMS sha256', sha(manifest))


if __name__ == '__main__':
    main()
