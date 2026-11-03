"""Check the one-row diagnostic and its native details pointer after W failure."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_cases as nc
from common import save,sha
from extra_once import record as record_extra
record_extra()

def main(unit):
    n,ux,m,fr=nc.n,nc.ux,nc.m,nc.fr
    n.configure(unit,'notice-details')
    h,p,w=m.boot(unit);m.published(h,p,w)
    writes=[]
    def failed_write(event):
        writes.append(dict(pc=hex(event.pc),bytes=event.data.hex()))
    h.b.add_write_trace(p.symbol_pc('n')+3712,p.symbol_pc('n')+3713,failed_write)
    reached=nc.persistent(h,p,16)
    assert reached>16 and h.u(p.symbol_pc('n')+3712,1)==1
    assert ux.snap(h,p)['list']['uncertain']==1
    details=[]
    def pointer(b):
        address=b.core.r[2]
        root=fr.root_fields(h)
        fail,value=fr.owned_fail(h,5,root)
        details.append(dict(pointer=hex(address),bytes=h.b.read(address,12).hex(),owner_fail=fail,owner_value=value,
            activity=h.u(0x205d9bf8),state=h.u(0x205d9c00),part=h.u(0x205a280f,1),
            count=h.u(0x205a27d4,1),names=hex(h.u(0x2022f5a8)),root=root))
        return False
    h.b.add_breakpoint(0x201febec,pointer)
    at=len(p.rpc.log)
    shown=nc.notice(h,p,w)
    ui=shown['state']['root']['ui_block']
    save('local/native/notice-details-progress-'+unit+'.json',dict(diagnostic=shown,details=details,failed_writes=writes))
    assert h.u(ui+96,1)==1
    owned=[d for d in details if not d['owner_fail']]
    assert shown['state']['rows']==shown['state']['cursor']==shown['state']['dot_row']==1,shown
    assert details and all(d['bytes']=='00'*12 for d in details),details
    assert all(d['pointer']==hex(ui+104) for d in owned),owned
    for _ in range(2):
        ux.need(fr.move_key(h,0x20));ux.need(fr.native(h,0x202be220))
        ux.need(fr.press(h,0x23));h.parent()
        opened,_,error=fr.publish(h,p,w);ux.need(opened);assert error is None,error
        assert h.u(0x2022f5ac,1)==1 and h.u(0x2022f726,1)==1
    assert len(p.rpc.log)==at
    assert h.u(p.symbol_pc('n')+3712,1)==1
    save('local/native/notice-details-'+unit+'.json',dict(status='PASS',unit=unit,diagnostic=shown,
        details=details,failed_writes=writes,rpc_calls_after_lock=0,file_mutations=m.no_writes(p),dat_sha256=sha(p.dat)))
    print('PASS diagnostic text and empty native details',unit,flush=True)

if __name__=='__main__':main(sys.argv[1])
