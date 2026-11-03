"""Recheck retained full-state receipts and the observed counterexamples."""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent
RUNS=HERE/'runs'
def read(name):
    return json.loads((RUNS/(name+'.json')).read_text())
rows=[]
for left,right in [('sd-keys-native-01','sd-keys-reference-01'),
                   ('recovery-seg-native-01','recovery-seg-reference-01'),
                   ('menu-published-native-01','menu-published-reference-01'),
                   ('first-menu-native-02','first-menu-reference-02')]+[
        (f'menu-seg-native-{i:02d}',f'menu-seg-reference-{i:02d}') for i in range(1,5)]:
    a,b=read(left),read(right)
    assert a['points']==b['points'],(left,right)
    assert a.get('final')==b.get('final'),(left,right,'final')
    rows.append({'native':left,'reference':right,'checkpoints':len(a['points'])})
for backend in ('native','reference'):
    raw=(HERE/f'sd-keys-{backend}-01-working.img').read_bytes()
    for sector in (521,523):
        expected=bytes((i*17+sector)%256 for i in range(512))
        assert raw[sector*512:(sector+1)*512]==expected
assert (HERE/'sd-keys-native-01-working.img').read_bytes()==(HERE/'sd-keys-reference-01-working.img').read_bytes()
a,b=read('edges-native-final'),read('edges-reference-final')
edge_count=len(a['cases'])
assert edge_count==10 and set(a['cases'])==set(b['cases'])
different={k for k in a['cases'] if a['cases'][k]['state']!=b['cases'][k]['state'] or a['cases'][k]['detail']!=b['cases'][k]['detail']}
assert different=={'absent-step-hook','base-only-step-hook','retained-mutable-input','wide-device-clock'}
a,b=read('pre-overlay-native-01'),read('pre-overlay-reference-01')
assert a['model_revision']==b['model_revision'] and (a['r0'],b['r0'])==(85,84)
matrix=read('snapshot-model-key-matrix')
assert all(r['identity_equal'] for r in matrix)
assert [r['accepted'] for r in matrix]==[True,False,True,True,True,False]
assert read('snapshot-key-input-source-01')['input_change_rejected']
assert read('snapshot-key-input-source-01')['source_change_rejected']
bench=read('benchmark-original-01')
assert bench['status']=='COMPLETE' and len(bench['pairs'])==5
assert all(r['same_state'] and r['records']['original']['state']==r['records']['native']['state'] for r in bench['pairs'])
print(json.dumps({'receipt_pairs':rows,'edge_cases':edge_count,
                  'expected_different_edge_cases':sorted(different),'p1':5,
                  'literal_SD_bytes':True,'speedup':bench['speedup']},ensure_ascii=False))
