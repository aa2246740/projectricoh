"""Check final identities, original suites, memory sizes and package files."""
from pathlib import Path
import json
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_call
import scope


def read(path):
    return json.loads(Path(path).read_text())


def main():
    sys.addaudithook(legacy_call.fence)
    frozen = scope.freeze_check()
    before = read(scope.HERE/'inputs-r2-before.json')
    retained = ('artifact-failure.json', 'verification.json', 'heap-tests.json',
                'inputs-before.json', 'reproduction-r2.json')
    for name in retained:
        key = 'research/diag_dat_v2/'+name
        if key in before:
            assert scope.sha(scope.HERE/name) == before[key]['sha256']
    engine = scope.ROOT/'firmware/engine_diag_v2'
    for key, value in before.items():
        if key.startswith('firmware/engine_diag_v2/') and '/local/' not in key:
            assert scope.sha(scope.ROOT/key) == value['sha256']
    package = scope.ROOT/'firmware/package_v36_diag2'
    dat = package/'local/SD_ROOT/GXRCE.DAT'
    raw = dat.read_bytes()
    assert scope.sha(dat) == 'ef39f71b9e8df800cffd7998474668f992534e71807e55a92f2146c375f0ede4'
    assert len(raw) == 21588 and int.from_bytes(raw[28:32], 'big') == 128
    header = bytearray(raw[:256])
    expected = int.from_bytes(header[20:24], 'big')
    header[20:24] = bytes(4)
    assert zlib.crc32(header) == expected
    assert zlib.crc32(raw[256:]) == int.from_bytes(raw[24:28], 'big')
    built = engine/'candidate/local/full-r13'
    assert raw == (built/'GXRCE.DAT').read_bytes()
    offset, size = struct.unpack_from('>II', raw, 132)
    assert raw[offset:offset+size] == (built/'engine.bin').read_bytes()
    bss = int.from_bytes(raw[116:120], 'big')
    assert size == 11980 and bss == 26316
    identity = dict(generation=128, dat_bytes=len(raw), dat_sha256=scope.sha(dat),
                    elf_sha256=scope.sha(built/'engine.elf'), code_bytes=size,
                    bss_bytes=bss, main_request_bytes=1104+((len(raw)+bss+3)&~3)+6144+256)
    assert identity['main_request_bytes'] == 55408
    original_identity = read(scope.HERE/'artifact-failure.json')
    for key, expected in identity.items():
        assert original_identity[key] == expected
    reproduction = read(scope.HERE/'reproduction-r2.json')
    assert reproduction['status'] == 'REPRODUCED'
    assert ''.join(event['expected_page'] for event in reproduction['events']) == 'ABCDFHA'
    assert ''.join(event['actual_page'] for event in reproduction['events']) == 'ABCDFAB'
    assert reproduction['events'][5]['rows'] == original_identity['observed_rows']
    assert len(list((package/'local/SD_ROOT').iterdir())) == 30
    fixed = 0
    for path in (package/'local/SD_ROOT').iterdir():
        assert path.is_file()
        if path.name != 'GXRCE.DAT':
            base = scope.ROOT/'firmware/package_v36_g120b/SD_ROOT'/path.name
            assert path.read_bytes() == base.read_bytes()
            fixed += 1
    assert fixed == 29
    manifest = read(package/'manifest.json')
    assert len(manifest['files']) == 30
    for item in manifest['files']:
        path = package/'local/SD_ROOT'/item['name']
        assert path.stat().st_size == item['bytes'] and scope.sha(path) == item['sha256']
    for line in (package/'CARD_SHA256SUMS').read_text().splitlines():
        expected, name = line.split(None, 1)
        assert scope.sha(scope.ROOT/name) == expected
    artifact = read(scope.HERE/'artifact-r2.json')
    assert artifact['status'] == 'PASS' and artifact['dat_sha256'] == identity['dat_sha256']
    for unit in ('50mm', '28mm', 'mount'):
        result = read(scope.HERE/('artifact-r2-'+unit+'.json'))
        assert result['status'] == 'PASS' and len(result['events']) == 14
        for event in result['events']:
            assert event['actual_page'] == event['expected_page']
            assert len(event['rows']) == 8 and all(0 < len(row) <= 8 for row in event['rows'])
            opening = event['event'] == 'open'
            assert sum(item['entry'] == 'capture' for item in event['path']) == int(opening)
    heap = read(scope.HERE/'heap-tests-r2.json')
    assert heap['status'] == 'PASS' and heap['cases'] == 43 and heap['shape_checks'] == 138760
    assert heap['snapshot_bytes'] == 12432
    review = scope.HERE/'local/legacy/review'
    summary = read(review/'evidence/summary.json')
    assert summary['dat_sha256'] == identity['dat_sha256']
    expected_counts = dict(original_behavior_cases=411, error_cases=291,
        prepublication_and_reopen_cases=96, withdrawal_cases=72,
        lens_preservation_cases=3, first_service_failure_demonstrations=1,
        unique_case_records=874, setter_counterexample_cases=56,
        settings_value_change_cases=44, same_value_setter_cases=12)
    for key, expected in expected_counts.items():
        assert summary[key] == expected, (key, summary[key], expected)
    for key in ('positive_case_DAT_rpc8', 'positive_case_DAT_file_calls',
                'positive_case_DAT_queue2', 'positive_case_unapproved_DAT_stores'):
        assert summary[key] == 0
    matrix = read(review/'evidence/matrix.json')
    assert matrix and all(item['returncode'] == 0 for item in matrix)
    extra = read(scope.HERE/'review-extra-r2.json')
    assert extra['status'] == 'PASS' and len(extra['jobs']) == 14
    assert extra['dat_sha256'] == identity['dat_sha256']
    assert all(item['returncode'] == 0 for item in extra['jobs'])
    static = read(review/'evidence/static-audit.json')
    assert static['status'] == 'PASS_DAT_INTRINSIC_STATIC_BOUNDARY'
    assert static['dat_sha256'] == identity['dat_sha256']
    assert static['elf_sha256'] == identity['elf_sha256']
    assert static['dat_engine_elf_equal'] and static['no_direct_file_or_rpc_call']
    for name in ('matrix', 'rebuild', 'static_audit', 'summarize', 'seal'):
        assert read(scope.HERE/'local/suite-r2'/(name+'.json'))['returncode'] == 0
    assert read(review/'evidence/rebuild.json')['status'] == 'PASS'
    rebuilt = review/'local/rebuild'
    comparisons = {}
    for name in ('GXRCE.DAT', 'engine.bin', 'engine.elf', 'reloc.bin'):
        path = rebuilt/name if name == 'GXRCE.DAT' else rebuilt/'candidate/local/product-r13/m32r-lto'/name
        assert path.read_bytes() == (built/name).read_bytes()
        comparisons[name] = scope.sha(path)
    archive = Path('candidate/local/resident/engine-services/libgxr_services.a')
    assert (review/'local/rebuild'/archive).read_bytes() == (engine/archive).read_bytes()
    comparisons['service_archive'] = scope.sha(review/'local/rebuild'/archive)
    scope.save(scope.HERE/'verification-r2.json', dict(status='PASS_HOST_READY_FOR_REVIEW',
        root_cause='TEST_ADAPTER', product_source_unchanged=True, identity=identity,
        frozen_inputs=frozen, frozen_inputs_unchanged=True, package_files=30,
        fixed_files_identical=fixed, artifact_events=42, synthetic_heap_cases=43,
        format_checks=138760, review_counts=expected_counts,
        independent_rebuild=comparisons, inherited_P1='OPEN_UNCHANGED',
        camera='NOT_RUN', card='NOT_RUN', network='NOT_RUN', delegates=0))
    print('ACCEPT_R2 RETURN 0 COUNT 874')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        frames = []
        tb = error.__traceback__
        while tb:
            frames.append(dict(file=Path(tb.tb_frame.f_code.co_filename).name,
                               function=tb.tb_frame.f_code.co_name, line=tb.tb_lineno))
            tb = tb.tb_next
        scope.save(scope.HERE/'accept-error-r2.json', dict(type=type(error).__name__, frames=frames,
                                                       message=str(error)[:500]))
        print('ACCEPT_R2 RETURN 1 COUNT 0 TYPE', type(error).__name__)
        raise SystemExit(1)
