"""Recompute the existing local A checks with review-owned output paths."""
from pathlib import Path
import collections
import json
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_scope import ROOT, SOURCE, OUT, load, save, sha, record_inputs

common = types.ModuleType('common')
common.ROOT, common.OUT = ROOT, SOURCE
common.load, common.save, common.sha = load, save, sha
sys.modules['common'] = common
c = load(SOURCE / 'codegen.py', 'review_current_codegen')
c.OUT = OUT / 'local_a'
c.OUT.mkdir(exist_ok=True)
c.save = lambda name, value: save('local_a/' + name, value)
c.main()
expected = json.loads((SOURCE / 'codegen-inventory.json').read_text())
actual = json.loads((c.OUT / 'codegen-inventory.json').read_text())
assert actual == expected
save('local-a-check.json', dict(status='PASS', exact_inventory_equal=True,
     obligations=len(actual), local_A=sum(bool(x.get('local_A')) for x in actual),
     changes=dict(collections.Counter(x['status'] for x in actual))))
record_inputs('local-a-inputs.json')
