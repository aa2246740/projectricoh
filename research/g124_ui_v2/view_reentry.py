"""Inject native arrows at inflight cuts on every gen 124 screen; S must not change."""
from pathlib import Path
import argparse
import os
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ui_test_support import *
from safety_cases import shadow
from static_audit import symbols

CUTS=('entry','bind','after_restore','before_redraw','row_draw')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--unit',default='50mm',choices=('50mm','28mm','mount'))
    parser.add_argument('--cuts',nargs='+',choices=CUTS,default=CUTS)
    args=parser.parse_args();s=Session(args.unit,'view-reentry')
    s.press('DOWN');s.press('OK');s.reopen()
    compiled=symbols(ELF);ui_symbol=next(name for name in compiled if name=='ui_list' or name.startswith('ui_list.'))
    ui_start=s.p.image_base+compiled[ui_symbol]['address'];ui_end=ui_start+compiled[ui_symbol]['size']
    results=[]
    def view(name):
        for cut in args.cuts:
            for key in ('UP','DOWN'):
                sys.stdout.flush();pid=os.fork()
                if pid==0:
                    record=dict(view=name,cut=cut,key=key,unit=args.unit,dat_sha256=sha(s.p.dat));code=0
                    injected=[False]
                    def inject(b):
                        if injected[0]:return False
                        if s.h.u(s.pe.ROOT_ADDR+6,1)!=1:
                            # The native movement handler draws before H08.
                            # Wait for the requested draw inside real inflight.
                            return False
                        assert s.h.u(s.pe.ROOT_ADDR+6,1)==1,'cut must be inside real resident inflight'
                        assert b.core.psw&0x40,'nested native task requires IRQ enabled'
                        injected[0]=True
                        settings=s.h.u(0x200c0dac);before=s.h.b.read(settings,0xc9e)
                        other=shadow(s.h,s.v);at=len(s.p.rpc.log)
                        visited=other.b.visits[0x202bb96c]
                        nested=s.fr.move_key(other,0x1f if key=='UP' else 0x20,steps=30000000)
                        s.ux.need(nested)
                        after=s.h.b.read(settings,0xc9e)
                        record['nested']=dict(pc=hex(b.pc),psw=b.core.psw,rows=s.h.u(0x2022f5ac,1),
                            native_H08_visits=other.b.visits[0x202bb96c]-visited,extra_RPC=len(s.p.rpc.log)-at,
                            S_changes=[dict(offset=i,before=a,after=z) for i,(a,z) in enumerate(zip(before,after)) if a!=z],result=nested)
                        assert before==after,'native arrow changed S'
                        assert not record['nested']['native_H08_visits'] and not record['nested']['extra_RPC']
                        return False
                    try:
                        if cut=='entry':s.h.b.add_breakpoint(s.p.symbol_pc('ig_apply'),inject)
                        elif cut=='bind':s.h.b.add_breakpoint(ui_start,inject)
                        elif cut=='before_redraw':s.h.b.add_breakpoint(s.p.symbol_pc('rv_native_draw'),inject)
                        elif cut=='row_draw':s.h.b.add_breakpoint(0x201ffb2c,inject)
                        else:
                            armed=[False]
                            def restored(b):
                                caller=b.core.r[14]
                                if not armed[0] and ui_start<=caller<ui_end:
                                    armed[0]=True;s.h.b.add_breakpoint(caller,inject)
                                return False
                            s.h.b.add_breakpoint(s.p.symbol_pc('rv_irq_restore'),restored)
                        s.h.b.core.psw|=0x40
                        record['outer']=s.ux.need(s.fr.move_key(s.h,0x20,steps=30000000))
                        assert injected[0],('unreached cut',name,cut)
                        assert s.h.u(0x2022f5ac,1)==8
                        record.update(status='PASS',after=s.state(),native_UI=ui_audit(s.h),file_mutations=s.m.no_writes(s.p),rpc_log=s.p.rpc.log)
                    except BaseException:
                        record.update(status='FAIL',error=traceback.format_exc(),rpc_log=s.p.rpc.log);code=1
                    save('local/view-reentry/'+args.unit+'-'+name+'-'+cut+'-'+key+'.json',record)
                    print(args.unit,name,cut,key,record['status'],record.get('error','')[-500:],flush=True)
                    os._exit(code)
                _,status=os.waitpid(pid,0);results.append(dict(view=name,cut=cut,key=key,wait_status=status))
    view('L1')
    s.press('DISP');view('card')
    s.press('DISP');view('items')
    s.press('DISP');view('value')
    s.press('DISP');s.goto(2,0);s.press('DISP');s.goto(1,0);s.press('DISP');s.goto(0,9);s.press('DISP');view('groups')
    s.press('DISP');view('entries')
    s.goto(5,0);s.press('DISP');s.goto(4,0);s.press('DISP');s.goto(0,4);s.press('OK');s.reopen()
    original=s.p.rpc.call;failed=[False]
    def fault(command,value):
        if command==22 and not failed[0]:
            result=original(command,value);s.p.rpc.log[-1].update(device_result=result,result=-1,simulated=True);failed[0]=True;return -1
        if failed[0]:
            s.p.rpc.log.append(dict(cmd=command,value=value,page=s.p.rpc.page,result=-1,t=s.p.rpc.t,simulated=True));return -1
        return original(command,value)
    s.p.rpc.call=fault;s.press('DOWN');s.p.rpc.call=original
    assert s.state()['failed'];view('ERR')
    target=OUT/'evidence'/('view-reentry-'+args.unit+'.json')
    if set(args.cuts)!=set(CUTS) and target.exists():
        previous=json.loads(target.read_text())
        assert previous['dat_sha256']==sha(s.p.dat)
        results=([row for row in previous['cases'] if row['cut'] not in args.cuts]+results)
    save('evidence/view-reentry-'+args.unit+'.json',dict(status='PASS' if all(x['wait_status']==0 for x in results) else 'FAIL',
        dat_sha256=sha(s.p.dat),cases=results,screen_count=7,cut_count=5,keys=['UP','DOWN'],native_UI_hand_seeded=False))
    assert all(x['wait_status']==0 for x in results),results

if __name__=='__main__':main()
