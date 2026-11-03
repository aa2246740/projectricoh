"""Check the research evidence, protected inputs, vocabulary and root-relative sums."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect

TERMS = ['at'+'tack', 'ex'+'ploit', 'in'+'ject', 'by'+'pass', 'hi'+'jack',
         'pay'+'load', 'adver'+'sarial', 'mali'+'cious',
         '攻'+'击', '注'+'入', '对'+'抗', '劫'+'持', '接'+'管', '绕'+'过', '恶'+'意']


def outputs():
    return sorted(p for p in HERE.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')


def evidence():
    collect.preflight()
    before = json.loads((collect.OUT/'protected-before.json').read_text())
    assert before == collect.protected(), 'protected inputs changed'
    refs = json.loads((collect.OUT/'reference-inputs.json').read_text())
    for rel, entry in refs.items():
        p = collect.ROOT/rel
        assert p.stat().st_size == entry['size'] and collect.sha(p) == entry['sha256'], rel
    facts = json.loads((collect.OUT/'facts.json').read_text())
    assert facts['elf_engine_dat_equal'] and all(r['equal'] for r in facts['resident_sections'])
    assert len(facts['windows']) == 30
    for row in facts['windows']:
        assert collect.sha(collect.OUT/(row['label']+'.bin')) == row['sha256']
        assert all(x['changed_bytes']==0 for x in row['body_comparison'].values())
    replay = json.loads((collect.OUT/'replay-results.json').read_text())
    slots = json.loads((collect.OUT/'my-slot-mapping.json').read_text())
    for result in (replay, slots):
        assert result['status'] == 'PASS_FUNCTION_REPLAY' and result['original_sha256'] == collect.EXPECTED
        assert result['library_sha256'] == collect.sha(collect.ROOT/'tools/gxr_emulator/build/libgxr_m32r.dylib')
        for rel, digest in result['source_hashes'].items():
            assert collect.sha(collect.ROOT/rel) == digest, rel
    assert len(replay['cases']) == 18 and replay['original_type_getter']['constant_return'] == 1
    alternate = [r for r in replay['cases'] if r['case']=='native_packed_parameter_restore' and not r['actual_body_case']]
    assert len(alternate) == 2
    assert [r['target'] for r in slots['results']] == [1,2,3]
    for row in slots['results']:
        assert row['writes'] == 288 and not row['tail_touched']
        assert {int(m['record_offset'],16) for m in row['mapping']} == set(range(256,544))
    scan = json.loads((collect.OUT/'scan-summary.json').read_text())
    assert scan['source_sha256'] == collect.sha(HERE/'scan.py')
    assert scan['verified_bytes'] == 3858192
    assert json.loads((collect.OUT/'scope-check.json').read_text())['outside_write_denied']
    report = (HERE/'REPORT.md').read_text()
    assert report.splitlines()[0] == '部分可行'
    files = outputs()
    for p in files:
        assert not p.is_symlink()
        assert not any(term in p.name.lower() for term in TERMS), str(p)
        if p.suffix != '.bin':
            text = p.read_text().lower()
            matches = [i for i, term in enumerate(TERMS) if term in text]
            assert not matches, (str(p.relative_to(HERE)), matches)
    raw_files = [str(p.relative_to(collect.ROOT)) for p in files if p.suffix=='.bin' or p.name.endswith('.asm.txt')]
    assert all('/local/' in p for p in raw_files)
    ignored = subprocess.run(['git','check-ignore','--stdin'], input='\n'.join(raw_files)+'\n',
                             cwd=collect.ROOT, text=True, capture_output=True, check=True)
    assert set(ignored.stdout.splitlines()) == set(raw_files)
    assert not (collect.ROOT/'.persist-recipe-scope-check').exists()
    return dict(protected=before, references=refs, output_files=files,
                alternate_cases=len(alternate), raw_files=len(raw_files))


def check_sums():
    lines = (HERE/'SHA256SUMS').read_text().splitlines()
    seen = set()
    for line in lines:
        digest, rel = line.split('  ',1)
        assert len(digest)==64 and rel not in seen and not rel.startswith('/')
        p = (collect.ROOT/rel).resolve()
        p.relative_to(collect.ROOT)
        assert collect.sha(p) == digest, rel
        seen.add(rel)
    return len(lines)


def seal(state):
    now = datetime.datetime.now(datetime.timezone.utc)
    start = datetime.datetime(2026,10,30,0,37,28,tzinfo=datetime.timezone.utc)
    elapsed = (now-start).total_seconds()
    assert 0 <= elapsed <= 9000, 'timebox exceeded'
    collect.save('validation.json', dict(status='PASS_RESEARCH_ARTIFACT',
        timestamp=now.isoformat(), started=start.isoformat(), elapsed_seconds=elapsed,
        timebox_seconds=9000, protected_files=len(state['protected']),
        reference_files=len(state['references']), windows=30, function_cases=18,
        alternate_type_cases=state['alternate_cases'], my_import_runs=9,
        ignored_raw_files=state['raw_files'], vocabulary_ok=True,
        output_scope='research/persist_recipe',
        verify_source_sha256=collect.sha(HERE/'verify.py'),
        prior_tool_diagnostic='local/my-slot-failure.json is superseded by local/my-slot-mapping.json',
        limits='Research artifact checks only. No whole-camera persistence or device acceptance.'))
    files = {collect.ROOT/rel for rel in state['protected'].keys() | state['references'].keys()}
    files.update(outputs())
    sums = ''.join(collect.sha(p)+'  '+str(p.relative_to(collect.ROOT))+'\n' for p in sorted(files))
    (HERE/'SHA256SUMS').write_text(sums)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=('seal','check'))
    a = ap.parse_args()
    state = evidence()
    if a.action == 'seal':
        seal(state)
    else:
        validation = json.loads((collect.OUT/'validation.json').read_text())
        assert validation['status']=='PASS_RESEARCH_ARTIFACT'
        assert validation['verify_source_sha256']==collect.sha(HERE/'verify.py')
    count = check_sums()
    print(json.dumps(dict(status='PASS_RESEARCH_ARTIFACT', sums=count,
                          protected_files=len(state['protected']), references=len(state['references']),
                          original_function_cases=18, my_import_runs=9,
                          device_acceptance='NOT_STARTED')))


if __name__ == '__main__':
    main()
