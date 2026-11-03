"""Read back the final package and require every requested result."""
from pathlib import Path
import difflib
import json
import struct
import subprocess
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope


def read(path):
    return json.loads(Path(path).read_text())


def main():
    frozen = scope.freeze_check()
    root, here = scope.ROOT, scope.HERE
    engine = root / 'firmware/engine_diag_v21'
    package = root / 'firmware/package_v36_diag21'
    built = engine / 'candidate/local/full-r13'
    dat = package / 'local/SD_ROOT/GXRCE.DAT'
    raw = dat.read_bytes()
    assert len(raw) == 22020 and int.from_bytes(raw[28:32], 'big') == 132
    assert scope.sha(dat) == '097a178a936881583fee22b5c5dee54e15b3d27ad5bd11f147f5fea97bcab227'
    assert raw == (built / 'GXRCE.DAT').read_bytes()
    header = bytearray(raw[:256])
    expected = int.from_bytes(header[20:24], 'big')
    header[20:24] = bytes(4)
    assert zlib.crc32(header) == expected
    assert zlib.crc32(raw[256:]) == int.from_bytes(raw[24:28], 'big')
    offset, size = struct.unpack_from('>II', raw, 132)
    assert size == 12412 and raw[offset:offset + size] == (built / 'engine.bin').read_bytes()
    assert int.from_bytes(raw[116:120], 'big') == 26372
    files = sorted((package / 'local/SD_ROOT').iterdir())
    assert len(files) == 30 and all(p.is_file() for p in files)
    fixed = 0
    for p in files:
        if p.name != 'GXRCE.DAT':
            assert p.read_bytes() == (root / 'firmware/package_v36_g120b/SD_ROOT' / p.name).read_bytes()
            fixed += 1
    assert fixed == 29
    ignored = subprocess.check_output(['git', 'check-ignore', '--stdin'], cwd=root, text=True,
        input=''.join(str(p.relative_to(root)) + '\n' for p in files))
    assert len(ignored.splitlines()) == 30
    manifest = read(package / 'manifest.json')
    assert manifest['generation'] == 132 and len(manifest['files']) == 30
    for item in manifest['files']:
        p = package / 'local/SD_ROOT' / item['name']
        assert p.stat().st_size == item['bytes'] and scope.sha(p) == item['sha256']
    for line in (package / 'CARD_SHA256SUMS').read_text().splitlines():
        digest, path = line.split(None, 1)
        assert scope.sha(root / path) == digest

    heap = read(here / 'heap-tests-r2.json')
    assert heap['status'] == 'PASS' and heap['cases'] == 43
    assert heap['shape_checks'] == 138760 and heap['snapshot_bytes'] == 12460
    extra = read(here / 'raw-tests.json')
    assert extra['status'] == 'PASS' and extra['cases'] == 24
    model = read(here / 'raw-model.json')
    assert model['status'] == 'PASS' and len(model['cases']) == 9
    assert model['dat_sha256'] == scope.sha(dat)
    artifact = read(here / 'artifact-r2.json')
    assert artifact['status'] == 'PASS' and artifact['dat_sha256'] == scope.sha(dat)
    for unit in ('50mm', '28mm', 'mount'):
        item = read(here / ('artifact-r2-' + unit + '.json'))
        assert item['status'] == 'PASS' and len(item['events']) == 14
        for opening in (1, 2):
            events = [e for e in item['events'] if e['opening'] == opening]
            assert ''.join(e['actual_page'] for e in events) == 'ABCDFHA'
        for event in item['events']:
            assert event['actual_page'] == event['expected_page']
            assert len(event['rows']) == 8 and all(1 <= len(x) <= 8 for x in event['rows'])
            assert sum(x['entry'] == 'capture' for x in event['path']) == int(event['event'] == 'open')

    review = here / 'local/legacy/review'
    summary = read(review / 'evidence/summary.json')
    counts = dict(original_behavior_cases=411, error_cases=291,
        prepublication_and_reopen_cases=96, withdrawal_cases=72,
        lens_preservation_cases=3, first_service_failure_demonstrations=1,
        unique_case_records=874, setter_counterexample_cases=56,
        settings_value_change_cases=44, same_value_setter_cases=12)
    assert summary['dat_sha256'] == scope.sha(dat)
    for key, count in counts.items():
        assert summary[key] == count, key
    for key in ('positive_case_DAT_rpc8', 'positive_case_DAT_file_calls',
                'positive_case_DAT_queue2', 'positive_case_unapproved_DAT_stores'):
        assert summary[key] == 0, key
    matrix = read(review / 'evidence/matrix.json')
    assert matrix and all(x['returncode'] == 0 for x in matrix)
    jobs = read(here / 'review-extra-r2.json')
    assert jobs['status'] == 'PASS' and len(jobs['jobs']) == 14
    assert all(x['returncode'] == 0 for x in jobs['jobs'])
    static = read(review / 'evidence/static-audit.json')
    assert static['status'] == 'PASS_DAT_INTRINSIC_STATIC_BOUNDARY'
    assert static['dat_sha256'] == scope.sha(dat) and static['elf_sha256'] == scope.sha(built / 'engine.elf')
    assert static['dat_engine_elf_equal'] and static['no_direct_file_or_rpc_call']
    for name in ('matrix', 'rebuild', 'static_audit', 'summarize', 'seal'):
        assert read(here / 'local/suite-r2' / (name + '.json'))['returncode'] == 0, name
    assert read(review / 'evidence/rebuild.json')['status'] == 'PASS'
    comparisons = {}
    rebuilt = review / 'local/rebuild'
    for name in ('GXRCE.DAT', 'engine.bin', 'engine.elf', 'reloc.bin'):
        p = rebuilt / name if name == 'GXRCE.DAT' else rebuilt / 'candidate/local/product-r13/m32r-lto' / name
        assert p.read_bytes() == (built / name).read_bytes(), name
        comparisons[name] = scope.sha(p)
    archive = Path('candidate/local/resident/engine-services/libgxr_services.a')
    assert (rebuilt / archive).read_bytes() == (engine / archive).read_bytes()
    comparisons['service_archive'] = scope.sha(rebuilt / archive)

    c_review = here / 'local/review2'
    h = read(c_review / 'heap-results.json')
    assert h['cases'] == 169 and h['strict_change_rule'] == 'FAIL' and h['slot_range_rule'] == 'FAIL'
    for name in ('pages', 'baseline'):
        result = read(c_review / (name + '-results.json'))
        assert result['status'] == 'PASS' and len(result['units']) == 3
    result = read(c_review / 'capture-results.json')
    assert len(result['metrics']) == 15 and result['dat_sha256'] == scope.sha(dat)
    assert result['strict_change_rule'] == 'FAIL' and result['slot_range_rule'] == 'FAIL'
    assert result['write_guard'] == 'BSS_AND_STACK_ONLY'
    assert read(c_review / 'static-results.json')['status'] == 'PASS'
    import call
    call.prepare_review()
    parser = call.bridge_at().load_path(root / 'research/review_diag2/check_static.py')['elf']
    old_tables = parser(root / 'firmware/engine_diag_v2/candidate/local/full-r13/engine.elf')[3]
    new_tables = parser(built / 'engine.elf')[3]
    for name in ('diag_fields', 'diag_layout'):
        assert old_tables(name) == new_tables(name), name

    old = root / 'firmware/engine_diag_v2'
    changes, diff = [], []
    for p in sorted(engine.rglob('*')):
        rel = p.relative_to(engine)
        if not p.is_file() or {'local', '__pycache__'}.intersection(rel.parts):
            continue
        previous = old / rel
        assert previous.is_file(), str(rel)
        if p.read_bytes() == previous.read_bytes():
            continue
        changes.append(str(rel))
        diff.extend(difflib.unified_diff(previous.read_text().splitlines(True), p.read_text().splitlines(True),
            fromfile=str(previous.relative_to(root)), tofile=str(p.relative_to(root))))
    assert set(changes) == {'STATUS.txt', 'build_diag.py', 'candidate/common.py',
        'candidate/containers/product/diag.c', 'candidate/containers/product/diag_heap.h'}
    (here / 'source-v2.diff').write_text(''.join(diff))
    scope.save(here / 'verification.json', dict(status='PASS_HOST_READY_FOR_REVIEW', generation=132,
        dat_sha256=scope.sha(dat), dat_bytes=len(raw), code_bytes=size, bss_bytes=26372,
        snapshot_bytes=12460, main_request_bytes=55896, native_main_span=55908,
        source_changes=changes, frozen_inputs=frozen, frozen_inputs_unchanged=True,
        package_files=30, fixed_files_identical=29, heap_cases=43, raw_cases=24,
        raw_model_cases=9, shape_checks=138760, artifact_events=42, review2_heap_cases=169,
        review2_capture_cases=15, review_counts=counts, independent_rebuild=comparisons,
        P1_03='REQUIREMENT_CHANGED_BY_TASK_OWNER', P2_03='OPEN',
        camera='NOT_RUN', card='NOT_RUN', network='NOT_RUN', delegates=0))
    print('ACCEPT RETURN 0 ORIGINAL 411 REVIEW 874 RAW 24 MODEL 9')


if __name__ == '__main__':
    main()
