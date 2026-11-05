"""Freeze existing inputs and copy only g156 source. No firmware generation."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
assert not C.ENGINE.exists(), 'prepare is a one-time source copy'
files=[]
for root in (C.BASE,C.BODY/'resident'):
    for p in sorted(root.rglob('*')):
        if not p.is_file() or {'local','__pycache__'}&set(p.relative_to(root).parts): continue
        raw=p.read_bytes(); rel=p.relative_to(C.ROOT)
        dest=C.LOCAL/'inputs'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        files.append(dict(path=str(rel),bytes=len(raw),sha256=C.sha(raw)))
        if root==C.BASE:
            target=C.ENGINE/p.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
paths=[C.ROOT/p for p in (
    'research/g156_field_issues_r1/REPORT.md','research/g156_field_issues_r1/local/G157_DESIGN.md',
    'research/g156_field_issues_r1/local/g157-selection-plan.json','research/library_28mm_r1/REPORT.md',
    'research/library_28mm_r1/local/g157_handoff.json','research/library_28mm_r1/local/final_verification.json',
    'firmware/package_v310_g156/GXRCE.DAT','firmware/package_v310_g156_test/GXRCE.DAT',
    'firmware/package_v310_g155c/GXRCE.DAT','firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT',
    'firmware/resident_v310_g155/local/resident/trust.json')]
for build in ('boot-on','boot-off'):
    paths += [C.BASE/'candidate/local'/build/n for n in ('engine.elf','layout.json')]
handoff=json.loads((C.ROOT/'research/library_28mm_r1/local/g157_handoff.json').read_text())
paths += [Path(r['record_file']) for r in handoff['profiles'] if r['accepted']]
for p in paths:
    raw=p.read_bytes();rel=p.relative_to(C.ROOT)
    dest=C.LOCAL/'inputs'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    files.append(dict(path=str(rel),bytes=len(raw),sha256=C.sha(raw)))
(C.ENGINE/'.gitignore').write_text('local/\n**/local/\ncandidate/\n')
for package in C.PACKAGES.values():
    package.mkdir(parents=True,exist_ok=True)
    (package/'.gitignore').write_text('local/\n')
C.save(C.LOCAL/'frozen.json',dict(start_utc='2026-11-04T07:33:00Z',deadline_utc='2026-11-04T13:33:00Z',files=files))
print('frozen',len(files))
