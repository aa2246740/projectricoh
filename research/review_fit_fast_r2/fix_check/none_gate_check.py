"""Check the absolute-DE00 rule for None-similarity targets against the review mutations."""
import importlib.util, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tools/fit_fast')); sys.path.insert(0, str(ROOT/'tools/fit_fast/round2'))
spec = importlib.util.spec_from_file_location('qg', ROOT/'tools/fit_fast/round2/quality_gate.py')
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
rows = json.loads((ROOT/'artifacts/downloads/fit-fast-r1/round2/quality/full-guard-final/per_photo.json').read_text())
out = []
for index in (30, 38, 46):
    sel = [r for r in rows if r['index'] == index and r['key'] == 'L1']
    assert len(sel) == 17 and all(r['reference'][0] is None for r in sel)
    for amount in (0., 1e-6, .001, .1, .5):
        op = {r['photo']: tuple(r['reference']) for r in sel}
        np_ = {r['photo']: (None, *[v+amount for v in r['actual'][1:]]) for r in sel}
        ok, _ = gate.absolute_de00(op, np_)
        out.append(dict(index=index, increase=amount, passed=ok))
print(json.dumps(out))
bad = [r for r in out if r['passed'] != (r['increase'] == 0.)]
sys.exit(1 if bad else 0)
