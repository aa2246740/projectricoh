"""Select accepted reruns and compare all C/Python transaction witnesses."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

def read(name):
    value=json.loads((C.HERE/'evidence'/(name+'.json')).read_text())
    assert value['status']=='PASS',name
    return value

c={}
for name in ('fast-iteration-r2','fast-extra-c','fast-critical-c'):
    c.update({r['case']:r for r in read(name)['rows']})
p={r['case']:r for r in read('fast-python-final')['rows'] if r['case'] not in ('wrong-T','wrong-row')}
p.update({r['case']:r for r in read('fast-python-r2')['rows']})
assert len(c)==len(p)==21 and c.keys()==p.keys()
fields=('return_value','word','W_calls','preview_calls','fixed_word_stores','S_stores','S_equal','record_equal','T')
rows=[]
for case in sorted(c):
    left,right=c[case],p[case]
    assert all(left[k]==right[k] for k in fields),case
    assert left['stop']['reason']==right['stop']['reason']=='return'
    assert left['stop']['steps']==right['stop']['steps'],case
    if 'stock_rows_equal' in left:
        assert left['stock_rows_equal']==right['stock_rows_equal'],case
    rows.append(dict(case=case,C_Python_witnesses_equal=True,instructions=left['stop']['steps'],
                     result=left['return_value'],word=left['word'],W_calls=left['W_calls'],
                     stock_rows_equal=right.get('stock_rows_equal')))
required=('qualification','native-selection','release','h52-r2','record-store','retained-matrix','static',
          'transaction-baseline-bounded-r2','transaction-w-fail-compensation-fault-r2',
          'transaction-mode-after-W-fault-r2')
for name in required:read(name)
C.save('cross-backend',dict(status='PASS',rows=rows,required_receipts=list(required),
                           discarded_rows='fast-python-final wrong-T and wrong-row replaced by fast-python-r2',
                           process_deviation='See process-deviation.json. This check does not erase that history.'))
