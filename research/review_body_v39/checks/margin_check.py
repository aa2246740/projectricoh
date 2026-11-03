#!/usr/bin/python3 -I
"""Recheck the single linker margin at its pass/fail boundary."""
from pathlib import Path
import importlib.util
import json
import os
import sys

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
TEMP = Path(os.environ['REVIEW_TEMP'])
source = ROOT / 'firmware/resident_v39/resident/build.py'
rows = []
for margin, expected in ((44, True), (45, False), (177, False)):
    spec = importlib.util.spec_from_file_location('review_margin_' + str(margin), source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.LOCAL = TEMP / 'preflight'
    output = TEMP / str(margin)
    sys.argv = [str(source), '--margin', str(margin), '--out', str(output)]
    assert module.main() == 0
    row = json.loads((output / 'size.json').read_text())
    assert row['link_ok'] is expected
    if expected:
        assert row['code_bytes'] == 8040
    else:
        assert any('resident planning margin' in message for message in row['link_messages'])
    rows.append({'margin': margin, **row})
(ROOT / 'research/review_body_v39/evidence/margins.json').write_text(json.dumps(rows, indent=1) + '\n')
print(json.dumps({'status': 'PASS', 'margins': [row['margin'] for row in rows]}))
