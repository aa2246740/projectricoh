"""Re-enter every screen at each linked UI cut using all six native keys."""
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
KEYS=('UP','DOWN','DISP','OK','ADJ','HALF')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm')
    parser.add_argument('--cuts',nargs='+',choices=CUTS,default=CUTS)
    parser.add_argument('--keys',nargs='+',choices=KEYS,default=KEYS)
    parser.add_argument('--tag',default='')
    args=parser.parse_args()
    completed=OUT/('evidence/reentry-all-keys-'+args.unit+args.tag+'.json')
    if completed.exists() and set(args.cuts)==set(CUTS) and set(args.keys)==set(KEYS):
        old=json.loads(completed.read_text())
        if old.get('status')=='PASS' and old.get('dat_sha256')==file_sha(DAT) and len(old.get('cases',[]))==210:
            for row in old['cases']:
                raw=json.loads((OUT/('local/reentry-all-keys'+args.tag)/(row['case']+'.json')).read_text())
                assert raw['status']=='PASS' and raw['dat_sha256']==file_sha(DAT) and row['wait_status']==0
            print('Already verified 210 cases for final DAT:',args.unit,flush=True)
            return
    s=Session(args.unit,'reentry-all-keys')
    sequence=load(MATERIALS/'native_sequence.py','reentry_raw_sequence')
    sequence.device_edges(s.h,s.p)
    sequence.prepare_input(s.h)
    # RTOS service 400 answers whether this is normal task context. The
    # interpreter cannot execute the kernel trap; no menu value is supplied.
    s.h.stub(0x0500c6ec,'review_normal_task_context',value=0)
    def task_id(b):
        b.write(b.core.r[4],(6).to_bytes(2,'big'))
        return 0
    s.h.stub(0x0500c574,'review_task_id',task_id)
    os_messages=[]
    def submit(b):
        address,size=b.core.r[5],b.core.r[6]
        os_messages.append(dict(queue=b.core.r[4],size=size,message_sha256=sha(b.read(address,size)) if size<=512 else None))
        return 0
    s.h.stub(0x2005e034,'review_RTOS_message_submit',submit)
    s.reopen()
    s.press('DOWN');s.press('OK');s.reopen()
    sym=symbols(ELF);name=next(n for n in sym if n=='ui_list' or n.startswith('ui_list.'))
    ui=s.p.image_base+sym[name]['address'];ui_end=ui+sym[name]['size'];results=[]
    def screen(name):
        outer_key='DISP' if name=='value' else 'DOWN'
        for cut in args.cuts:
            for key in args.keys:
                label=args.unit+'-'+name+'-'+cut+'-'+key
                sys.stdout.flush();pid=os.fork()
                if pid==0:
                    record=dict(case=label,unit=args.unit,view=name,cut=cut,key=key,outer_key=outer_key,dat_sha256=sha(s.p.dat))
                    code=0;fired=[False];setters=[];mode_stores=[]
                    def insert_event(b):
                        if fired[0] or s.h.u(s.pe.ROOT_ADDR+6,1)!=1:return False
                        assert b.core.psw&0x40
                        fired[0]=True
                        settings=s.h.u(0x200c0dac);before=s.h.b.read(settings,0xc9e)
                        other=shadow(s.h,s.v);rpc=len(s.p.rpc.log);mark=s.w.mark()
                        for pc in (0x202871dc,0x20268768,0x20268774,0x202688d4):
                            other.b.add_breakpoint(pc,lambda bb,pc=pc:setters.append(hex(pc)) or False)
                        def mode_write(e):mode_stores.append(dict(pc=hex(e.pc),origin=e.origin,data=e.data.hex()))
                        other.b.add_write_trace(settings+0x36e,settings+0x36f,mode_write)
                        if key in ('UP','DOWN'):
                            result=s.fr.move_key(other,0x1f if key=='UP' else 0x20,steps=30000000)
                        elif key=='DISP':result=s.fr.native(other,0x202be220,steps=30000000)
                        elif key in ('OK','ADJ'):result=s.fr.press(other,0x23 if key=='OK' else 0x2b,steps=30000000)
                        else:
                            result=sequence.key(other,s.fr,0x0d)
                            assert result['logical']==0x29 and all(x['ok'] for x in result['dispatch'])
                        if key!='HALF':s.ux.need(result)
                        after=s.h.b.read(settings,0xc9e)
                        changes=[dict(offset=i,before=a,after=z) for i,(a,z) in enumerate(zip(before,after)) if a!=z]
                        record['nested']=dict(pc=hex(b.pc),psw=b.core.psw,rows=s.h.u(0x2022f5ac,1),
                            extra_RPC=len(s.p.rpc.log)-rpc,S_changes=changes,Image_setters=setters,
                            Image_mode_stores=mode_stores,result=result,resident_hooks=s.w.since(mark),OS_messages=list(os_messages))
                        assert not setters and not mode_stores
                        assert not record['nested']['extra_RPC']
                        if key!='HALF':assert not changes,changes
                        return False
                    try:
                        if cut=='entry':s.h.b.add_breakpoint(s.p.symbol_pc('ig_panel_open' if outer_key=='DISP' else 'ig_apply'),insert_event)
                        elif cut=='bind':s.h.b.add_breakpoint(ui,insert_event)
                        elif cut=='before_redraw':s.h.b.add_breakpoint(s.p.symbol_pc('rv_native_draw'),insert_event)
                        elif cut=='row_draw':s.h.b.add_breakpoint(0x201ffb2c,insert_event)
                        else:
                            armed=[False]
                            def restore(b):
                                caller=b.core.r[14]
                                if not armed[0] and ui<=caller<ui_end:
                                    armed[0]=True;s.h.b.add_breakpoint(caller,insert_event)
                                return False
                            s.h.b.add_breakpoint(s.p.symbol_pc('rv_irq_restore'),restore)
                        s.h.b.core.psw|=0x40
                        record['outer']=s.ux.need(s.fr.native(s.h,0x202be220,steps=30000000) if outer_key=='DISP' else
                                                 s.fr.move_key(s.h,0x20,steps=30000000))
                        assert fired[0],('unreached cut',name,cut)
                        record.update(status='PASS',after=s.state(),native_UI=ui_audit(s.h),file_mutations=s.m.no_writes(s.p))
                    except BaseException:record.update(status='FAIL',error=traceback.format_exc());code=1
                    record['rpc_log']=s.p.rpc.log
                    save('local/reentry-all-keys'+args.tag+'/'+label+'.json',record)
                    print(label,record['status'],record.get('error','')[-600:],flush=True)
                    os._exit(code)
                _,status=os.waitpid(pid,0);results.append(dict(case=label,wait_status=status))
    # The matrix exercises the inflight publication cuts without re-running
    # an unrelated transaction in each fork. The inherited arrow matrix and
    # W-started lock tests separately exercise movement with transactions.
    s.goto(0,9);screen('L1');s.press('UP');s.press('DISP');screen('card');s.press('DISP');screen('items');s.press('DISP');screen('value')
    s.press('DISP');s.goto(2,0);s.press('DISP');s.goto(1,0);s.press('DISP');s.goto(0,9);s.press('DISP');screen('groups')
    s.press('DISP');screen('entries')
    s.goto(5,0);s.press('DISP');s.goto(4,0);s.press('DISP');s.goto(0,4);s.press('OK');s.reopen()
    orig=s.p.rpc.call;failed=[False]
    def fault(cmd,value):
        if cmd==22 and not failed[0]:
            result=orig(cmd,value);s.p.rpc.log[-1].update(device_result=result,result=-1,simulated=True);failed[0]=True;return -1
        if failed[0]:s.p.rpc.log.append(dict(cmd=cmd,value=value,page=s.p.rpc.page,result=-1,t=s.p.rpc.t,simulated=True));return -1
        return orig(cmd,value)
    s.p.rpc.call=fault;s.press('DOWN');s.p.rpc.call=orig
    assert s.state()['failed'];screen('ERR')
    save('evidence/reentry-all-keys-'+args.unit+args.tag+'.json',dict(status='PASS' if all(x['wait_status']==0 for x in results) else 'FAIL',
        dat_sha256=sha(s.p.dat),unit=args.unit,cases=results,cuts=list(args.cuts),keys=list(args.keys),
        fixture='Official native input task prologue and raw 0x0d half press. RTOS service 400 returns normal task context; service 380 returns native menu task 6; native message submission records the message and returns success. L1 starts at MyRec; numeric outer action is DISP.'))
    assert all(x['wait_status']==0 for x in results)

if __name__=='__main__':
    from completed import reuse
    if not reuse(Path(__file__).stem,sys.argv[1:]):
        main()
