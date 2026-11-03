"""Only the newly adjudicated lock-display cases, on the final DAT."""
from pathlib import Path
import argparse,json,os,re,sys,traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from run_cases import prepare
from safety_cases import shadow

NAMES=('write_latch','d2_four_failures','d2_persistent','reason_cursor',
       'panel_mid_lock','unowned_list','unowned_panel','lost_during_republish')

def run(name,fixture,record):
    ux,m,fr,pe,v,h,p,w,prepared=fixture
    record.update(prepared)
    layout=json.loads((OUT/'local/layout/current-adapter-layout.json').read_text())
    core=json.loads((OUT/'local/layout/layout.json').read_text())
    scope=load(MATERIALS/'ui_trace_scope.py','lock_ui_scope')
    adapter=p.symbol_pc('n');g=p.symbol_pc('g')
    if name in ('panel_mid_lock','unowned_panel'):ux.need(fr.native(h,0x202be220))
    before=ux.snap(h,p);original=p.rpc.call;at=len(p.rpc.log)
    seen=[0];locked=[False];switched=[False];after_switch=[None]
    texts=[];draws=[];late=[];later=[];primary=[True];irqs=[];reasons=[]
    code_low=p.image_base+256;code_high=code_low+len((TREE/'candidate/local/full-r13/engine.bin').read_bytes())
    ui=before['root']['ui_block']
    def is_ui(e):return scope.touches_ui(e) or ui<=e.address<ui+1980
    def flag(e):
        if e.value==1:locked[0]=True
    h.b.add_write_trace(adapter+layout['failed'],adapter+layout['failed']+1,flag)
    def reason_entry(bb):
        if not h.u(adapter+layout['failed'],1) and h.u(g+core['uncertain'],1) and h.u(g+core['write_started'],1):
            reasons.append(dict(entry=h.u(adapter+layout['entry'],1),stage=h.u(g+core['stage'],1),
                status=bb.core.r[0],sequence=h.u(adapter+layout['rpc_sequence'])))
        return False
    h.b.add_breakpoint(p.symbol_pc('record_failure'),reason_entry)

    def watch(e):
        if switched[0] and e.origin=='cpu' and code_low<=e.pc<code_high and is_ui(e):
            (late if primary[0] else later).append(dict(address=hex(e.address),pc=hex(e.pc),data=e.data.hex()))
    h.b.add_write_trace(0,2**32,watch)
    def switch():
        other=shadow(h,v);other.run_slice(0x202ba380,0x202ba3c8);other.leave_other_list()
        after_switch[0]=ux.snap(h,p);switched[0]=True
    def text(bb):
        if h.u(adapter+layout['failed'],1):
            texts.append(bb.read(bb.core.r[0],bb.core.r[1]).decode('ascii'))
            if name=='lost_during_republish' and not switched[0]:switch()
        return False
    def draw(bb):
        if locked[0]:
            state=bb.core.r[13];draws.append(dict(rows=h.u(0x2022f5ac,1),marker=h.u(state+9,1),cursor=h.u(state+10,1)))
        return False
    h.b.add_breakpoint(p.symbol_pc('rv_native_ascii'),text)
    h.b.add_breakpoint(0x201ffb2c,draw)
    h.b.add_breakpoint(p.symbol_pc('rv_irq_save'),lambda b:irqs.append(dict(op='save',psw=b.core.psw)) or False)
    h.b.add_breakpoint(p.symbol_pc('rv_irq_restore'),lambda b:irqs.append(dict(op='restore',argument=b.core.r[0])) or False)
    first_w=name in ('write_latch','panel_mid_lock','unowned_list','unowned_panel','lost_during_republish')
    fired=[False]
    def fault(cmd,value):
        seen[0]+=1
        if not fired[0] and ((first_w and cmd==22) or (not first_w and seen[0]==16)):
            result=original(cmd,value);fired[0]=True
            p.rpc.log[-1].update(device_result=result,result=-1,simulated=True)
            record['event_W_at_fault']=sum(x['cmd']==22 for x in p.rpc.log[at:])
            assert cmd==22,(name,'chosen partial-W point must be W',seen[0],cmd)
            if name.startswith('unowned_'):switch()
            return -1
        if fired[0] and (name!='d2_four_failures' or seen[0]<=19):
            p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True));return -1
        return original(cmd,value)
    p.rpc.call=fault
    event=ux.need(fr.move_key(h,0x20,steps=30000000));p.rpc.call=original
    after=ux.snap(h,p);primary[0]=False
    record.update(case=name,unit=p.unit,dat_sha256=sha(p.dat),before=before,after=after,event=event,
        calls=seen[0],fault_fired=fired[0],locked=locked[0],ascii_after_lock=texts,draws_after_lock=draws,
        switched=switched[0],after_switch=after_switch[0],late_DAT_ui_writes=list(late),primary_irq_calls=list(irqs))
    assert fired[0]
    stack=[]
    for e in irqs:
        if e['op']=='save':stack.append(e['psw'])
        else:assert stack and stack.pop()==e['argument'],irqs
    assert not stack,irqs
    if name=='d2_four_failures':
        assert seen[0]>19 and not h.u(adapter+layout['failed'],1)
        assert not after['list']['uncertain'] and after['rows']==8
        record['actual_after_recovery']=ux.matches(h,p,5)
        record['reopened']=m.reopen(h,p,w);record['actual_reopened']=ux.matches(h,p,5)
        assert not texts and not locked[0]
    else:
        assert locked[0] and h.u(adapter+layout['failed'],1)==1 and after['list']['uncertain']==1
        reason=h.b.read(adapter+layout['failed_text'],15).split(b'\0',1)[0].decode('ascii')
        assert reasons,reasons
        witness=reasons[0]
        expected='ERR '+str(witness['entry'])+str(witness['stage'])+str(witness['status'])+'.'+format(witness['sequence']&255,'02X')+' OFF'
        record['reason_witness']=witness
        assert reason==expected and re.fullmatch(r'ERR [0-9]{3}\.[0-9A-F]{2} OFF',reason),(reason,expected)
        record['reason']=reason
        if name in ('d2_persistent','reason_cursor'):
            complete=[]
            for slot in range(1,9):
                try:ux.matches(h,p,slot)
                except AssertionError:pass
                else:complete.append(slot)
            record['matching_complete_recipes_after_partial_W']=complete
            assert not complete,complete
        if switched[0]:
            assert not late,late
            assert after['native_activity']==after_switch[0]['native_activity']==7
            assert after['native_overlay']==after_switch[0]['native_overlay']==21
            assert (after['cursor'],after['dot_row'],after['rows'])==(after_switch[0]['cursor'],after_switch[0]['dot_row'],after_switch[0]['rows'])
        else:
            assert after['rows']==after['cursor']==after['dot_row']==h.u(0x205a2944,1)==1,after
            assert after['native_snapshot_rows']==[1,1]
            assert texts and all(x==reason for x in texts),texts
            assert draws and all(x['rows']==x['marker']==x['cursor']==1 for x in draws),draws
            assert not h.u(adapter+layout['panel.open'],1) and not h.u(adapter+layout['panel.input_enabled'],1)
            ui=after['root']['ui_block'];record['ERR_glyph_hex']=h.b.read(ui+424,96).split(b'\0',1)[0].hex()
            assert record['ERR_glyph_hex']
        count=len(p.rpc.log)
        if not switched[0]:
            for key in (0x20,0x1f):ux.need(fr.move_key(h,key))
            ux.need(fr.native(h,0x202be220))
            ux.need(fr.press(h,0x23))
        h.parent();opened,_,error=fr.publish(h,p,w);ux.need(opened);assert error is None,error
        reopened=ux.snap(h,p)
        assert reopened['rows']==reopened['cursor']==reopened['dot_row']==1
        assert len(p.rpc.log)==count,'No communication after the permanent latch'
        record.update(next_H01=reopened,no_more_RPC_after_lock=True,next_H01_reason=reason)
    record['next_H01_DAT_ui_writes']=later
    record['all_irq_calls']=irqs
    record['rpc_log']=p.rpc.log
    record['file_mutations']=m.no_writes(p);record['native_UI']=ui_audit(h)
    assert not record['native_UI']['host_ui_writes'] and not record['native_UI']['getter_callback_present']
    record['status']='PASS'

def main(unit,only=None):
    args=argparse.Namespace(generation=123,unit=unit,case='locked-display')
    fixture=prepare(args);results=[]
    names=only or NAMES
    for name in names:
        sys.stdout.flush();pid=os.fork()
        if pid==0:
            r={};code=0
            try:run(name,fixture,r)
            except BaseException:r.update(status='FAIL',error=traceback.format_exc());code=1
            save('local/lock-cases/'+unit+'-'+name+'.json',r)
            print(name,r['status'],r.get('error','')[-700:],flush=True);os._exit(code)
        _,status=os.waitpid(pid,0);results.append(dict(case=name,wait_status=status))
    save('evidence/locked-'+('ownership-' if only else '')+unit+'.json',dict(status='PASS' if all(x['wait_status']==0 for x in results) else 'FAIL',
        unit=unit,dat_sha256=file_sha(DAT),cases=results))
    assert all(x['wait_status']==0 for x in results),results
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('unit',choices=('50mm','28mm','mount'));parser.add_argument('--only',nargs='+',choices=NAMES)
    args=parser.parse_args();main(args.unit,args.only)
