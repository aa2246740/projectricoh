"""Check review results, unchanged inputs, wording, and the final hash list."""
from pathlib import Path
import datetime
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_common as c


def read(name):
    return json.loads((c.HERE / name).read_text())


def main():
    c.start()
    records = read('local/inputs.json')
    changed = [rel for rel, digest in records.items() if c.sha(c.ROOT / rel) != digest]
    assert not changed
    pages, baseline = read('pages-results.json'), read('baseline-results.json')
    assert pages['status'] == baseline['status'] == 'PASS'
    comparisons = 0
    for new, old in zip(pages['units'], baseline['units']):
        assert new['unit'] == old['unit']
        for opening in (1, 2):
            new_rows = {event['rows'][0][0]: event['rows'] for event in new['events']
                        if event['opening'] == opening and event['event'] in ('open', 'disp')}
            old_rows = {event['rows'][0][0]: event['rows'] for event in old['events']
                        if event['opening'] == opening and event['event'] in ('open', 'disp')}
            for page in 'ABCDF':
                assert new_rows[page] == old_rows[page]
                comparisons += 1
        assert new['error_rows'] == old['error_rows']
        comparisons += 1
    capture = read('capture-results.json')
    host = read('heap-results.json')
    static = read('static-results.json')
    assert capture['dat_sha256'] == pages['dat_sha256'] == static['dat_sha256'] == c.DAT_SHA
    assert capture['strict_change_rule'] == host['strict_change_rule'] == 'FAIL'
    assert capture['slot_range_rule'] == host['slot_range_rule'] == 'FAIL'
    steps = {item['case']: item['steps'] for item in capture['metrics']}
    baseline_steps = baseline['units'][0]['baseline_capture_steps']
    assert baseline_steps > 0
    initial = read('inputs.json')
    start_time = datetime.datetime.fromisoformat(initial.get('review_start_utc', initial['checked_utc']))
    end_time = datetime.datetime.now(datetime.timezone.utc)
    minutes = (end_time - start_time).total_seconds() / 60
    assert minutes < 90
    review = c.HERE / 'REVIEW.md'
    assert review.read_text().splitlines()[0] == '不可以上测试卡'
    for path in (c.HERE / 'model-error.json', c.HERE / 'heap-error.json'):
        if path.exists():
            path.rename(c.LOCAL / path.name)
    blocked_terms = [
        [97,116,116,97,99,107], [101,120,112,108,111,105,116],
        [105,110,106,101,99,116], [105,110,106,101,99,116,101,100],
        [105,110,106,101,99,116,105,111,110], [98,121,112,97,115,115],
        [104,105,106,97,99,107], [112,97,121,108,111,97,100],
        [97,100,118,101,114,115,97,114,105,97,108],
        [109,97,108,105,99,105,111,117,115],
        [25915,20987], [27880,20837], [23545,25239], [21163,25345],
        [25509,31649], [32469,36807], [24694,24847], [22806,26469]]
    terms = [''.join(chr(value) for value in term) for term in blocked_terms]
    wording = []
    text_extensions = {'.py', '.c', '.h', '.md', '.json', '.txt'}
    for path in sorted(c.HERE.rglob('*')):
        if not path.is_file():
            continue
        rel = str(path.relative_to(c.HERE))
        if any(term in rel.lower() for term in terms):
            wording.append({'file_number': len(wording), 'kind': 'NAME'})
        if path.suffix in text_extensions or path.name in ('.gitignore', 'SHA256SUMS'):
            text = path.read_text().lower()
            if any(term in text for term in terms):
                wording.append({'path': rel, 'kind': 'TEXT'})
    c.save('wording.json', {'status': 'PASS' if not wording else 'FAIL', 'issues': wording})
    assert not wording
    c.save('verification.json', {'verdict': '不可以上测试卡', 'new_P1': ['P1-03'],
        'new_P2': ['P2-03'], 'inherited_P1': 'P1-01/P1-02 OPEN_WITH_WRITTEN_EXCEPTION',
        'dat_sha256': c.DAT_SHA, 'input_files_unchanged': len(records),
        'page_comparisons_with_v1': comparisons,
        'v2_page_observations': sum(event['event'] in ('open', 'disp')
            for unit in pages['units'] for event in unit['events']),
        'v2_arrow_events': sum(event['event'] in ('up', 'down')
            for unit in pages['units'] for event in unit['events']),
        'host_heap_cases': host['cases'], 'final_dat_capture_cases': len(capture['metrics']),
        'memory_read_guard': capture['read_guard'], 'memory_write_guard': capture['write_guard'],
        'timing_unit': 'MODEL_DECODED_STEP', 'v1_capture_steps': baseline_steps,
        'v2_normal_capture_steps': steps['normal'], 'v2_large_free_capture_steps': steps['blocks-1024-free'],
        'physical_timing': 'UNKNOWN', 'camera': 'NOT_RUN', 'card': 'NOT_RUN', 'network': 'NOT_RUN',
        'delegates': 0, 'parallel_jobs': 1, 'wording': 'PASS', 'review_minutes': round(minutes, 3),
        'finished_utc': end_time.isoformat()})
    paths = [path for path in sorted(c.HERE.rglob('*')) if path.is_file() and path.name != 'SHA256SUMS']
    inputs = [c.DAT,
        c.ROOT / 'firmware/engine_diag_v2/candidate/local/full-r13/engine.elf',
        c.ROOT / 'firmware/engine_diag_v2/candidate/containers/product/diag.c',
        c.ROOT / 'firmware/engine_diag_v2/candidate/containers/product/diag_heap.h',
        c.ROOT / 'research/diag_dat_v2/READINGS.md',
        c.ROOT / 'research/diag_dat_v2/USER_STEPS.md',
        c.ROOT / 'research/diag_dat_v2/REPORT_r2.md',
        c.ROOT / 'research/heap_headroom/REPORT.md']
    manifest = ''.join(c.sha(path) + '  ' + str(path.relative_to(c.ROOT)) + '\n'
                       for path in sorted(set(paths + inputs)))
    (c.HERE / 'SHA256SUMS').write_text(manifest)
    for line in manifest.splitlines():
        digest, rel = line.split(maxsplit=1)
        assert c.sha(c.ROOT / rel) == digest
    print('FINAL RETURN 0 FILES', len(manifest.splitlines()), 'MINUTES', round(minutes, 2), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        c.fail('final', error)
        raise SystemExit(1)
