"""Verify standard-04 recovery after all confirmed-recipe attempts fail."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_cases as nc
from common import save,sha
from extra_once import record as record_extra
record_extra()

unit=sys.argv[1]
n,ux,m,fr=nc.n,nc.ux,nc.m,nc.fr
n.configure(unit,'recovery-limits')
h,p,w=m.boot(unit);m.published(h,p,w);nc.move_to(h,p,5)
ux.need(fr.press(h,0x2b));m.reopen(h,p,w);ux.matches(h,p,5)
checkpoint=nc.stamp(h,p);rows=[]
for last_error in (20,21):
    def run(record,last_error=last_error):
        original=p.rpc.call;seen=[0];attempts=[];at=len(p.rpc.log)
        def attempt(b):
            attempts.append(dict(slot=h.u(b.core.r[0]+1,1),recovery=b.core.r[2]))
            return False
        h.b.add_breakpoint(p.symbol_pc('apply_impl'),attempt)
        def communication(command,value):
            seen[0]+=1
            if 16<=seen[0]<=last_error:
                if seen[0]==16:
                    value_returned=original(command,value)
                    p.rpc.log[-1].update(device_result=value_returned,result=-1,simulated=True)
                else:p.rpc.log.append(dict(cmd=command,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
                return -1
            return original(command,value)
        p.rpc.call=communication;result=ux.need(fr.move_key(h,0x20));p.rpc.call=original
        after=ux.snap(h,p);actual=ux.matches(h,p,4)
        assert h.u(p.symbol_pc('n')+3712,1)==0 and after['list']['uncertain']==0
        expected=[6,5,5,5,5]+[4]*(1 if last_error==20 else 2)
        assert [x['slot'] for x in attempts]==expected,attempts
        ux.need(fr.press(h,0x2b));m.reopen(h,p,w);reopened=ux.snap(h,p)
        assert reopened['rows']==8 and reopened['cursor']==4
        ux.matches(h,p,4)
        initial_attempts=list(attempts)
        retry_at=len(p.rpc.log)
        nc.move_to(h,p,6);retry_actual=ux.matches(h,p,6)
        ux.need(fr.press(h,0x2b));m.reopen(h,p,w)
        retry_state=ux.snap(h,p)
        assert retry_state['cursor']==6 and h.u(p.symbol_pc('n')+3712,1)==0
        assert retry_state['list']['confirmed_slot']==6
        record.update(unit=unit,dat_sha256=sha(p.dat),last_error=last_error,attempts=attempts,result=result,
            initial_attempts=initial_attempts,retry_actual=retry_actual,retry_state=retry_state,
            retry_rpc=len(p.rpc.log)-retry_at,
            after=after,actual=actual,reopened=reopened,rpc_log=p.rpc.log[at:],file_mutations=m.no_writes(p))
    x=nc.case('recovery-limits-'+unit+'-'+str(last_error),run,checkpoint)
    rows.append(dict(last_error=last_error,attempts=x['attempts']))
save('native/recovery-limits-'+unit+'.json',dict(status='PASS',unit=unit,dat_sha256=sha(p.dat),cases=rows))
