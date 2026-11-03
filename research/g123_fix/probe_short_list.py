from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
ux,m,fr,pe,v=setup(tag='short-list-probe')
probe=OUT/'local/probe'
m.DAT=pe.STAGED=probe/'GXRCE.DAT';pe.STAGED_SHA=file_sha(pe.STAGED);pe.ENGINE_ELF=probe/'engine.elf'
assert pe.STAGED_SHA=='35ea05b7931a44a2bf9383e5c5f863fdb85ecd8ed5255fd20a82f259ba719f18'
h,p,w=m.boot('50mm');m.published(h,p,w)
ux.need(fr.move_key(h,0x20));ux.matches(h,p,5);ux.need(fr.press(h,0x2b))
p.rpc.overlay.clear();p.rpc.t=2
original=p.rpc.call
def busy(cmd,value):
    p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True));return -1
p.rpc.call=busy
h.parent();mark=len(h.writes);draws=[]
def draw(b):
    state=b.core.r[13];draws.append(dict(state=hex(state),marker=h.u(state+9,1),cursor=h.u(state+10,1),rows=h.u(0x2022f5ac,1)));return False
h.b.add_breakpoint(0x201ffb2c,draw)
opened,_,error=fr.publish(h,p,w);ux.need(opened);assert error is None,error
before=ux.snap(h,p);events=[]
def entered(b):events.append('H08');return False
h.b.add_breakpoint(p.symbol_pc('ig_apply'),entered)
arrow=ux.need(fr.move_key(h,0x20,steps=30000000));after=ux.snap(h,p)
record=dict(status='PROBE_OBSERVED',unit='50mm',dat_sha256=sha(p.dat),opened=opened,pending=before,arrow=arrow,after=after,events=events,draws=draws,
    native_cursor_marker_writes=[x for x in h.writes[mark:] if int(x['address'],16) in (0x2022f725,0x2022f726)],rpc_log=p.rpc.log,native_UI=ui_audit(h),file_mutations=m.no_writes(p))
save('local/probe/short-list.json',record)
print(json.dumps(dict(rows=before['rows'],cursor=before['cursor'],dot=before['dot_row'],after_rows=after['rows'],H08=len(events),draws=draws[:4])))
