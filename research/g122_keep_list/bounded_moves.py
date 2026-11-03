"""Keep native navigation active at every transaction and verify both limits."""
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
    n.configure(unit,'bounded-moves')
    h,p,w=m.boot(unit);m.published(h,p,w);checkpoint=nc.stamp(h,p)
    records=[]
    for panel in (False,True):
        def run(record,panel=panel):
            if panel:ux.need(fr.native(h,0x202be220))
            h.b.map(0x206a0000,bytes(0x10000))
            transactions=[];pending=[False];original=p.rpc.call
            def applied(b):
                transactions.append(dict(recovery=b.core.r[2],rpc=len(p.rpc.log)))
                shadow_b=v.PythonBackend();shadow_b.regions=h.b.regions;shadow_b.mmio=h.b.mmio;shadow_b.traces=h.b.traces
                shadow_b.breakpoints={k:list(x) for k,x in h.b.breakpoints.items()}
                shadow_b.core.r=list(h.b.core.r);shadow_b.core.psw=h.b.core.psw;shadow_b.core.cr=dict(h.b.core.cr)
                shadow_b.core.bpsw=h.b.core.bpsw;shadow_b.core.bbpsw=h.b.core.bbpsw;shadow_b.core.acc=h.b.core.acc
                shadow_b.set_reg('r15',0x206afff0)
                shadow=copy.copy(h);shadow.b=shadow_b
                transactions[-1]['nested']=ux.need(fr.move_key(shadow,0x20))
                return False
            h.b.add_breakpoint(p.symbol_pc('apply_impl'),applied)
            def communication(cmd,value):
                if pending[0]:
                    pending[0]=False
                    b=v.PythonBackend();b.regions=h.b.regions;b.mmio=h.b.mmio;b.traces=h.b.traces
                    b.breakpoints={k:list(x) for k,x in h.b.breakpoints.items()}
                    b.core.r=list(h.b.core.r);b.core.psw=h.b.core.psw;b.core.cr=dict(h.b.core.cr)
                    b.core.bpsw=h.b.core.bpsw;b.core.bbpsw=h.b.core.bbpsw;b.core.acc=h.b.core.acc
                    b.set_reg('r15',0x206afff0)
                    shadow=copy.copy(h);shadow.b=b
                    transactions[-1]['nested']=ux.need(fr.move_key(shadow,0x20))
                return original(cmd,value)
            p.rpc.call=communication
            result=ux.need(fr.move_key(h,0x20,steps=60000000));p.rpc.call=original
            after=ux.snap(h,p)
            assert len(transactions)==16,transactions
            assert h.u(p.symbol_pc('n')+3712,1)==0
            assert after['list']['uncertain']==0
            if panel:
                from fn2_quality import live_rows
                actual=live_rows(h,p)
            else:actual=ux.matches(h,p,4)
            record.update(status='PASS',unit=unit,panel=panel,result=result,transactions=transactions,
                after=after,actual=actual,rpc_log=p.rpc.log,file_mutations=m.no_writes(p),dat_sha256=sha(p.dat))
        result=nc.case('bounded-moves-'+unit+('-panel' if panel else '-list'),run,checkpoint)
        records.append(dict(panel=panel,transactions=len(result['transactions'])))
    save('native/bounded-moves-'+unit+'.json',dict(status='PASS',unit=unit,cases=records,dat_sha256=sha(p.dat)))

if __name__=='__main__':main(sys.argv[1])
