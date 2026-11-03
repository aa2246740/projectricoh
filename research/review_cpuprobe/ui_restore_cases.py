"""Check the native cursor cache as well as the two published cursor bytes."""
from pathlib import Path
import json
import signal
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import review_scope as scope
import accept_cpuprobe as cp

CACHE=0x205A2944
STATE=0x205A293C


def native_fragment(s, cache):
    """Execute exactly the stock cache-to-cursor store, without navigation or drawing."""
    registers={f'r{i}':s.h.b.get_reg(f'r{i}') for i in range(16)}
    psw=s.h.b.get_reg('psw')
    pc=s.h.b.get_reg('pc')
    state=s.h.u(STATE)
    old=s.h.u(state+10,1)
    old_cache=s.h.u(CACHE,1)
    s.h.put(CACHE,cache,1)
    done=s.h.b.call(0x201CA75C,(),0x30000100,7)
    value=s.h.u(state+10,1)
    assert done.reason=='max_steps' and done.pc==0x201CA778,(done.reason,hex(done.pc))
    assert value==cache,(value,cache)
    s.h.put(state+10,old,1)
    s.h.put(CACHE,old_cache,1)
    for name,v in registers.items():s.h.b.set_reg(name,v)
    s.h.b.set_reg('psw',psw)
    s.h.b.set_reg('pc',pc)
    return dict(start='0x201CA75C',end='0x201CA778',instruction_words=7,
                stop_reason=done.reason,cache=cache,native_state=hex(state),
                cursor_address=hex(state+10),cursor_before=old,cursor_after=value,
                scope='Bounded stock instruction fragment; not a complete physical key event.')


def main():
    signal.alarm(1200)
    start=time.monotonic()
    scope.freeze_check()
    s=cp.Session('50mm')
    s.h.b.set_reg('psw',s.h.b.get_reg('psw')|0x40)
    writes=[]
    phase=['setup']
    def trace(e):
        writes.append(dict(phase=phase[0],value=e.value,pc=hex(e.pc) if e.pc is not None else None,
                           engine_offset=hex(e.pc-s.p.image_base) if e.pc is not None and
                           s.p.image_base<=e.pc<s.p.image_base+s.layout['engine_bytes'] else None))
    s.h.b.add_write_trace(CACHE,CACHE+1,trace)
    cases=[]
    tests=[('as_prepared',0x23,None),('positive_control',0x23,1),('cursor_two',0x23,2),
           ('cursor_five',0x23,5),('adj',0x2B,7),('half_0d',0x0D,7),
           ('half_29',0x29,7),('half_63',0x63,7)]
    fragment=None
    for label,key,value in tests:
        phase[0]=label+':fixture'
        if value is not None:
            # Consistent legal native cursor/cache prestate; not a corrupt pointer fixture.
            s.h.put(cp.CUR_A,value,1);s.h.put(cp.CUR_B,value,1);s.h.put(CACHE,value,1)
        before=s.native()
        cache_before=s.h.u(CACHE,1)
        state_before=s.h.u(STATE)
        phase[0]=label+':open'
        opened=s.open()
        assert opened['rows']==8,opened
        cache_open=s.h.u(CACHE,1)
        phase[0]=label+':close'
        s.press(key)
        after=s.native()
        cache_after=s.h.u(CACHE,1)
        assert after==before,(label,before,after)
        restored=cache_after==cache_before
        assert restored==(cache_before==1),(label,cache_before,cache_after)
        row=dict(label=label,key=hex(key),before=before,after=after,
                 cache_before=cache_before,cache_open=cache_open,cache_after=cache_after,
                 cache_restored=restored,state_before=hex(state_before),state_after=hex(s.h.u(STATE)))
        cases.append(row)
        print('RESTORE',json.dumps(row),flush=True)
        if label=='as_prepared':
            assert before['a']==before['b']==cache_before==7
            phase[0]='bounded_native_reader'
            fragment=dict(residual_cache=native_fragment(s,cache_after),
                          original_cache=native_fragment(s,cache_before))
    original=scope.ROOT/'firmware/engine_probe_p1/candidate/containers/product/probe.c'
    candidate=cp.PRODUCT/'probe.c'
    marker='RV_BYTE(0x205a2944)=1;'
    inherited=marker in original.read_text() and marker in candidate.read_text()
    assert inherited
    report=dict(status='RESTORE_COUNTEREXAMPLE_CONFIRMED',dat=scope.sha(cp.DAT),cases=cases,
                cache_writes=writes,
                cache_restore_failures=sum(not c['cache_restored'] for c in cases),
                positive_controls=sum(c['cache_restored'] for c in cases),
                native_reader=fragment,inherited_from_gen141=True,
                source_store=marker,gen141_source_sha256=scope.sha(original),
                candidate_source_sha256=scope.sha(candidate))
    cp.final_audit(s,report)
    report['elapsed_seconds']=time.monotonic()-start
    scope.save(HERE/'ui-restore-cases.json',report)
    print('RESTORE_COUNTEREXAMPLES',report['cache_restore_failures'],flush=True)


if __name__=='__main__':main()
