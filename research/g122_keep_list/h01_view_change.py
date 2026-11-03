"""Check that a failed H01 check does not publish over another native view."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_cases as nc
from common import save,sha
from ui_trace_scope import touches_ui

unit=sys.argv[1];n,ux,m,fr=nc.n,nc.ux,nc.m,nc.fr
n.configure(unit,'h01-view-change')
h,p,w=m.boot(unit);m.published(h,p,w);nc.move_to(h,p,5)
ux.need(fr.press(h,0x2b));h.parent()
original=p.rpc.call;changed=[False];writes=[];other=[None]
offset=int.from_bytes(p.dat[132:136],'big');length=int.from_bytes(p.dat[136:140],'big')
low=p.image_base+offset;high=low+length
def watch(event):
    if changed[0] and touches_ui(event) and event.origin=='cpu' and low<=event.pc<high:
        writes.append(dict(address=hex(event.address),pc=hex(event.pc),data=event.data.hex()))
h.b.add_write_trace(0,2**32,watch)
def communication(command,value):
    if not changed[0]:
        other[0]=nc.other_list(h);changed[0]=True
    p.rpc.log.append(dict(cmd=command,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
    return -1
p.rpc.call=communication
opened,_,error=fr.publish(h,p,w);p.rpc.call=original
after=ux.snap(h,p)
save('native/h01-view-change-'+unit+'.json',dict(status='PASS' if not writes else 'FAIL',
    unit=unit,dat_sha256=sha(p.dat),opened=opened,error=error,other=other[0],after=after,
    engine_ui_writes_after_switch=writes,file_mutations=m.no_writes(p),rpc_log=p.rpc.log))
assert opened['ok'] and error is None and changed[0]
assert not writes,writes
print('PASS H01 view change',unit,flush=True)
