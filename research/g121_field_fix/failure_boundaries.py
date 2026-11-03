"""Verify that failures before W release the view and permit a later retry."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_native as n
from common import save,sha

unit=sys.argv[1];at=int(sys.argv[2]);n.configure(unit,'failure-boundary-'+str(at))
ux,m,fr=n.ux,n.m,n.fr
h,p,w=m.boot(unit);m.published(h,p,w)
original=p.rpc.call;seen=[0]
def failed(cmd,value):
    seen[0]+=1
    if seen[0]<at:return original(cmd,value)
    p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
    return -1
p.rpc.call=failed
result=ux.need(fr.move_key(h,0x20));after=ux.snap(h,p)
assert seen[0]>=at and after['W']==0 and h.u(p.symbol_pc('n')+3712,1)==0
ux.matches(h,p,4)
p.rpc.call=original
m.reopen(h,p,w)
reopened=ux.snap(h,p)
assert reopened['rows']==8 and reopened['cursor']==4
ux.need(fr.move_key(h,0x20));actual=ux.matches(h,p,5)
save('native/failure-boundary-'+unit+'-at'+str(at)+'.json',dict(status='PASS',unit=unit,at=at,
    dat_sha256=sha(p.dat),move=result,after=after,reopened=reopened,actual=actual,
    calls_reached=seen[0],rpc_log=p.rpc.log,file_mutations=m.no_writes(p)))
print('PASS recoverable communication boundary',unit,at,flush=True)
