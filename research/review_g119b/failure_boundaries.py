"""Observe persistent communication errors before and at the first unit write."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_native as n
from common import save,sha

unit=sys.argv[1];at=int(sys.argv[2]);n.configure(unit,'failure-boundary-'+str(at))
ux,m,fr=n.ux,n.m,n.fr
h,p,w=m.boot(unit);m.published(h,p,w);original=p.rpc.call;seen=[0]
def failed(cmd,value):
    seen[0]+=1
    if seen[0]<at:return original(cmd,value)
    if seen[0]==at:
        original(cmd,value);p.rpc.log[-1].update(device_result=p.rpc.log[-1]['result'],result=-1,simulated=True)
    else:p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
    return -1
p.rpc.call=failed
result=ux.need(fr.move_key(h,0x20));after=ux.snap(h,p);slots=[]
for slot in range(1,9):
    try:ux.matches(h,p,slot)
    except AssertionError:continue
    slots.append(slot)
before_open=len(p.rpc.log);texts=[]
def text_input(b):
    texts.append(b.read(b.core.r[0],b.core.r[1]).decode('ascii'))
    return False
h.b.add_breakpoint(p.symbol_pc('rv_native_ascii'),text_input)
ux.need(fr.press(h,0x2b));h.parent()
opened,_,error=fr.publish(h,p,w);ux.need(opened);assert error is None,error
notice=ux.snap(h,p)
visible=notice['rows']==1 and texts and all(t=='ERR POWER OFF/ON' for t in texts)
assert len(p.rpc.log)==before_open
save('native/failure-boundary-'+unit+'-at'+str(at)+'.json',dict(unit=unit,at=at,dat_sha256=sha(m.DAT.read_bytes()),
    status='NOTICE_VISIBLE' if visible else 'NOTICE_ABSENT',move=result,after=after,complete_slots=slots,
    notice=notice,ascii_sources=texts,notice_visible=bool(visible),new_rpc=0,rpc_log=p.rpc.log,file_mutations=m.no_writes(p),
    scope='Native cold menu, real arrow and close/reopen paths; only communication responses are simulated.'))
print('OBSERVED persistent error',unit,'boundary',at,'complete recipes',slots,'notice',bool(visible),'root',after['root']['state'],flush=True)
