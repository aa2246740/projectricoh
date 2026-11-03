"""Observe H07 before the 28mm unit reports ready, through native handlers."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_native as n
from common import save,sha
n.configure('28mm','h07-unready')
ux,m,fr=n.ux,n.m,n.fr
h,p,w=m.boot('28mm',ready=0,link=1)
ux.need(fr.open_settings(h))
before=ux.snap(h,p)
assert before['rows']==7
rpc=len(p.rpc.log);preview=h.stub_hits.get('preview',0)
r=ux.need(fr.press(h,0x23));after=ux.snap(h,p)
row=dict(status='PASS',unit='28mm',before=before,after=after,result=r,rpc_delta=len(p.rpc.log)-rpc,
 preview_delta=h.stub_hits.get('preview',0)-preview,W_delta=sum(x['cmd']==22 for x in p.rpc.log[rpc:]),
 file_mutations=m.no_writes(p),native_log=p.native_log,getter_fixed_return_stub_removed=True,native_ui_hand_seeded=False)
save('native/h07-unready-28mm.json',row)
print('H07 first unready 28mm',row['rpc_delta'],row['W_delta'],row['preview_delta'],flush=True)
assert row['rpc_delta']==row['W_delta']==row['preview_delta']==0
