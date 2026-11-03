"""Verify native-settings restoration and a pre-W preview failure on reopen."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_cases as nc
from common import save,sha

unit=sys.argv[1]
n,ux,m,fr=nc.n,nc.ux,nc.m,nc.fr
n.configure(unit,'settings-retry')
h,p,w=m.boot(unit);m.published(h,p,w);original=p.rpc.call
def busy(command,value):
    p.rpc.log.append(dict(cmd=command,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True));return -1
p.rpc.call=busy;ux.need(fr.move_key(h,0x20));p.rpc.call=original
failed=ux.snap(h,p);assert failed['W']==0 and failed['rows']==7
before=len(p.rpc.log);moved=ux.need(fr.move_key(h,0x20));after=ux.snap(h,p)
next_calls=len(p.rpc.log)-before
assert after['mode']==4 and after['rows']==7 and next_calls==0
checkpoint=nc.stamp(h,p);rows=[]
for preview_failure in (False,True):
    def run(record,preview_failure=preview_failure):
        middle=None
        if preview_failure:
            address=0x202d6f38;callbacks=list(h.b.breakpoints[address]);h.b.breakpoints[address]=[]
            h.stub(address,'preview',value=1)
            h.parent();opened,_,error=fr.publish(h,p,w);ux.need(opened);assert error is None,error
            middle=ux.snap(h,p)
            assert middle['rows']==7 and middle['mode']==1 and middle['W']==0
            assert middle['list']['uncertain']==0 and h.u(p.symbol_pc('n')+3712,1)==0
            h.b.breakpoints[address]=callbacks
        m.reopen(h,p,w);reopened=ux.snap(h,p);actual=ux.matches(h,p,4)
        assert reopened['rows']==8 and reopened['mode']==1 and reopened['W']==0
        assert reopened['list']['uncertain']==0 and h.u(p.symbol_pc('n')+3712,1)==0
        record.update(unit=unit,dat_sha256=sha(p.dat),preview_failure=preview_failure,
            failed=failed,after_native_move=after,middle=middle,reopened=reopened,actual=actual,
            rpc_log=p.rpc.log,file_mutations=m.no_writes(p))
        if not preview_failure:
            save('local/native/next-move-'+unit+'.json',dict(status='FAIL_MOVE_REBIND',unit=unit,dat_sha256=sha(p.dat),
                failed=failed,move=moved,after=after,reopened=reopened,reopen_settings_aligned=True,
                next_move_rpc=next_calls,file_mutations=m.no_writes(p)))
    x=nc.case('settings-retry-'+unit+('-preview' if preview_failure else '-normal'),run,checkpoint)
    rows.append(dict(preview_failure=preview_failure,status=x['status']))
save('local/native/settings-retry-'+unit+'.json',dict(status='PASS',unit=unit,dat_sha256=sha(p.dat),cases=rows))
