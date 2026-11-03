"""Observe whether a failed preview is retried after the next native reopen."""
from pathlib import Path
import argparse
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ui_test_support as ui
from support import *
from cold_reentry import full_plan

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm')
    parser.add_argument('--generation',type=int,choices=(124,126),default=126)
    args=parser.parse_args()
    original_setup=ui.setup
    ui.setup=lambda unit,tag:original_setup(args.generation,unit,tag)
    s=ui.Session(args.unit,'preview-reopen-'+str(args.generation))
    s.press('DOWN');s.press('OK');s.reopen()
    assert s.state()['slot']==5
    before=s.state()
    settings=s.h.u(0x200c0dac)
    s.h.phase='model:settings_input'
    s.h.put(settings+0x36e,5,1)
    s.h.phase='cpu'
    observed=[]
    service_calls=[]
    def service(b):
        if b.core.r[0]!=5 or b.core.r[1]!=1:return False
        service_calls.append(dict(plan=full_plan(s.h,s.p,5),failed=len(service_calls)==0))
        if len(service_calls)==1:
            reply=b.core.r[3]
            b.write(reply,struct.pack('>HHi',1,32,-1))
            b.core.r[0]=0xffffffff
            b.set_reg('pc',b.core.r[14])
        return False
    s.h.b.add_breakpoint(s.p.symbol_pc('rv_call'),service)
    s.h.b.add_breakpoint(0x202d6f38,lambda b:observed.append(full_plan(s.h,s.p,5)) or False)
    callbacks=s.h.b.breakpoints[s.p.symbol_pc('rv_native_ascii')]
    callbacks[:]=[cb for cb in callbacks if cb!=s._ascii]
    if args.generation==126:
        failed_return=s.press('DISP')
    else:
        s.h.parent()
        result,_,error=s.fr.publish(s.h,s.p,s.w)
        s.ux.need(result)
        assert error is None,error
        failed_return=s.state()
    at=len(service_calls);native_at=len(observed)
    after_failure=full_plan(s.h,s.p,5)
    next_open=s.reopen()
    after_reopen=full_plan(s.h,s.p,5)
    assert len(service_calls)>=1 and after_failure['matches'] and after_reopen['matches']
    missing=len(service_calls)==at and len(observed)==native_at
    report=dict(status='OBSERVED_MISSING_RETRY' if missing else 'PREVIEW_RETRIED',
        generation=args.generation,unit=args.unit,dat_sha256=sha(s.p.dat),before=before,
        failed_return=failed_return,after_failure=after_failure,next_open=next_open,
        after_reopen=after_reopen,preview_services=service_calls,native_preview_plans=observed,
        preview_service_calls_on_next_open=len(service_calls)-at,native_preview_calls_on_next_open=len(observed)-native_at,
        file_mutations=s.m.no_writes(s.p),native_UI=ui_audit(s.h),rpc_log=s.p.rpc.log)
    save('local/preview-reopen/'+str(args.generation)+'-'+args.unit+'.json',report)
    save('evidence/preview-reopen-'+str(args.generation)+'-'+args.unit+'.json',
         {k:v for k,v in report.items() if k!='rpc_log'})
    print(report['status'],args.generation,args.unit,'preview calls on reopen',len(observed)-native_at)

if __name__=='__main__':main()
