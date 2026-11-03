"""Observe settings writes after a native menu switch during first publication."""
from pathlib import Path
import argparse
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from safety_cases import shadow
from cold_reentry import full_plan

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--generation',type=int,choices=(121,124,126),default=126)
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm')
    args=parser.parse_args()
    ux,m,fr,pe,v=setup(args.generation,args.unit,'ownership-settings')
    h,p,w=m.boot(args.unit)
    settings=h.u(0x200c0dac)
    armed=[False];arrow=[False];switched=[False]
    stores=[];services=[];events=[]
    def switch(b):
        if switched[0]:return False
        assert b.core.psw&0x40 and h.u(pe.ROOT_ADDR+6,1)==1
        before=ux.snap(h,p)
        other=shadow(h,v)
        other.run_slice(0x202ba380,0x202ba3c8)
        other.leave_other_list()
        events.append(dict(kind='native_menu_switch',pc=hex(b.pc),before=before,after=ux.snap(h,p)))
        switched[0]=True
        return False
    def service(b):
        service_id,operation=b.core.r[0],b.core.r[1]
        if service_id==10 and operation==1 and not switched[0]:
            h.b.add_breakpoint(b.core.r[14],switch)
        if switched[0] and service_id in (5,6):
            services.append(dict(service=service_id,operation=operation,activity=h.u(0x205d9bf8),state=h.u(0x205d9c00)))
        return False
    def before_publish(b):
        if arrow[0]:return False
        arrow[0]=True
        other=shadow(h,v)
        before=ux.snap(h,p)
        result=ux.need(fr.move_key(other,0x20,steps=30000000))
        events.append(dict(kind='native_direction_key',before=before,after=ux.snap(h,p),result=result))
        assert h.u(settings+0x36e,1)==5
        return False
    def entering(b):
        if armed[0]:return False
        block=h.u(pe.ROOT_ADDR+56)
        if not block:return False
        p.image_base=h.u(block+312)
        if not p.image_base:return False
        armed[0]=True
        h.b.add_breakpoint(p.symbol_pc('list_bind'),before_publish)
        h.b.add_breakpoint(p.symbol_pc('rv_call'),service)
        return False
    def store(e):
        if switched[0] and e.origin=='cpu':
            stores.append(dict(pc=hex(e.pc),offset=hex(e.address-settings),bytes=len(e.data),value=e.value,
                               activity=h.u(0x205d9bf8),state=h.u(0x205d9c00)))
    h.b.add_write_trace(settings,settings+0xc9e,store)
    h.b.add_breakpoint(h.symbols['rv_invoke'],entering)
    h.b.core.psw|=0x40
    h.parent()
    result,_,error=fr.publish(h,p,w)
    ux.need(result)
    assert error is None,error
    assert arrow[0] and switched[0]
    plan=full_plan(h,p)
    record=dict(status='LATE_SETTINGS_WRITES' if stores else 'NO_LATE_SETTINGS_WRITES',
        generation=args.generation,unit=args.unit,dat_sha256=sha(p.dat),events=events,
        stores_after_switch=stores,services_after_switch=services,final=ux.snap(h,p),
        final_plan=plan,file_mutations=m.no_writes(p),native_UI=ui_audit(h),rpc_log=p.rpc.log)
    save('local/ownership-settings/'+str(args.generation)+'-'+args.unit+'.json',record)
    save('evidence/ownership-settings-'+str(args.generation)+'-'+args.unit+'.json',
         {k:v for k,v in record.items() if k!='rpc_log'})
    print(record['status'],args.generation,args.unit,stores)

if __name__=='__main__':main()
