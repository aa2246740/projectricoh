#!/usr/bin/env python3
"""Check retained evidence, local report links and official firmware integrity."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
before = json.loads((HERE / 'firmware-hashes-before.json').read_text())
after = []
changed = []
for row in before['files']:
    p = ROOT / row['path']
    data = p.read_bytes()
    actual = dict(path=row['path'], size=len(data), sha256=hashlib.sha256(data).hexdigest())
    after.append(actual)
    if actual != row:
        changed.append(dict(before=row, after=actual))
now = datetime.now(timezone.utc).isoformat()
(HERE / 'firmware-hashes-after.json').write_text(json.dumps(dict(utc=now,files=after),indent=2)+'\n')
report = (HERE/'REPORT.md').read_text()
command_section = report.split('### 2.2 ',1)[1].split('### 2.3 ',1)[0]
documented = re.findall(r'^\| `(0x[0-9A-F]{4})` \|',command_section,re.M)
expected = [x['command'] for x in json.loads((HERE/'unit-commands.json').read_text())]
assert len(documented) == 44 and set(documented) == set(expected), (documented,expected)
result = dict(utc=now,official_files=len(after),unchanged=len(after)-len(changed),changed=changed)
(HERE/'firmware-integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
links = []
for target in re.findall(r'\]\(([^)]+)\)', report):
    if '://' not in target:
        p = (HERE / target.split('#',1)[0]).resolve()
        assert p.is_relative_to(HERE), target
        links.append(dict(target=target,exists=p.is_file()))
assert all(x['exists'] for x in links), [x for x in links if not x['exists']]
result.update(main_command_ids_documented=len(documented),report_local_links=len(links),all_report_links_exist=all(x['exists'] for x in links))
(HERE/'firmware-integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
assert not changed, changed
print(json.dumps(result,ensure_ascii=False))
