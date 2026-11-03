"""Execute final timing wrappers with hostile callee register clobbering."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_probe as n
import check_native as flow


def main():
    h,p,w=n.boot();n.open_menu(h,p);cases=[]
    original_callee=[h.b.get_reg('r'+str(i)) for i in range(8,14)]
    clobber=[False]
    def hostile_tick(b):
        if clobber[0]:
            for i in range(8,14):b.set_reg('r'+str(i),0xee000000+i)
        return False
    h.b.breakpoints[0x2005f164].insert(0,hostile_tick)
    for name,args in (('p0_tick',()),('p0_empty',(0,0,0,0)),('p0_decrement',(0,16384,0,0))):
        expected=[0x5a000000+i for i in range(8,14)]
        for i,value in enumerate(expected,8):h.b.set_reg('r'+str(i),value)
        before_sp=h.b.get_reg('r15');before_ie=h.b.get_reg('psw')&0x40
        clobber[0]=name=='p0_tick'
        result=n.require(p.call(p.image_base+p.elf.symbols[name],args))
        after=[h.b.get_reg('r'+str(i)) for i in range(8,14)]
        assert after==expected and h.b.get_reg('r15')==before_sp and h.b.get_reg('psw')&0x40==before_ie
        cases.append(dict(function=name,callee_registers_preserved=True,stack_preserved=True,IRQ_preserved=True,result=result))
    for i,value in enumerate(original_callee,8):h.b.set_reg('r'+str(i),value)
    event_input={};event_results=[]
    def event(b):
        if event_input.get('armed'):
            event_input['armed']=False;q=b.get_reg('r2')
            h.put(q+44,event_input['keep']);h.put(q+56,event_input['caller']);h.put(q+60,event_input['reason'])
        return False
    h.b.add_breakpoint(p.image_base+p.elf.symbols['p0_event'],event)
    for caller in (0x202c2d74,0x202c2d84,0x202c2d70):
        for keep in (0,1):
            flow.select(h,p,2);n.reopen(h,p);p.ticks=(p.state()['ref_start']+30000)&0xffffffff
            event_input.update(armed=True,caller=caller,keep=keep,reason=0x23)
            n.require(n.fr.press(h,0x23));state=p.state()
            accepted=caller in (0x202c2d74,0x202c2d84)
            assert (state['phase']==3 and state['ref_count']>0) if accepted else (state['phase']==7 and state['ref_count']==0)
            assert h.u(0x2022f5ac,1)==7
            event_results.append(dict(caller=hex(caller),keep=keep,accepted=accepted,state=state,native_keep0_closed=True))
            n.reopen(h,p)
    assert not p.rpc.overlay and not any(row['cmd']==22 for row in p.rpc.log)
    n.c.save(n.c.RESEARCH/'evidence/native-contracts.json',dict(status='PASS',dat_sha256=n.c.sha(n.DAT),cases=cases,
        wrapper_native_tick_clobbered_r8_to_r13=True,lr_returned_through_real_wrapper=True,
        event_argument_injection_after_real_H07=event_results))
    print('PASS native timing wrappers, stack, r8..r13 and IRQ')


if __name__=='__main__':main()
