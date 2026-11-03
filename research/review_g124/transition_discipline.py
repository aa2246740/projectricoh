"""Observe every row-count write across all seven views' native exit paths."""
from pathlib import Path
import argparse
import os
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ui_test_support import *

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--irq-enabled',action='store_true');args=parser.parse_args()
    suffix='-irq' if args.irq_enabled else ''
    s=Session('50mm','row-transition');s.press('DOWN');s.press('OK');s.reopen();results=[]
    def view(name):
        for key in ('OK','ADJ','HALF'):
            sys.stdout.flush();pid=os.fork()
            if pid==0:
                record=dict(unit='50mm',view=name,key=key,dat_sha256=sha(s.p.dat));code=0
                counts=[];setters=[]
                def row(e):
                    counts.append(dict(pc=hex(e.pc),value=e.value,PSW=s.h.b.core.psw,
                        inflight=s.h.u(s.pe.ROOT_ADDR+6,1),ui_restore0=s.h.u(s.pe.ROOT_ADDR+156)))
                s.h.b.add_write_trace(0x2022f5ac,0x2022f5ad,row)
                for pc in (0x202871dc,0x20268768,0x20268774):
                    s.h.b.add_breakpoint(pc,lambda b,pc=pc:setters.append(hex(pc)) or False)
                try:
                    if args.irq_enabled and key!='HALF':s.h.b.core.psw|=0x40
                    before=s.state();assert before['rows']==8
                    after=s.press(key)
                    assert not setters
                    assert all(x['value'] in (7,8) for x in counts)
                    assert all(x['value']==8 or not (x['PSW']&0x40) for x in counts),'7-row withdrawal must be IRQ protected'
                    root=s.fr.root_fields(s.h)
                    if after['rows']==7:assert root['ui_restore0']==0
                    else:assert key=='HALF' and after['overlay']==0
                    record.update(status='PASS',before=before,after=after,row_count_stores=counts,
                        Image_setters=setters,root=root,native_UI=ui_audit(s.h),file_mutations=s.m.no_writes(s.p))
                except BaseException:record.update(status='FAIL',error=traceback.format_exc());code=1
                record['IRQ_enabled_at_input']=bool(args.irq_enabled and key!='HALF')
                save('local/row-transitions'+suffix+'/50mm-'+name+'-'+key+'.json',record)
                print(name,key,record['status'],record.get('error','')[-600:],flush=True);os._exit(code)
            _,status=os.waitpid(pid,0);results.append(dict(view=name,key=key,wait_status=status))
    view('L1');s.press('DISP');view('card');s.press('DISP');view('items');s.press('DISP');view('value')
    s.press('DISP');s.goto(2,0);s.press('DISP');s.goto(1,0);s.press('DISP');s.goto(0,9);s.press('DISP');view('groups')
    s.press('DISP');view('entries')
    s.goto(5,0);s.press('DISP');s.goto(4,0);s.press('DISP');s.goto(0,4);s.press('OK');s.reopen()
    original=s.p.rpc.call;failed=[False]
    def fault(cmd,value):
        if cmd==22 and not failed[0]:
            result=original(cmd,value);s.p.rpc.log[-1].update(device_result=result,result=-1,simulated=True);failed[0]=True;return -1
        if failed[0]:s.p.rpc.log.append(dict(cmd=cmd,value=value,page=s.p.rpc.page,result=-1,t=s.p.rpc.t,simulated=True));return -1
        return original(cmd,value)
    s.p.rpc.call=fault;s.press('DOWN');s.p.rpc.call=original;assert s.state()['failed'];view('ERR')
    save('evidence/row-transitions-50mm'+suffix+'.json',dict(status='PASS' if all(x['wait_status']==0 for x in results) else 'FAIL',
        dat_sha256=sha(s.p.dat),unit='50mm',cases=results,
        scope='Eight rows throughout the owned views. A completed withdrawal restores the official seven-row list under IRQ; raw half-close can leave an unowned hidden eight-row descriptor until next constructor.'))
    assert all(x['wait_status']==0 for x in results)
if __name__=='__main__':main()
