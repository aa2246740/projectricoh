#!/usr/bin/python3 -I -B
"""Check design records and pixel oracles; never execute v4 product code."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DESIGN = HERE.parent / 'DESIGN.md'
sys.path.insert(0, str(HERE))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def base_records():
    return json.loads((HERE.parent/'r4/complete-records.json').read_text())


def fixture_checks(write=False):
    sys.path.insert(0,str(HERE.parent/'r4'))
    from record_check import run_checks
    return run_checks(write=write)


def pixel_checks():
    stride = 8576
    pattern = bytes(((x*37) ^ (x >> 8) ^ 19) & 255 for x in range(stride))
    def image(height, source):
        return b''.join(source[(y*17) % stride:] + source[:(y*17) % stride]
                        for y in range(height))
    before = image(2848, pattern)
    unchanged = before
    partial = bytearray(before)
    partial[632*stride+11] ^= 1
    refusal_ok = lambda old, new: len(old) == len(new) and old == new
    assert refusal_ok(before, unchanged)
    assert not refusal_ok(before, partial)
    bands = {2848: ((0, 632), (2216, 2848)),
             2416: ((0, 416), (2000, 2416))}
    for height, ranges in bands.items():
        source = image(height, pattern)
        output = bytearray(source)
        for start, end in ranges:
            output[start*stride:end*stride] = b'\x00\x00\x80\x80' * ((end-start)*stride//4)
        lo, hi = ranges[0][1], ranges[1][0]
        assert output[lo*stride:hi*stride] == source[lo*stride:hi*stride]
        assert len(output) == height*stride
        for start, end in ranges:
            assert output[start*stride:end*stride] == b'\x00\x00\x80\x80' * ((end-start)*stride//4)
    guard = bytes([0xa5]) * (432*stride)
    short_source = image(2416, pattern)
    wrong = bytearray(short_source + guard)
    for start, end in bands[2848]:
        wrong[start*stride:end*stride] = b'\x00\x00\x80\x80' * ((end-start)*stride//4)
    assert wrong[len(short_source):] != guard
    assert len(wrong)-len(short_source) == 3704832
    first = bytes(v ^ 0xa7 for v in pattern)
    first_image = image(2848, first)
    full_expected = b''.join(first_image[y*stride+2144:y*stride+6432]
                             + before[y*stride+2144:y*stride+6432]
                             for y in range(2848))
    assert len(full_expected) == len(before)
    wrong_row_order = full_expected[stride:] + full_expected[:stride]
    assert wrong_row_order != full_expected
    expected_row = first[2144:6432] + pattern[2144:6432]
    forward = bytearray(pattern)
    for n in range(4288):
        forward[4288+n] = forward[2144+n]
    forward[:4288] = first[2144:6432]
    assert bytes(forward) != expected_row
    right_to_left = bytearray(pattern)
    for n in range(4287, -1, -1):
        right_to_left[4288+n] = right_to_left[2144+n]
    right_to_left[:4288] = first[2144:6432]
    assert bytes(right_to_left) == expected_row
    return dict(classification='independent_pixel_oracle_sensitivity',
                refusal_equal_accepted=True, one_changed_byte_rejected=True,
                xpan_heights=[2848, 2416], wrong_2848_bounds_on_2416_rejected=True,
                outside_rows=432, outside_bytes=3704832,
                wrong_overlap_direction_rejected=True, correct_overlap_direction_accepted=True,
                wrong_vertical_order_rejected=True,
                product_h42_exits_executed=0, thumbnails_or_jpeg_encoded=0)


def frozen_checks():
    r4=HERE.parent/'r4'
    receipt=json.loads((r4/'input-receipt.json').read_text())
    changed=[r['path'] for r in receipt['frozen'] if digest(ROOT/r['path'])!=r['sha256']]
    assert not changed,changed
    mutable={'research/body_v4_design/DESIGN.md'}
    mutable.update('research/body_v4_design/r3/'+name for name in
                   ('diag_gate.py','spec_check.py','diag-fixtures.json','spec-results.json',
                    'verification.json','closure-map.json'))
    legacy={r['path']:r for r in receipt['source_entries'] if r['status']=='not_read_by_user_rule'}
    unchanged=0
    for row in receipt['source_entries']:
        name=row['path']
        if name in legacy:
            stat=(ROOT/name).stat()
            assert stat.st_size==row['size'] and stat.st_mtime_ns==row['mtime_ns'],name
        elif name not in mutable:
            assert digest(ROOT/name)==row['expected'],name
            unchanged+=1
    assert digest(HERE.parent/'DESIGN_r3.md')==receipt['input_design_sha256']
    assert digest(HERE.parent/'DESIGN_r2.md')=='5fc89fa03a23ca8957ea93098188023cc18b7b620de12d4f2d69ed0b1fb0749a'
    old={r['path']:r['expected'] for r in receipt['source_entries']}
    for path in (r4/'before').iterdir():
        assert digest(path)==old['research/body_v4_design/r3/'+path.name],path.name
    return dict(frozen_count=len(receipt['frozen']),changed=[],unchanged_source_files=unchanged,
                r2_copy_exact=True,r3_copy_exact=True,old_files_not_read=sorted(legacy),
                declared_source_change_paths=sorted(mutable))


def document_checks():
    text = DESIGN.read_text()
    assert text.splitlines()[0] == '可以评审'
    assert '## §R3 复审修改' in text
    assert '## §R4 复审修改' in text
    assert '## 给用户的大白话' in text
    for key in ('P1-01', 'P1-02', 'P1-03', 'P1-04', 'P1-05', '严格链接', '108,112', '108,064',
                '107,612', '1,584', '3,704,832', '0x201F813C', '552 B', '7,902'):
        assert key in text, key
    paths = re.findall(r'\]\(([^)]+)\)', text)
    for link in paths:
        if '://' not in link:
            assert (DESIGN.parent/link.split('#', 1)[0]).exists(), link
    banned_english = ['att'+'ack', 'ex'+'ploit', 'in'+'ject', 'by'+'pass',
                      'hi'+'jack', 'pay'+'load', 'adver'+'sarial', 'mali'+'cious']
    banned_chinese = ['注'+'入', '绕'+'过', '旁'+'路', '攻'+'击', '劫'+'持',
                      '接'+'管', '恶'+'意', '外'+'来', '对'+'抗']
    targets = [DESIGN] + [p for directory in (HERE,HERE.parent/'r4') for p in directory.rglob('*') if p.is_file()]
    hits = []
    for path in targets:
        content = path.read_text()
        if path.name == 'input-SHA256SUMS-r2':
            continue
        for word in banned_english:
            if re.search(r'\b'+word, content, re.I):
                hits.append((str(path.relative_to(ROOT)), word))
        for word in banned_chinese:
            if word in content:
                hits.append((str(path.relative_to(ROOT)), word))
    assert not hits, hits
    return dict(first_line=text.splitlines()[0], links_checked=len(paths), neutral_word_hits=0)


def manifest_checks():
    receipt = json.loads((HERE.parent/'r4/input-receipt.json').read_text())
    skipped = {r['path']: r['expected'] for r in receipt['source_entries']
               if r['status'] == 'not_read_by_user_rule'}
    rows = (HERE.parent/'SHA256SUMS').read_text().splitlines()
    names = []
    for row in rows:
        expected, name = row.split(None, 1)
        name = name.lstrip('*')
        assert name not in names
        assert (ROOT/name).resolve().is_relative_to(HERE.parent.resolve())
        names.append(name)
        if name in skipped:
            assert expected == skipped[name]
        else:
            assert digest(ROOT/name) == expected, name
    actual = {str(p.relative_to(ROOT)) for p in HERE.parent.rglob('*')
              if p.is_file() and p.name != 'SHA256SUMS'}
    assert set(names) == actual, (set(names)-actual, actual-set(names))
    return dict(entries=len(rows), hashed=len(rows)-len(skipped), carried_without_read=len(skipped))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--write-evidence', action='store_true')
    args = parser.parse_args()
    assert args.check != args.write_evidence
    for directory in (HERE,HERE.parent/'r4'):
        for path in directory.glob('*.py'):
            compile(path.read_text(),str(path),'exec')
    records = fixture_checks(write=args.write_evidence)
    pixels = pixel_checks()
    frozen = frozen_checks()
    native = json.loads((HERE/'native-heap.json').read_text())
    budget = json.loads((HERE/'layout-budget.json').read_text())
    assert native['source_sha256'] == digest(HERE/'native_heap_replay.py')
    assert budget['compile']['source_sha256'] == digest(HERE/'layout_probe.c')
    assert budget['checker_sha256'] == digest(HERE/'layout_check.py')
    assert native['short_tail_example']['actual_spans'] == [644, 108100]
    assert native['short_tail_example']['total_span'] == 108744
    assert budget['parent']['default_request_cap'] == 108064
    if args.write_evidence:
        (HERE/'diag-fixtures.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n')
        (HERE/'spec-results.json').write_text(json.dumps(dict(records=records, pixels=pixels),
                                                        ensure_ascii=False, indent=2)+'\n')
        # The delivery references this file while document links are checked.
        (HERE/'verification.json').write_text('{}\n')
    cli=json.loads((HERE.parent/'r4/cli-results.json').read_text())
    assert cli['checker_sha256']==digest(HERE/'diag_gate.py')
    assert cli['runner_sha256']==digest(HERE.parent/'r4/cli_check.py')
    assert cli['all_passed'] is True and len(cli['cases'])==20
    assert cli['profile_sha256']==(HERE.parent/'r4/reference-profile.sha256').read_text().strip()
    reviewed=json.loads((ROOT/'research/review_v4_design_r2/record-variants.json').read_text())['variants'][1:]
    expected_names={'complete','complete_interleaved','wrong_reference_hash','duplicate_json_member',
                    'nonfinite_json_number','truncated_json','missing_file','fixture_profile_for_device_record'}
    expected_names.update(prefix+case['name'] for prefix in ('original_','rebased_') for case in reviewed)
    assert {row['name'] for row in cli['cases']}==expected_names
    for row in cli['cases']:
        complete=row['name'] in ('complete','complete_interleaved')
        assert row['exitcode']==(0 if complete else 2)
        assert row['record_stage']==('records_complete_for_offline_review' if complete else 'undetermined')
    for name in ('before-failures.json','before-rebased-failures.json'):
        before=json.loads((HERE.parent/'r4'/name).read_text())
        assert before['checker_sha256']==digest(HERE.parent/'r4/before/diag_gate.py')
        assert before['runner_sha256']==digest(HERE.parent/'r4/reproduce_review.py')
        assert before['reviewed_inputs_sha256']==digest(ROOT/'research/review_v4_design_r2/record-variants.json')
        assert set(before['failed_cases'])=={row['name'] for row in reviewed}
        assert len(before['failed_cases'])==6
        if name=='before-rebased-failures.json':
            assert before['complete_records_sha256']==digest(HERE.parent/'r4/complete-records.json')
            assert before['base_stage']=='records_complete_for_offline_review'
    docs = document_checks()
    verification = dict(classification='design_r4_local_checks_only', frozen=frozen, document=docs,
                        design_sha256=digest(DESIGN),
                        spec_checker_sha256=digest(Path(__file__)),
                        record_checker_sha256=digest(HERE/'diag_gate.py'),
                        record_cases_rejected=records['record_cases_rejected'],
                        record_case_counts=records['counts'],positive_records=len(records['positive_cases']),
                        record_detail_sha256=records['detail_sha256'],
                        cli_results_sha256=digest(HERE.parent/'r4/cli-results.json'),
                        complete_record_fixture_accepted=True, pixel_oracle=pixels,
                        native_replay_sha256=digest(HERE/'native-heap.json'),
                        layout_budget_sha256=digest(HERE/'layout-budget.json'),
                        final_window_linked=False, final_extension_linked=False,
                        final_diag_linked=False, g0_passed=False,
                        device_or_card_access=False, network_used=False,
                        product_code_changed=False, new_recovery_boot_runs=0)
    if args.write_evidence:
        (HERE/'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2)+'\n')
    else:
        saved = json.loads((HERE/'verification.json').read_text())
        assert saved == verification
        verification['manifest'] = manifest_checks()
    print(json.dumps(dict(design=docs['first_line'], frozen_files=frozen['frozen_count'],
                          invalid_record_cases_rejected=records['record_cases_rejected'],
                        record_case_counts=records['counts'],positive_records=len(records['positive_cases']),
                        record_detail_sha256=records['detail_sha256'],
                        cli_results_sha256=digest(HERE.parent/'r4/cli-results.json'),
                          pixel_oracle_sensitive=True, g0_passed=False,
                          manifest=verification.get('manifest')), ensure_ascii=False))


if __name__ == '__main__':
    main()
