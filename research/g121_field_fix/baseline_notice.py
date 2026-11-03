"""Observe the original one-row notice through the unchanged native constructor."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import save,sha
from key_probe import configure,ux,m,fr
import native_sequence as sequence

def main():
    configure(True)
    h,p,w=m.boot('50mm');sequence.device_edges(h,p);sequence.prepare_input(h)
    h.parent();m.published(h,p,w);h.select_item_8();sequence.open_image_from_adj(h,p,fr)
    writes=[];details=[];texts=[]
    h.b.add_write_trace(p.symbol_pc('n')+3712,p.symbol_pc('n')+3713,
        lambda e:writes.append(dict(pc=hex(e.pc),bytes=e.data.hex(),origin=e.origin)))
    original=p.rpc.call;count=[0]
    def busy(command,value):
        count[0]+=1
        if count[0]<=3:
            p.rpc.log.append(dict(cmd=command,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True));return -1
        return original(command,value)
    p.rpc.call=busy;ux.need(fr.move_key(h,0x20));p.rpc.call=original
    before=ux.snap(h,p)
    def pointer(b):
        a=b.core.r[2];details.append(dict(pointer=hex(a),bytes=b.read(a,12).hex(),row=h.u(0x2022f726,1)))
        return False
    def text(b):texts.append(b.read(b.core.r[0],b.core.r[1]).decode('ascii'));return False
    h.b.add_breakpoint(0x201febec,pointer)
    h.b.add_breakpoint(p.symbol_pc('rv_native_ascii'),text)
    ux.need(fr.press(h,0x2b));h.parent()
    opened,_,error=fr.publish(h,p,w);ux.need(opened);assert error is None,error
    after=ux.snap(h,p)
    assert h.u(p.symbol_pc('n')+3712,1)==1 and before['W']==0 and after['rows']==1
    save('baseline-notice.json',dict(status='OBSERVED',dat_sha256=sha(p.dat),before=before,after=after,
        text=texts,details=details,failed_writes=writes,file_mutations=m.no_writes(p)))
    print('OBSERVED original notice',after['cursor'],after['dot_row'],texts,details,flush=True)

if __name__=='__main__':main()
