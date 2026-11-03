"""P1 fault injection occurs after real H01, never as a successful boot seed."""
from pathlib import Path
import struct
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_probe as n

OUT=n.c.RESEARCH/'evidence/p1-native.json'
report=dict(status='RUNNING',dat_sha256=n.c.sha(n.DAT),cases=[],
    injection_scope='Normal cold H01 has no UI preseed. Matrix cases inject scalar faults only after actual H01 reaches the final capture guard. Rejected malformed states stop before stock replay.')
FIELDS=((0x2022f5a8,4),(0x2022f5ac,1),(0x2022f725,1),(0x2022f726,1))


def four(h):return [h.u(a,size) for a,size in FIELDS]


def main():
    h,p,w=n.boot()
    print('P1 genuine cold H01',flush=True)
    n.open_menu(h,p)
    n.require(n.fr.press(h,0x29))
    control={}
    def fault_write(address,value,size=4):
        old=h.b.origin;h.b.origin='fault-input'
        h.put(address,value,size);h.b.origin=old
    def trace(event):
        if not control.get('active') or event.origin=='fault-input':return
        if event.pc is not None and p.image_base+256<=event.pc<p.image_base+256+int.from_bytes(p.dat[136:140],'big'):
            if any(a<=event.address<a+size for a,size in FIELDS) or 0x205a27a0<=event.address<=0x205a27a8:
                control['writes'].append(dict(address=hex(event.address),bytes=len(event.data),value=event.value,pc=hex(event.pc)))
    h.b.add_write_trace(0,2**32,trace)
    def capture(b):
        if not control.get('active'):return False
        assert not (b.get_reg('psw')&0x40),'capture guard ran with IRQ enabled'
        if control.get('inject'):
            control['inject']();control['inject']=None
        control['raw']=four(h)
        control['restore_before']=[h.u(n.pe.ROOT_ADDR+156+4*i) for i in range(14)]
        ret=b.get_reg('r14')
        def returned(b):
            if control.get('waiting'):
                control['guard_result']=b.get_reg('r0');control['at_return']=four(h);control['waiting']=False
            return False
        control['waiting']=True
        h.b.add_breakpoint(ret,returned)
        return False
    h.b.add_breakpoint(p.image_base+p.elf.symbols['probe_p1_capture'],capture)
    def stop_replay(b):
        if control.get('active') and control.get('reject'):
            control['engine_returned']=True
            b.set_reg('r15',control['sp'])
            for index,value in enumerate(control['callee'],8):b.set_reg('r'+str(index),value)
            b.set_reg('pc',n.fr.END)
        return False
    h.b.add_breakpoint(0x202870a4,stop_replay)

    def case(name,inject=None,reject=False,expected=None,other_list=False):
        h.parent()
        if other_list:h.leave_other_list()
        original=[(a,h.b.read(a,size)) for a,size in FIELDS]
        original_views=h.b.read(0x205a279c,16)
        original_count=h.u(0x205a27d4,1)
        original_restore=h.b.read(n.pe.ROOT_ADDR+156,56)
        control.clear();control.update(active=True,inject=inject,reject=reject,writes=[],sp=h.b.get_reg('r15'),
            callee=[h.b.get_reg('r'+str(i)) for i in range(8,14)],name=name)
        result=n.fr.open_settings(h)
        n.require(result)
        if reject:
            assert control.get('guard_result')==0,(name,control,p.state())
            assert control['raw']==control['at_return'],(name,control)
            assert not control['writes'],(name,control)
            assert [h.u(n.pe.ROOT_ADDR+156+4*i) for i in range(14)]==control['restore_before'],(name,n.fr.root_fields(h))
            assert p.state()['error']==2,(name,p.state())
        else:
            assert control.get('guard_result')==1,(name,control,p.state())
            assert h.u(0x2022f5ac,1)==8,(name,p.state(),control)
            want=control['raw'] if expected is None else expected
            n.require(n.fr.press(h,0x29))
            assert four(h)==want,(name,want,four(h),control)
        record=dict(name=name,rejected=reject,guard=control.get('guard_result'),raw=control.get('raw'),
                    restored=None if reject else four(h),writes=control['writes'],steps=result['steps'],
                    stopped_before_stock_replay=control.get('engine_returned',False))
        report['cases'].append(record);n.c.save(OUT,report)
        control['active']=False
        if reject:
            # Undo only the test's injected fault after observing atomic rejection.
            for address,data in original:h.b.write(address,data)
            h.b.write(0x205a279c,original_views);h.put(0x205a27d4,original_count,1)
            h.b.write(n.pe.ROOT_ADDR+156,original_restore)
        return record

    for x in range(1,8):
        for y in range(1,8):
            case('cursor-%d-%d'%(x,y),lambda x=x,y=y:(fault_write(0x2022f725,x,1),fault_write(0x2022f726,y,1)))
        print('P1 legal pairs',x*7,flush=True)
    for value in (0,8,9,10,11,12,13,255):
        for address in (0x2022f725,0x2022f726):
            case('reject-%x-%d'%(address,value),lambda a=address,v=value:fault_write(a,v,1),True)
    for name,address,value,size in (
        ('thirteen-rows',0x2022f5ac,13,1),('unknown-table',0x2022f5a8,0x2022d614,4),
        ('wrong-view-array',0x205a27d8,0x205a27a4,4),('wrong-part',0x205a280f,1,1),
        ('wrong-view-tag',0x205a279c,31,1)):
        old=h.b.read(address,size)
        case(name,lambda a=address,v=value,s=size:fault_write(a,v,s),True)
        h.b.write(address,old)
    check_epoch=[h.u(n.pe.ROOT_ADDR+8+4*6)]
    def epoch_fault():fault_write(n.pe.ROOT_ADDR+8+4*6,check_epoch[0]+1)
    case('epoch-changes-between-glyph-and-capture',epoch_fault,True)
    h.put(n.pe.ROOT_ADDR+8+4*6,check_epoch[0])
    case('unknown-restore-record',lambda:fault_write(n.pe.ROOT_ADDR+156+13*4,1),True)
    case('unknown-tag33-state',lambda:fault_write(0x205a27a0,0x2022f71c+4),True,other_list=True)
    print('P1 invalid cursor, table, view and epoch cases',flush=True)
    # A direct UI_VIEW publish also reaches the same IRQ-protected capture.
    forced={}
    def force_view(b):
        if not forced.get('active') or b.get_reg('r0')!=10 or b.get_reg('r1')!=1:return False
        forced['active']=False;q=b.get_reg('r2');buf=h.u(q+48)
        ctx=h.u(p.state_address()+4)
        ui=h.u(ctx+64);ui_bytes=h.u(ctx+68);token=h.u(ctx+32)
        array=h.u(0x205a27d8);count=h.u(0x205a27d4,1);top=array+8*(count-1)
        raw=struct.pack('>HH11I',1,48,0,0,2,33,ui,ui_bytes,token,array,count,h.u(top,1),h.u(top+4))
        h.b.write(buf,raw);h.put(q+44,0);h.put(q+52,48);h.put(q+56,0)
        b.set_reg('r0',12)
        ret=b.get_reg('r14')
        def view_return(b):
            if forced.get('waiting'):
                forced['result']=n.pe.signed(b.get_reg('r0'));forced['slot']=h.u(top+4);forced['waiting']=False
            return False
        forced['waiting']=True;h.b.add_breakpoint(ret,view_return)
        return False
    h.b.add_breakpoint(p.image_base+p.elf.symbols['rv_call'],force_view)
    h.parent();h.leave_other_list();forced['active']=True
    n.require(n.fr.open_settings(h))
    assert forced.get('result')==0,forced
    assert forced.get('slot')==h.u(n.pe.ROOT_ADDR+136),forced
    n.require(p.engine(8,[]))
    assert h.u(n.pe.ROOT_ADDR+156)==0
    report['ui_view']=dict(forced,capture_shared=True,withdrawn=True)
    n.c.save(OUT,report)
    print('PASS UI_VIEW capture and exact withdrawal',flush=True)
    # Normal refresh with a foreign owner must not abort that owner.
    h.parent();n.open_menu(h,p)
    old=h.u(0x2022f5a8);foreign=old+4
    h.put(0x2022f5a8,foreign)
    before=four(h)
    # Call the engine's close with a valid ingress; it must refuse foreign names.
    n.require(p.engine(8,[]))
    assert four(h)==before
    h.put(0x2022f5a8,old);n.require(p.engine(8,[]))
    report['foreign_owner']=dict(not_aborted=True)
    assert not any(x['cmd']==22 for x in p.rpc.log)
    report.update(status='PASS',legal_pairs=49,invalid_cases=len(report['cases'])-49,unit_W=0,files=p.native_log)
    n.c.save(OUT,report);print('PASS P1 native',len(report['cases']),flush=True)


if __name__=='__main__':
    try:main()
    except BaseException:
        report['status']='FAIL';report['error']=traceback.format_exc();n.c.save(OUT,report)
        n.c.save(n.c.RESEARCH/('evidence/failures/p1-'+report['dat_sha256'][:12]+'.json'),report)
        raise
