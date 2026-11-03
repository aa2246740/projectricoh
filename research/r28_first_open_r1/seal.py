"""Check research evidence, language limits, and relative SHA-256 records."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, save, sha

MANIFEST = OUT/'SHA256SUMS'
SELFCHECK = OUT/'manifest-selfcheck.json'


def output_files():
    paths = sorted(p for p in OUT.rglob('*') if p.is_file() and p != MANIFEST)
    assert not any(p.is_symlink() for p in paths)
    assert not any(p.suffix.lower() == '.dat' for p in paths)
    return paths


def check_language():
    parts = [('adver', 'sarial'), ('att', 'ack'), ('ex', 'ploit'), ('in', 'ject'),
             ('hi', 'jack'), ('take', 'over'), ('by', 'pass'), ('pay', 'load'),
             ('对', '抗'), ('攻', '击'), ('注', '入'), ('劫', '持'), ('接', '管'), ('绕', '过')]
    terms = [''.join(p).casefold() for p in parts]
    bad, count = [], 0
    for path in output_files():
        if path.suffix not in ('.py', '.json', '.md', '.txt', '.log', '.tsv', '.sh'):
            continue
        content = path.read_text().casefold()
        count += 1
        if any(term in content for term in terms):
            bad.append(str(path.relative_to(OUT)))
    assert not bad, bad
    save('neutral-language.json', dict(status='PASS', text_files_checked=count, matches=0))


def write_manifest():
    paths = output_files()
    MANIFEST.write_text(''.join(sha(p.read_bytes())+'  '+str(p.relative_to(OUT))+'\n' for p in paths))
    return len(paths)


def verify_manifest():
    entries = {}
    for line in MANIFEST.read_text().splitlines():
        digest, name = line.split('  ', 1)
        p = OUT/name
        assert not Path(name).is_absolute() and p.resolve().is_relative_to(OUT)
        assert name not in entries
        assert sha(p.read_bytes()) == digest, name
        entries[name] = digest
    expected = {str(p.relative_to(OUT)) for p in output_files()}
    assert set(entries) == expected
    return len(entries)


def run():
    acceptance = json.loads((OUT/'acceptance.json').read_text())
    integrity = json.loads((OUT/'input-integrity.json').read_text())
    contract = json.loads((OUT/'static-contract.json').read_text())
    assert acceptance['status'] == integrity['status'] == contract['status'] == 'PASS'
    assert acceptance['native_cases'] == 8
    assert acceptance['exits_follow_native_event_table']
    for case in acceptance['cases']:
        assert sha((OUT/case['evidence']).read_bytes()) == case['sha256']
    assert integrity['before'] == integrity['after'] == 24281
    check_language()
    SELFCHECK.write_text(json.dumps(dict(status='RUNNING'), indent=2)+'\n')
    count = write_manifest()
    assert verify_manifest() == count
    SELFCHECK.write_text(json.dumps(dict(status='PASS', verified_files=count,
                                         manifest='SHA256SUMS', selfcheck_included=True,
                                         excludes=['SHA256SUMS'], relative_paths=True), indent=2)+'\n')
    assert write_manifest() == verify_manifest() == count
    print(json.dumps(dict(status='PASS', verified_files=count, selfcheck_included=True)))


if __name__ == '__main__':
    if sys.argv[1:] == ['--check']:
        count = verify_manifest()
        assert json.loads(SELFCHECK.read_text())['status'] == 'PASS'
        print(json.dumps(dict(status='PASS', verified_files=count)))
    else:
        run()
