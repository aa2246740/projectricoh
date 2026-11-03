"""Verify the final artifacts and the executed g153 repair evidence."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIX = HERE / 'review_fix'
ENGINE = ROOT / 'firmware/engine_v62_g153'
sys.path.insert(0, str(HERE))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    from dat_format import sections, strict_effects, expand, expand_effect, u32
    delivery = read(HERE / 'evidence/p1-import.json')
    for name, digest in read(FIX / 'evidence/test-source-bindings.json').items():
        assert sha(ROOT / name) == digest, name
    assert (HERE / 'review_fix_checks.py').read_bytes() == (ROOT / 'research/looks_g152/review_fix_checks.py').read_bytes()
    assert (HERE / 'review_fix_photo_v3.py').read_bytes() == (ROOT / 'research/looks_g152/review_fix_photo_v3.py').read_bytes()
    original = (HERE / 'unverified_checks.py').read_text()
    assertion = "assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\\x01'"
    assert original.count(assertion) == 1
    assert (HERE / 'review_fix_unverified.py').read_text() == original.replace(
        assertion, "assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\\x00'")
    review_copies = {}
    for copy in sorted((FIX / 'legacy').glob('after-refusal-*')):
        source = ROOT / 'research/review_g152/runtime/evidence' / copy.name
        assert copy.read_bytes() == source.read_bytes(), copy.name
        review_copies[copy.name] = sha(copy)
    assert review_copies
    assert (FIX / 'legacy/independent_cases.py').read_bytes() == (ROOT / 'research/review_g152/independent_cases.py').read_bytes()
    for manifest in delivery['input_manifests'][:1]:
        path = ROOT / manifest['path']
        assert sha(path) == manifest['sha256']
        rows = path.read_text().splitlines()
        assert len(rows) == manifest['verified'] == 840
        for row in rows:
            digest, name = row.split('  ', 1)
            assert sha(ROOT / name) == digest, name
    core = 'candidate/containers/product/src/firmware/engine/core/eng_core.c'
    assert sha(ENGINE / core) == delivery['core_sha256']
    assert (ENGINE / core).read_bytes() == (ROOT / 'firmware/engine_v60_g152' / core).read_bytes()
    selected_sources = {str(path.relative_to(ENGINE)) for path in ENGINE.rglob('*')
                        if path.is_file() and 'local' not in path.relative_to(ENGINE).parts}
    assert selected_sources == set(delivery['prior_source_hashes'])
    changed = [name for name, digest in delivery['prior_source_hashes'].items()
               if sha(ENGINE / name) != digest]
    assert changed == ['candidate/containers/product/looks_data.py', core], changed
    unchanged = []
    for name, digest in delivery['body_and_service_inputs_before'].items():
        if name.endswith('/GXRCE.DAT'):
            continue
        assert sha(ROOT / name) == digest, name
        unchanged.append(name)
    resident = load(ROOT / 'firmware/resident_v39/resident/build.py', 'g153_fix_identity')
    resident.HERE = HERE / 'local/body/resident'
    resident.SERVICES = HERE / 'local/body/engine_services'
    trust = read(HERE / 'local/body/local/resident/trust.json')
    assert resident.build_identity().hex() == trust['resident_build_id']
    assert resident.abi_identity().hex() == trust['resident_abi_id']
    image = load(ROOT / 'research/body_v39/build_image.py', 'g153_fix_official')
    image.WORK = HERE
    _, official = image.official_files()
    packages = {}
    for name, users in (('package_v39_g153', 0), ('package_v39_g153_test', 3)):
        path = ROOT / 'firmware' / name
        raw = (path / 'local/SD_ROOT/GXRCE.DAT').read_bytes()
        sections(raw)
        effects = strict_effects(raw)
        assert effects['capacity'] == effects['count'] == 10
        assert tuple(effects['capacities']) == (8, 28, 32, 32)
        assert tuple(effects['used']) == (0, 10, 9, 10) and effects['bytes'] == 6636
        assert raw[80:112].hex() == trust['resident_build_id']
        assert raw[212:228].hex() == trust['resident_abi_id']
        assert u32(raw, 28) == 153
        manifest = read(path / 'MANIFEST.json')
        assert manifest['users'] == users and manifest['dat_sha256'] == sha(path / 'SD_ROOT/GXRCE.DAT')
        assert manifest['body_sha256'] == sha(path / 'SD_ROOT/ilaunch3') == '8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d'
        companions = 0
        for filename, data in official.items():
            if filename != 'ilaunch3':
                assert (path / 'SD_ROOT' / filename).read_bytes() == data
                companions += 1
        assert companions == 28
        for row in (path / 'SHA256SUMS').read_text().splitlines():
            digest, filename = row.split('  ', 1)
            assert sha(ROOT / filename) == digest, filename
        old = (HERE / 'local/initial-g153' / ('GXRCE-test.DAT' if users else 'engine/candidate/local/full-r13/GXRCE.DAT')).read_bytes()
        for effect in range(10):
            assert expand_effect(raw, effect) == expand_effect(old, effect)
        for unit in range(3):
            for slot in range(1, 9):
                assert expand(raw, unit, slot) == expand(old, unit, slot)
        old_at, new_at = u32(old, 204), u32(raw, 204)
        assert raw[new_at+3392:new_at+3392+7904] == old[old_at+3392:old_at+3392+7904]
        assert raw[new_at+1408:new_at+1408+1984] == old[old_at+1408:old_at+1408+1984]
        packages[name] = dict(sha256=manifest['dat_sha256'], bytes=len(raw), users=users,
                              effects=effects, official_companions=companions)
    size = read(HERE / 'evidence/build-size.json')
    assert size['main_request'] == 107072 and size['main_headroom'] == 540
    assert size['file_bytes'] == 90164 and size['file_headroom'] == 7628
    assert size['code_bytes'] == 65268 and size['bss_bytes'] == 9280
    runner = load(HERE / 'review_fix_run.py', 'g153_fix_plan')
    receipts, events, applications = [], [], []
    current = packages['package_v39_g153_test']['sha256']
    for phase, jobs in runner.PHASES.items():
        state = read(FIX / 'evidence' / ('phase-' + phase + '.json'))
        assert state['status'] == 'PASS'
        last_end = 0
        for batch in state['batches']:
            assert len(batch) <= 2 and min(row['started_ns'] for row in batch) >= last_end
            last_end = max(row['ended_ns'] for row in batch)
            assert all(row['returncode'] == 0 and row['wait_completed'] for row in batch)
        for name, script, arguments, timeout in jobs:
            receipt = read(HERE / 'evidence' / ('fix-' + name + '-receipt.json'))
            assert receipt['returncode'] == 0 and receipt['nice'] == 10
            assert receipt['arguments'] == arguments and receipt['timeout'] == timeout
            assert sha(HERE / script) == receipt['script_sha256']
            log = HERE / 'local' / ('fix-' + name + '.log')
            assert sha(log) == receipt['log_sha256']
            assert current in log.read_text(), name
            if script == 'apply_checks.py':
                observations = [json.loads(line.removeprefix('APPLY_RESULT '))
                                for line in log.read_text().splitlines() if line.startswith('APPLY_RESULT ')]
                assert len(observations) == 1
                observed = observations[0]
                assert observed['status'] == 'PASS' and observed['dat_sha256'] == current
                assert observed['native_UI_audit']['backend'] == 'tools/native_harness/python_backend.py'
                assert observed['native_UI_audit']['host_UI_writes'] == 0
                applications.append(dict(unit=observed['unit'], dat_sha256=current,
                                         native_UI_audit=observed['native_UI_audit'], status='PASS'))
            assert receipt['TMPDIR'].endswith('/jobs/p' + str(receipt['pid']))
            events += [(receipt['started_ns'], 1), (receipt['ended_ns'], -1)]
            receipts.append(receipt)
    running = maximum = 0
    for _, delta in sorted(events):
        running += delta
        maximum = max(maximum, running)
    assert running == 0 and maximum <= 2
    assert sorted(row['unit'] for row in applications) == ['28mm', '50mm', 'mount']
    selected_snapshots = [
        HERE / 'evidence/unverified-50mm-original-late.json',
        HERE / 'evidence/unverified-mount-original-late.json',
        HERE / 'evidence/t0-late-50mm.json', HERE / 'evidence/t0-late-mount.json',
        FIX / 'evidence/snapshot-race-mount-rows.json',
        FIX / 'evidence/snapshot-race-50mm-T.json',
        HERE / 'evidence/unverified-50mm-builtin-effect-capture-invalid-ok.json',
        HERE / 'evidence/unverified-mount-builtin-effect-restore-fail-ok.json',
    ]
    for path in selected_snapshots:
        row = read(path)
        assert row['status'] == 'PASS' and row['dat_sha256'] == current, path.name
    variants = []
    for name, count in (('effect-mount-state.json', 1), ('multiple-50mm-state.json', 3),
                        ('photo-final-mount.json', 1)):
        row = read(FIX / 'evidence' / name)
        assert row['status'] == 'PASS' and row['dat_sha256'] == current
        detail = row['detail']
        assert len(detail['changes']) == count
        assert not any(detail['S_stores_during_refusals'])
        for change in detail['changes']:
            for field in ('rows', 'T', 'S_sha256'):
                assert change['before'][field] == change['after'][field]
        if name.startswith('photo'):
            assert len(row['half_transitions']) == 2
            assert all(event['physical_state_unchanged'] and event['live_verified'] == 0
                       for event in row['half_transitions'])
        variants.append(dict(name=name, late_refusals=count, status='PASS'))
    regressions = []
    for unit, cases in (('50mm', ('cold-none', 'offer-ok', 't-boot', 'first-apply-readback')),
                        ('mount', ('offer-ok', 't-boot', 'dat-release-test', 'dat-test-release')),
                        ('28mm', ('cold-none',))):
        for case in cases:
            row = read(HERE / 'evidence' / f'reg-{unit}-{case}.json')
            assert row['status'] == 'PASS' and row['dat_identities'], (unit, case)
            assert row['dat_sha256'] in {package['sha256'] for package in packages.values()}
            regressions.append(dict(unit=unit, case=case, dat_identities=row['dat_identities'], status='PASS'))
    lifetime = []
    for unit in ('50mm', 'mount'):
        for slot in (4, 8):
            row = read(FIX / 'evidence' / f'after-refusal-{unit}-{slot}.json')
            assert row['status'] == 'PASS' and row['dat_sha256'] == current
            details = row['detail']
            assert details['matches']['actual_prior'] and not details['frame']['failed']
            assert [(call['op'], call['returned']) for call in details['calls']] == [(6, 0), (2, -2)]
            assert not details['S_stores']
            assert details['flags_after_first_exit']['live_verified'] == '00'
            prefix = HERE / 'local/review-fix-runtime/runtime/evidence' / f'after-refusal-{slot}-{unit}'
            for suffix, length in (('.bin', 505), ('-S.bin', 4096)):
                values = [Path(str(prefix) + '-' + state + suffix).read_bytes()
                          for state in ('before', 'after', 'reopened')]
                assert all(len(value) == length for value in values)
                assert values[0] == values[1] == values[2]
            lifetime.append(dict(unit=unit, actual_prior_slot=slot, complete_unit_bytes=505,
                                  complete_S_bytes=4096, status='PASS'))
    matrix = []
    for unit in ('50mm', 'mount'):
        summary = read(HERE / 'evidence' / ('lock-fix-' + unit + '.json'))
        assert summary['status'] == 'PASS' and summary['cases'] == 24 and summary['dat_sha256'] == current
        for transition in ('builtin-effect', 'effect-same-base', 'effect-other-base', 'effect-builtin'):
            for timing in ('held', 'race-at-s', 'transient'):
                for how in ('ok', 'half'):
                    row = read(HERE / 'evidence' / f'lock-fix-{unit}-{transition}-{timing}-{how}.json')
                    assert row['status'] == 'PASS' and row['dat_sha256'] == current
                    assert [call['op'] for call in row['key_calls']] == ([6, 2] if timing == 'race-at-s' else [6])
                    assert not row['key_S_stores']
                    for state in ('after_key', 'after_exit', 'after_reopen'):
                        for field in ('rows', 'T', 'S_sha256', 'ref_sha256'):
                            assert row['before'][field] == row[state][field]
        matrix.append(dict(unit=unit, cases=24, status='PASS'))
    result = dict(status='PASS', delivered_core_sha256=delivery['core_sha256'], engine_changes=changed,
                  unchanged_body_service_files=len(unchanged), resident_rebuilt=False,
                  body_sha256=sha(HERE / 'local/ilaunch3'), trust=trust, size=size, packages=packages,
                  original_review_evidence_copies=review_copies,
                  snapshot_results=[str(path.relative_to(HERE)) for path in selected_snapshots],
                  selected_regressions=regressions,
                  application_results=applications,
                  transaction_variants=variants,
                  lifetime=lifetime, matrix=matrix, foreground_jobs=len(receipts),
                  maximum_concurrent_jobs=maximum, all_jobs_nice=10,
                  test_wall_seconds=(max(row['ended_ns'] for row in receipts)-min(row['started_ns'] for row in receipts))/1e9,
                  job_seconds=sum(row['seconds'] for row in receipts))
    (FIX / 'evidence/audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'delivered_core_sha256',
                     'unchanged_body_service_files', 'resident_rebuilt', 'body_sha256',
                     'size', 'foreground_jobs', 'maximum_concurrent_jobs',
                     'all_jobs_nice', 'test_wall_seconds', 'job_seconds')}))


if __name__ == '__main__':
    main()
