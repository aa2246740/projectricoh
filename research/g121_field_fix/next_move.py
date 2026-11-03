"""Observe the next native navigation after a pre-W communication failure."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_native as n
from common import save,sha

unit=sys.argv[1];n.configure(unit,'next-move')
ux,m,fr=n.ux,n.m,n.fr
h,p,w=m.boot(unit);m.published(h,p,w)
original=p.rpc.call
def busy(command,value):
    p.rpc.log.append(dict(cmd=command,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True));return -1
p.rpc.call=busy;ux.need(fr.move_key(h,0x20));p.rpc.call=original
failed=ux.snap(h,p);assert failed['W']==0 and h.u(p.symbol_pc('n')+3712,1)==0
at=len(p.rpc.log);moved=ux.need(fr.move_key(h,0x20));after=ux.snap(h,p)
next_calls=len(p.rpc.log)-at;rebound=after['rows']==8 and next_calls>0
m.reopen(h,p,w);reopened=ux.snap(h,p)
save('native/next-move-'+unit+'.json',dict(status='PASS' if rebound else 'FAIL_MOVE_REBIND',
    unit=unit,dat_sha256=sha(p.dat),failed=failed,move=moved,after=after,reopened=reopened,
    reopen_settings_aligned=reopened['mode']==1,next_move_rpc=next_calls,file_mutations=m.no_writes(p)))
print('Next move rebind',unit,rebound,'rows',after['rows'],'reopen',reopened['rows'],flush=True)
