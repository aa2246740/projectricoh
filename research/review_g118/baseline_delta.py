"""Same persistent-failure injection against the exact reviewed gen117 DAT."""
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import ROOT, OUT, save, sha
import run_native as review
ux,m,fr,pe,v=review.ux,review.m,review.fr,review.pe,review.v
dat,elf=ux.configure(True,'baseline-delta')
v.python_backend.CACHE=OUT/'decode/baseline-delta'
assert sha(dat.read_bytes())=='35ce20ac843764b9cdd452785683ebf99004c47b77ae90720c2e3dc716c31211'
h,p,w=m.boot('50mm');m.published(h,p,w);r=dict(dat_sha256=sha(dat.read_bytes()),elf_sha256=sha(elf.read_bytes()))
r['cold']=ux.snap(h,p);r['cold_actual']=m.deep(p,4)
original=p.rpc.call;count=0
def failed(cmd,value):
    global count
    count+=1
    if count==16:
        original(cmd,value);p.rpc.log[-1].update(device_result=p.rpc.log[-1]['result'],result=-1,injected=True);return -1
    if count>16:
        p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,injected=True));return -1
    return original(cmd,value)
p.rpc.call=failed
r['H08']=ux.need(fr.move_key(h,0x20));r['after_H08']=ux.snap(h,p);r['after_H08_actual']=m.deep(p,4)
assert count==0 and sum(x['cmd']==22 for x in p.rpc.log)==0
print('PASS gen117 same H08: zero RPC/W; complete stock04 remains; no RPC interruption window',flush=True)
r['H07']=ux.need(fr.press(h,0x23));r['after_H07']=ux.snap(h,p);r['complete_slots_after_H07']=[]
for slot in range(1,9):
    try:m.deep(p,slot)
    except AssertionError:pass
    else:r['complete_slots_after_H07'].append(slot)
assert count>=16 and not r['complete_slots_after_H07']
r.update(status='PASS_BASELINE_DELTA',rpc_calls=count,rpc_log=p.rpc.log,file_mutations=m.no_writes(p),
         finding='Persistent partial-write exposure already exists on gen117 H07; gen118 adds it to each H08 navigation and compensates only when transport recovers')
save('native/baseline-delta.json',r)
print('PASS baseline comparison: gen117 persistent failure during OK already leaves partial data; gen118 shifts exposure to navigation',flush=True)
