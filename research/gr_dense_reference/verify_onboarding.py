#!/usr/bin/env python3
"""Reproduce r3s byte regressions, new-owner dry run and real-input refusals."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native as n
import owners
import instructions_r3
import argparse
import json
import subprocess
import time

DRY_OWNER = 'dryrun-not-for-delivery'
DRY_INPUTS = [
    'captures/contrib/2026-10-22-gr4hdf-screenchart/dng/1792597588000_R0003038.DNG',
    'captures/contrib/2026-10-22-gr4hdf-screenchart/dng/1792597571000_R0003037.DNG',
]


def command(owner, output, paths=()):
    return [sys.executable, '-I', '-B', str(n.HERE / 'onboard.py'), '--owner', owner,
            '--output', str(output), *(['--candidates', *paths] if paths else [])]


def build(owner, output, paths, logs):
    summary = output / 'onboarding-summary.json'
    if summary.exists():
        n.require(n.read(summary)['status'] == 'OFFLINE_READY',
                  f'incomplete output retained at {output}; choose a NEW --run-name')
        print(owner, 'verify completed output without rebuilding', flush=True)
        return
    log = n.output(logs / f'{owner}.log')
    with log.open('x') as handle:
        subprocess.run(command(owner, output, paths), cwd=n.ROOT, stdout=handle,
                       stderr=subprocess.STDOUT, check=True)
    print(owner, 'full onboarding completed', flush=True)


def regress(owner, output):
    entry = owners.get(owner)
    reference = owners.PRIVATE / owner / 'r3s_sparecard/SEND_r3s'
    regenerated = output / 'r3s_sparecard/SEND_r3s'
    rows = []
    for basename, expected in entry['regression_sha256'].items():
        relative = basename if basename.endswith('.txt') else 'DCIM/100RICOH/' + basename
        before, after = reference / relative, regenerated / relative
        actual = n.sha(after)
        byte_equal = before.read_bytes() == after.read_bytes()
        n.require(n.sha(before) == expected == actual and byte_equal,
                  f'byte regression: {owner}/{basename}: expected={expected}, regenerated={actual}')
        rows.append(dict(owner=owner, file=basename, expected_sha256=expected,
                         regenerated_sha256=actual, byte_identical=True, expected_source='user-supplied'))
    before, after = reference / 'SHA256SUMS', regenerated / 'SHA256SUMS'
    n.require(before.read_bytes() == after.read_bytes(), 'canonical SHA256SUMS differs')
    rows.append(dict(owner=owner, file='SHA256SUMS', expected_sha256=n.sha(before),
                     regenerated_sha256=n.sha(after), byte_identical=True, expected_source='canonical file'))
    return rows


def refusal(name, paths, logs, message):
    before = n.sha(owners.REGISTRY)
    result = subprocess.run(command(name, owners.PRIVATE / name, paths), cwd=n.ROOT,
                            capture_output=True, text=True)
    n.dump(logs / f'{name}.json', dict(command=result.args, exit_code=result.returncode,
                                    stdout=result.stdout, stderr=result.stderr))
    n.require(result.returncode == 2 and message in result.stderr,
              f'wrong refusal for {name}: exit={result.returncode}, {result.stderr}')
    n.require(before == n.sha(owners.REGISTRY) and not (owners.PRIVATE / name).exists(),
              'refused candidate registered or generated owner artifacts')
    return dict(name=name, passed=True, exit_code=result.returncode,
                messages=[line for line in result.stderr.splitlines() if line.startswith('REFUSED')])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true', help='build missing outputs; never overwrite')
    parser.add_argument('--run-name', default='r3s_regen', help='new per-owner regression subdirectory')
    parser.add_argument('--evidence', type=Path, required=True, help='NEW directory under local/private')
    args = parser.parse_args()
    started = time.monotonic()
    n.preflight()
    evidence = owners.private_path(args.evidence)
    evidence.mkdir(parents=True, exist_ok=False)
    regressions = {owner: owners.PRIVATE / owner / args.run_name
                   for owner, entry in owners.load().items() if entry.get('regression_sha256')}
    n.require(regressions and all(Path(args.run_name).name == args.run_name for _ in regressions),
              '--run-name must be a single directory name')
    if args.build:
        for owner, output in regressions.items():
            build(owner, output, [], evidence)
        build(DRY_OWNER, owners.PRIVATE / DRY_OWNER, DRY_INPUTS, evidence)
    rows = []
    for owner, output in regressions.items():
        rows.extend(regress(owner, output))
    dry = n.read(owners.PRIVATE / DRY_OWNER / 'onboarding-summary.json')
    n.require(dry['status'] == 'OFFLINE_READY' and dry['selected_template']['path'] == DRY_INPUTS[0] and
              dry['selected_template']['iso'] == 200 and dry['high_iso_warning'] and
              dry['input_hashes_unchanged'] and dry['gates']['content_identities'] == 15 and
              dry['gates']['readback_negative_checks'] == 11 and not dry['gates']['filename_used'],
              'new-owner dry run differs from acceptance criteria')
    handout = instructions_r3.text(DRY_OWNER)
    n.require(instructions_r3.DEFAULT_CONTROL_ZH in handout and instructions_r3.DEFAULT_CONTROL_EN in handout
              and 'R09000' not in handout and 'old R090' not in handout, 'new-owner handout defaults differ')
    dry_root = owners.PRIVATE / DRY_OWNER
    import report_r3
    deliveries = {}
    for owner, output in {**regressions, DRY_OWNER: dry_root}.items():
        owners.set_root(owner, output)
        n.SCRATCH = evidence / 'unzip-work'
        deliveries[owner] = report_r3.verify_delivery(owner)
        n.require(deliveries[owner]['zip_member_count'] == 11, 'wrong zip member count')
    negatives = [refusal('refused-mixed-body', [DRY_INPUTS[0], owners.get('gr4')['template']['path']],
                        evidence, 'different camera body'),
                 refusal('refused-not-griv', ['captures/contrib/2026-10-21-evalsets/1/GR_III/bastibe_same_scene/Target.DNG'],
                         evidence, 'not a GR IV')]
    result = dict(schema='gr-dense-onboarding-verification/1', passed=True, regressions=rows,
                  dry_run=dry, deliveries=deliveries, negative_tests=negatives,
                  runtime_seconds=round(time.monotonic()-started, 3), camera_acceptance=False)
    n.dump(evidence / 'verification.json', result)
    table = ['| Owner | File | Expected SHA-256 | Regenerated SHA-256 | Bytes |',
             '|---|---|---|---|---|']
    for row in rows:
        table.append(f'| {row["owner"]} | {row["file"]} | `{row["expected_sha256"]}` | '
                     f'`{row["regenerated_sha256"]}` | identical |')
    n.output(evidence / 'REGRESSION.md').write_text('\n'.join(table) + '\n')
    print(f'PASS: {len(rows)} byte-exact regression files; dry-run G1-G4/readback/ZIP; '
          f'{len(negatives)} actual-input refusals. Evidence: {evidence}', flush=True)


if __name__ == '__main__':
    main()
