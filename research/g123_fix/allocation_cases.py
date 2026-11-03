"""Fail native workspace and UI allocations, then reopen through H01."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_cases as nc
from common import save,sha
from extra_once import record as record_extra
record_extra()

def main(unit):
    n,ux,m,fr,pe=nc.n,nc.ux,nc.m,nc.fr,nc.pe
    n.configure(unit,'allocation-retry')
    h,p,w=m.boot(unit);checkpoint=nc.stamp(h,p);records=[]
    for kind in ('workspace','ui'):
        def run(record,kind=kind):
            menu=[False];failed=[]
            def entry(b):
                if b.core.r[1]==p.elf.symbols['ig_menu']:menu[0]=True
                return False
            def allocate(b):
                size=b.core.r[4]
                if menu[0] and not failed and (kind=='workspace' or size==1968):
                    failed.append(dict(bytes=size,return_address=hex(b.core.r[14])))
                    b.core.r[0]=0;b.set_reg('pc',b.core.r[14])
                return False
            h.b.add_breakpoint(h.symbols['rv_engine'],entry)
            h.b.breakpoints.setdefault(0x2005bf5c,[]).insert(0,allocate)
            opened,_,error=fr.publish(h,p,w);ux.need(opened);assert error is None,error
            before=ux.snap(h,p)
            assert failed and before['root']['state']==3 and before['rows']==(8 if kind=='workspace' else 7)
            assert h.u(p.symbol_pc('n')+3712,1)==0
            m.reopen(h,p,w);after=ux.snap(h,p)
            assert after['rows']==8 and after['cursor']==4
            ux.need(fr.move_key(h,0x20));actual=ux.matches(h,p,5)
            record.update(unit=unit,kind=kind,failed_allocation=failed,before=before,after=after,
                actual=actual,file_mutations=m.no_writes(p),dat_sha256=sha(p.dat))
        records.append(nc.case('allocation-retry-'+unit+'-'+kind,run,checkpoint))
    save('local/native/allocation-retry-'+unit+'.json',dict(status='PASS',unit=unit,cases=records,dat_sha256=sha(p.dat)))

if __name__=='__main__':main(sys.argv[1])
