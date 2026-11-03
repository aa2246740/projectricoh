"""Check readiness loss at W and UI allocation failures using native entries."""
from pathlib import Path
import copy
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_cases as nc
from common import save,sha
from extra_once import record as record_extra
record_extra()

def main(unit):
    n,ux,m,fr,pe,v=nc.n,nc.ux,nc.m,nc.fr,nc.pe,nc.v
    n.configure(unit,'write-boundaries')
    h,p,w=m.boot(unit);m.published(h,p,w);checkpoint=nc.stamp(h,p)
    records=[]
    for point in ('before_w','service_w'):
        def run(record,point=point):
            h.b.map(0x206a0000,bytes(0x10000));fired=[False]
            def stop_ready(b):
                if fired[0]:return False
                if point=='service_w' and not (b.core.r[0]==4 and b.core.r[1]==3):return False
                fired[0]=True;p.ready=0
                shadow_b=v.PythonBackend();shadow_b.regions=h.b.regions;shadow_b.mmio=h.b.mmio;shadow_b.traces=h.b.traces
                shadow_b.breakpoints={k:list(x) for k,x in h.b.breakpoints.items()}
                shadow_b.core.r=list(h.b.core.r);shadow_b.core.psw=h.b.core.psw;shadow_b.core.cr=dict(h.b.core.cr)
                shadow_b.core.bpsw=h.b.core.bpsw;shadow_b.core.bbpsw=h.b.core.bbpsw;shadow_b.core.acc=h.b.core.acc
                shadow_b.set_reg('r15',0x206afff0)
                shadow=copy.copy(h);shadow.b=shadow_b
                ux.need(fr.native(shadow,0x200935b4,(0,)))
                return False
            h.b.add_breakpoint(p.symbol_pc('write_word' if point=='before_w' else 'rv_call'),stop_ready)
            result=ux.need(fr.move_key(h,0x20));after=ux.snap(h,p)
            assert fired[0] and after['W']==0
            assert h.u(p.symbol_pc('n')+3712,1)==0 and after['list']['uncertain']==0
            assert after['root']['state']==3
            ux.matches(h,p,4)
            p.ready=1;ux.need(fr.native(h,0x200935b4,(1,)))
            m.reopen(h,p,w);ux.need(fr.move_key(h,0x20));actual=ux.matches(h,p,5)
            record.update(unit=unit,point=point,result=result,after=after,actual=actual,
                rpc_log=p.rpc.log,file_mutations=m.no_writes(p),dat_sha256=sha(p.dat))
        records.append(nc.case('write-boundary-'+unit+'-'+point,run,checkpoint))
    save('local/native/write-boundaries-'+unit+'.json',dict(status='PASS',unit=unit,cases=records,dat_sha256=sha(p.dat)))

if __name__=='__main__':main(sys.argv[1])
