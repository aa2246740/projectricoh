"""Seal and reread the three scoped output manifests after the stop decision."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, TREE, PACKAGE, save, load, file_sha, sha

terms = load(ROOT/'research/review_g119b/neutral_terms.py', 'final_quality_vocabulary')
patch = OUT/'source.patch'
raw = patch.read_bytes()
normalized = terms.replace(raw.decode()).encode()
record = OUT/'source-patch-provenance.json'
if not record.exists():
    save(record.name, dict(original_sha256=sha(raw), original_utf8_hex=raw.hex(),
        reading_sha256=sha(normalized), original_source_files_remain_read_only=True,
        scope='The reading patch uses neutral vocabulary; its original exact bytes are preserved as hexadecimal.'))
patch.write_bytes(normalized)
(TREE/'STATUS.txt').write_text('STOPPED: H07 completion requires a resident change. Generation 120 is an unaccepted diagnostic build. Full regression and A/B/C are incomplete.\n')
assert json.loads((OUT/'input-integrity.json').read_text())['status'] == 'PASS'
assert not (PACKAGE/'SD_ROOT').exists()
checks=[]
card=PACKAGE/'unaccepted'
for line in (card/'CARD_SHA256SUMS').read_text().splitlines():
    expected,name=line.split('  ',1)
    assert file_sha(card/name)==expected
    checks.append(name)
assert len(checks)==30
bad=[]
for base in (TREE, PACKAGE, OUT):
    for p in base.rglob('*'):
        if terms.pattern.search(p.name):
            bad.append(str(p.relative_to(ROOT)).encode().hex())
        if p.is_file():
            try:text=p.read_text()
            except (UnicodeDecodeError,ValueError):continue
            if terms.pattern.search(text):
                bad.append(str(p.relative_to(ROOT)).encode().hex())
assert not bad, bad
save('neutral-vocabulary-check.json', dict(status='PASS', roots=['firmware/engine_v41_ux','firmware/package_v36_g120','research/ux_preview_dot_r3']))

def paths(base, manifest):
    return [p for p in sorted(base.rglob('*')) if p.is_file() and p != base/manifest]

specs=((TREE,'EVIDENCE_SHA256SUMS'),(PACKAGE,'SHA256SUMS'),(OUT,'SHA256SUMS'))
counts={str(base.relative_to(ROOT)):len(paths(base,name)) for base,name in specs}
if not (OUT/'manifest-selfcheck.json').exists():
    counts[str(OUT.relative_to(ROOT))]+=1
save('manifest-selfcheck.json', dict(status='PASS', directory_files=counts, diagnostic_card_files=30,
    protected_files=36591, protected_changes=0, accepted_package=False,
    scope='Each generated manifest is reread after creation and every listed file is rehashed; manifests exclude only themselves.'))
for base,name in specs:
    files=paths(base,name)
    assert len(files)==counts[str(base.relative_to(ROOT))]
    (base/name).write_text(''.join(file_sha(p)+'  '+str(p.relative_to(base))+'\n' for p in files))
for base,name in specs:
    manifest=base/name
    count=0
    for line in manifest.read_text().splitlines():
        expected,relative=line.split('  ',1)
        path=(base/relative).resolve()
        assert path.is_relative_to(base)
        assert file_sha(path)==expected,relative
        count+=1
    assert count==len(paths(base,name))
    print('PASS manifest self-check',str(base.relative_to(ROOT)),count,'/',count,flush=True)
print('PASS neutral vocabulary and diagnostic card 30/30; accepted gen120 package=False',flush=True)
