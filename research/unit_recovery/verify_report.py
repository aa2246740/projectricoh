#!/usr/bin/env python3
"""Verify this research artifact and input identity without camera interaction."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import runpy

HERE=Path(__file__).resolve().parent
M=runpy.run_path(str(HERE/'inspect.py'))
report=(HERE/'REPORT.md').read_text()
assert report.startswith('PARTIAL '), 'Verdict must be first'

broken=[]
for target in re.findall(r'\]\(([^)]+)\)',report):
    if target.startswith(('https://','http://','#')):
        continue
    p=(HERE/target).resolve()
    assert p.is_relative_to(M['ROOT']), 'Report link outside project'
    if not p.exists(): broken.append(target)
assert not broken, broken

untagged=[]
in_code=False
for i,line in enumerate(report.splitlines(),1):
    if line.startswith('```'):
        in_code=not in_code
        continue
    if in_code or not line.strip() or line.startswith(('#','|','PARTIAL ')):
        continue
    if not re.match(r'^(?:\d+\. )?【(?:静态确认|推断|未知)',line):
        untagged.append(i)
assert not untagged, untagged

before=json.loads((HERE/'official-before.json').read_text())
after=json.loads((HERE/'official-after.json').read_text())
assert after['all_unchanged'] and len(after['files'])==len(before['files'])==30
for row in after['files']:
    b=(M['ROOT']/row['path']).read_bytes()
    assert hashlib.sha256(b).hexdigest()==row['sha256']

manual=json.loads((HERE/'manual-hashes.json').read_text())
p=M['SCRATCH']/'gxr_fwup_en.pdf'
b=p.read_bytes()
manual.update(sha256_after=hashlib.sha256(b).hexdigest(),size_after=len(b),
              unchanged=(hashlib.sha256(b).hexdigest()==manual['sha256_before'] and len(b)==manual['size']),
              verified_utc=datetime.now(timezone.utc).isoformat())
assert manual['unchanged']
M['save']('manual-hashes.json',manual)

headers=json.loads((HERE/'a12-header-summary.json').read_text())
assert len(headers)==4 and all(x['checksum_matches'] for x in headers)
assert len(list((HERE/'evidence').glob('*.txt')))==14
for p in HERE.glob('*.py'):
    compile(p.read_text(),str(p),'exec')

result=dict(utc=datetime.now(timezone.utc).isoformat(),verdict='PARTIAL',
    official_files_unchanged='30/30',manual_unchanged=True,a12_weighted_checksums='4/4',
    report_links_valid=True,claim_labels_checked=True,evidence_excerpt_count=14,
    python_syntax_valid=True,
    limitations='Artifact and byte checks only. No camera, boot, flashing, or recovery execution.')
M['save']('verification.json',result)
print(json.dumps(result,ensure_ascii=False,indent=2))
