"""Bounded actual-M32R B checks, with no devices, traps, or native passthrough."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('bv4_machine_builder',HERE/'build.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
sys.path.insert(0,str(b.ROOT/'tools/native_harness'))
import python_backend as backend
backend.CACHE=b.REPORT/'local/arch-b-m32r-decode'


def main():
    b.b.preflight();e=b.b.Elf(b.LOCAL/'window.elf')
    layout=json.loads((b.REPORT/'arch-b-abi.json').read_text())
    payload=next(s for s in e.sections if s['name']=='.payload')
    inputs=[HERE/'test_machine.py']
    inputs += [b.ROOT/'tools/native_harness'/n for n in ('python_backend.py','backend_api.py','image_loader.py')]
    inputs += [b.ROOT/'research/emulator_feasibility_r1/prototype/boot_probe.py']
    before={str(p.relative_to(b.ROOT)):b.b.sha(p) for p in inputs};cases=[]
    def machine():
        m=backend.PythonBackend();m.map(0x20000000,bytes(0x800000))
        m.map(payload['address'],e.content(payload),writable=False)
        for n in range(16):m.set_reg('r'+str(n),0x1000+n*0x111)
        m.set_reg('r15',0x207f0000);m.core.psw=0x40
        return m
    def field(m,name,value):m.write(0x20054600+layout['Bv4Root.'+name],(value&0xffffffff).to_bytes(4,'big'))
    m=machine();m.write(0x20054600,bytes([255])*512)
    forbidden=[0x200a40b4,0x200a449c,0x200a437c,0x2005bf5c,0x2005c038]
    for pc in forbidden:m.add_breakpoint(pc,lambda _:True)
    stop=m.call(e.symbols['bv4_boot']['value'],[0x20054600],0x207e0000,10000)
    assert stop.reason=='return' and m.get_reg('r0')==((-14)&0xffffffff),(stop,list(m.tail))
    assert m.read(0x20054600,512)==bytes([255])*512 and not any(m.visits[pc] for pc in forbidden)
    cases.append(dict(case='actual_target_unknown_profile_blocks_boot_before_io',status='PASS',steps=stop.steps))
    official=(b.ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    outputs=[]
    for direct in (True,False):
        m=machine();m.write(0x20054600,bytes([255])*512)
        m.map(0x2010ddf8,b.at(official,0x2010ddf8,8),writable=False)
        m.add_breakpoint(0x2010de00,lambda _:True)
        for pc in forbidden:m.add_breakpoint(pc,lambda _:True)
        pc=0x2010ddf8 if direct else e.symbols['bv4_boot_native']['value']
        stop=m.call(pc,[],0x207e0000,20000)
        assert stop.reason=='breakpoint' and stop.pc==0x2010de00,(direct,stop,list(m.tail))
        assert m.read(0x20054600,512)==bytes([255])*512 and not any(m.visits[pc] for pc in forbidden)
        outputs.append(([m.get_reg('r'+str(i)) for i in range(16)],m.core.psw))
    assert outputs[0]==outputs[1],outputs
    cases.append(dict(case='native_boot_candidate_wrapper_exact_register_psw_stack_replay',status='PASS',installed=False))
    for n in (0,3,55,56,64,65,512):
        m=machine();raw=b'abc' if n==3 else bytes((i*37+11)&255 for i in range(n))
        m.write(0x20700000,raw)
        stop=m.call(e.symbols['bv4_sha256']['value'],[0x20700000,n,0x20710000],0x207e0000,1000000)
        assert stop.reason=='return',(n,stop,list(m.tail))
        assert m.read(0x20710000,32)==hashlib.sha256(raw).digest(),n
        assert m.get_reg('r15')==0x207f0000 and m.get_reg('r14')==0x207e0000
        cases.append(dict(case='actual_target_sha256',bytes=n,status='PASS',steps=stop.steps))
    # Exercise the real stock allocator, then demonstrate why an allocated
    # address/header cannot establish permanent ownership across heap reinit.
    m=machine()
    for address,n in ((0x2005bf00,0x5c),(0x2005bf5c,0xdc),(0x2005c038,0xd0)):
        m.map(address,b.at(official,address,n),writable=False)
    def word(address,value):m.write(address,(value&0xffffffff).to_bytes(4,'big'))
    def native_call(address,argument=None):
        if argument is not None:m.set_reg('r4',argument)
        stop=m.call(address,[],0x207e0000,1000000)
        assert stop.reason=='return',(hex(address),stop,list(m.tail))
        assert m.get_reg('r15')==0x207f0000
        return m.get_reg('r0')
    word(0x200c0dc0,0x20704800);word(0x200c0dc4,0x40000)
    native_call(0x2005bf00)
    first=native_call(0x2005bf5c,81920);assert first
    extent=int.from_bytes(m.read(first-4,4),'big')
    marker=bytes((i*11+3)&255 for i in range(64));m.write(first,marker)
    second=native_call(0x2005bf5c,72560);assert second and second>=first+81920
    native_call(0x2005c038,second);third=native_call(0x2005bf5c,4096)
    assert third and third>=first+81920 and m.read(first,64)==marker
    stop=m.call(e.symbols['rv4_allocation']['value'],[first,81920,extent],0x207e0000,10000)
    assert stop.reason=='return' and m.get_reg('r0')==1
    bounds=m.read(0x200d3488,8)
    cases.append(dict(case='actual_stock_allocator_keeps_held_block_out_of_other_allocations',status='PASS',
                      held_request=81920,held_extent=extent,adjacent_request=72560,hardware=False))
    native_call(0x2005bf00);reused=native_call(0x2005bf5c,81920)
    assert reused==first,(hex(first),hex(reused))
    assert m.read(0x200d3488,8)==bounds
    stop=m.call(e.symbols['rv4_allocation']['value'],[first,81920,extent],0x207e0000,10000)
    assert stop.reason=='return' and m.get_reg('r0')==1
    cases.append(dict(case='actual_stock_heap_reinit_counterexample_to_permanent_ownership',status='PASS',
                      same_address_reissued=True,bounds_unchanged=True,allocation_header_check_still_passes=True,
                      old_content_still_present=m.read(first,64)==marker,
                      runtime_reinit_occurrence_proven=False,hardware=False))
    old=json.loads((b.ROOT/'firmware/resident_v36/local/resident/hooks.json').read_text())
    for h in old:
        n=h['number']
        if n not in (1,2,5,6,7,8,9):continue
        target=int(h['replay_resume'],16);outputs=[]
        for direct in (True,False):
            m=machine();field(m,'magic',0x42345631);field(m,'state',3);field(m,'flags',8)
            m.map(int(h['va'],16),bytes.fromhex(h['original_bytes']),writable=False)
            m.add_breakpoint(target,lambda _:True)
            pc=int(h['va'],16) if direct else e.symbols[f'bv4_hook_{n:02}']['value']
            stop=m.call(pc,[],0x207e0000,20000)
            assert stop.reason=='breakpoint' and stop.pc==target,(n,direct,stop,list(m.tail))
            outputs.append(([m.get_reg('r'+str(i)) for i in range(16)],m.core.psw))
        assert outputs[0]==outputs[1],(n,outputs)
        cases.append(dict(case='factory_replay_matches_official_overwritten_instructions',hook=f'H{n:02}',status='PASS'))
    for hook,target in ((6,0x202be6a8),(8,0x202bcf58)):
        for state in ('unknown_root','extension_fault'):
            m=machine()
            if state=='extension_fault':field(m,'magic',0x42345631);field(m,'state',3);field(m,'flags',2)
            m.add_breakpoint(target,lambda _:True)
            original=[m.get_reg('r'+str(i)) for i in range(16)]
            stop=m.call(e.symbols[f'bv4_hook_{hook:02}']['value'],[],0x207e0000,20000)
            assert stop.reason=='breakpoint' and stop.pc==target,(hook,state,stop,list(m.tail))
            assert m.get_reg('r15')==0x207f0000 and m.get_reg('r14')==0x207e0000 and m.core.psw==0x40
            assert m.get_reg('r8')==0
            for i in (0,1,2,3,4,5,6,7,9,10,11,12,13):assert m.get_reg('r'+str(i))==original[i]
            cases.append(dict(case='permanent_fallback_after_unknown_or_extension_fault',hook=f'H{hook:02}',state=state,status='PASS',steps=stop.steps))
    assert {str(p.relative_to(b.ROOT)):b.b.sha(p) for p in inputs}==before
    result=dict(status='PASS_BOUNDED_ACTUAL_M32R',total=len(cases),cases=cases,
                exact_window_elf_sha256=b.b.sha(b.LOCAL/'window.elf'),address=hex(payload['address']),
                native_passthrough=False,hardware=False,full_native_lifecycle=False,
                full_extension_execution=False,inputs=before)
    b.b.write(b.REPORT/'arch-b-machine-tests.json',result)
    print(json.dumps({k:result[k] for k in ('status','total','address','native_passthrough','hardware')},indent=2))


if __name__=='__main__':main()
