"""Reach failure naturally, then challenge every resident engine application entry."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_native as n
from common import OUT,save,sha

unit=sys.argv[1];n.configure(unit,'latch-paths')
ux,m,fr=n.ux,n.m,n.fr
h,p,w=m.boot(unit);m.published(h,p,w)
original=p.rpc.call;calls=[0]
def failed(cmd,value):
    calls[0]+=1
    if calls[0]==16:
        original(cmd,value);p.rpc.log[-1].update(device_result=p.rpc.log[-1]['result'],result=-1,simulated=True)
        return -1
    if calls[0]>16:
        p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
        return -1
    return original(cmd,value)
p.rpc.call=failed
ux.need(fr.move_key(h,0x20));before=ux.snap(h,p)
assert before['list']['uncertain']==1 and before['root']['state']==3
root_n=p.symbol_pc('n');assert h.u(root_n+3712,1)==1
at=len(p.rpc.log);preview=h.stub_hits.get('preview',0);rows=[]
# Slot numbers come from the actual bootstrap entry table, not raw function
# calls. These are API-boundary challenges after a real native fault path.
for slot,args in ((0,[]),(3,[]),(4,[0]),(4,[10]),(5,[]),(6,[0]),(6,[7]),
                  (2,[7,1]),(2,[7,0]),(2,[0,0])):
    result=p.engine(slot,args)
    assert result['ok'],result
    assert len(p.rpc.log)==at and h.stub_hits.get('preview',0)==preview,(slot,args)
    assert h.u(root_n+3712,1)==1 and ux.snap(h,p)['list']['uncertain']==1
    rows.append(dict(slot=slot,args=args,result=result,failed=h.u(root_n+3712,1),rpc_delta=len(p.rpc.log)-at))
# The genuine constructor must still be available after repeated init and all
# application entries. Restore no field by hand.
h.parent();opened,_,error=fr.publish(h,p,w);ux.need(opened);assert error is None,error
notice=ux.snap(h,p);assert notice['rows']==notice['cursor']==notice['dot_row']==1
assert len(p.rpc.log)==at and h.stub_hits.get('preview',0)==preview
save('native/latch-paths-'+unit+'.json',dict(status='PASS',unit=unit,dat_sha256=sha(m.DAT.read_bytes()),
    before=before,cases=rows,notice=notice,application_latch_read_only=True,
    rpc_delta=0,preview_delta=0,file_mutations=m.no_writes(p),
    evidence_scope='Real native H08 creates latch; subsequent real resident API entries challenge alternate_routees; device edges remain models.'))
print('PASS latch',unit,'init, Fn2, panel event/abort, apply rows, H07 keep/close and other events; notice remains one row',flush=True)
