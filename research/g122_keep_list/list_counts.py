"""Measure all sixteen adjacent list transitions on the final DAT."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_cases as nc
from common import save,sha
from extra_once import record as record_extra
record_extra()

unit=sys.argv[1];n,ux,m,fr=nc.n,nc.ux,nc.m,nc.fr
n.configure(unit,'list-counts')
h,p,w=m.boot(unit);m.published(h,p,w);ins=nc.no_cost(h,p)
warm=ux.measure_move(h,p,0x20,ins);ux.matches(h,p,5)
steps=[]
for key in [0x20]*8+[0x1f]*8:
    step=ux.measure_move(h,p,key,ins);row=step['after']['cursor'];actual=ux.matches(h,p,row)
    assert step['after']['dot_row']==row and not step['after']['list']['uncertain']
    steps.append(step)
    save('native/list-counts-progress-'+unit+'.json',dict(status='RUNNING',unit=unit,
        dat_sha256=sha(p.dat),steps=steps,warm=warm,file_mutations=m.no_writes(p)))
    print('COUNT',unit,len(steps),step['before']['cursor'],row,step['rpc_calls'],flush=True)
assert len({(x['before']['cursor'],x['after']['cursor']) for x in steps})==16
save('native/list-counts-'+unit+'.json',dict(status='PASS',unit=unit,dat_sha256=sha(p.dat),
    steps=steps,warm=warm,file_mutations=m.no_writes(p)))
print('PASS sixteen list transition counts',unit,flush=True)
