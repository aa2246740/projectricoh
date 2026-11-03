"""Run the actual M32R H06/H08 thunks at a nonoverlapping host-test address.

The production-address diagnostic ELF is oversized and cannot run with its root.
The same object files are relinked at 0x21000000 for this bounded interpreter.
No firmware image is emitted and no device/trap passthrough is available.
"""
from pathlib import Path
import importlib.util
import json
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('rv4_machine_builder',HERE/'build.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
sys.path.insert(0,str(b.ROOT/'tools/native_harness'))
import python_backend as backend
backend.CACHE=b.REPORT/'local/m32r-decode'


def main():
    b.preflight()
    inputs=[HERE/'test_machine.py']
    inputs += [b.ROOT/'tools/native_harness'/n for n in ('python_backend.py','backend_api.py','image_loader.py')]
    inputs += [b.ROOT/'research/emulator_feasibility_r1/prototype/boot_probe.py']
    before={str(p.relative_to(b.ROOT)):b.sha(p) for p in inputs}
    e=b.Elf(b.LOCAL/'resident-host-machine.elf')
    layout=json.loads((HERE/'generated/target-layout.json').read_text())
    payload=next(s for s in e.sections if s['name']=='.payload')
    assert payload['address']==0x21000000
    cases=[]
    for hook,target,replay in [(6,0x202be6a8,0x202be250),(8,0x202bcf58,0x202bb96c)]:
        for rows in (1,2,7,8,11,16,19):
            for gate in ('inflight','owner_unknown','disabled','retiring'):
                for key in (0x1f,0x20):
                    m=backend.PythonBackend();m.map(0x20000000,bytes(0x800000))
                    m.map(payload['address'],e.content(payload),writable=False)
                    def word(address,value):m.write(address,(value&0xffffffff).to_bytes(4,'big'))
                    def field(name,value):word(0x20054600+layout['Rv4Root.'+name],value)
                    field('header.magic',0x52563430);field('header.version',4);field('header.state',4 if gate=='disabled' else 3)
                    field('header.flags',1 if gate=='disabled' else 0)
                    field('header.inflight',1 if gate=='inflight' else 0)
                    field('view.ticket',0x41);field('view.rows',rows)
                    if gate=='retiring':field('view.retiring',0x41);field('draw.frame_pins',1)
                    m.write(0x2022f5ac,bytes([rows]));m.write(0x2022f725,b'\x01\x01')
                    settings=0x20650000;m.write(settings,bytes([1])*0xc9e);word(0x200c0dac,settings)
                    writes=[];m.add_write_trace(settings,settings+0xc9e,lambda event:writes.append(dict(address=hex(event.address),pc=hex(event.pc or 0))))
                    for pc in (target,replay,0x20268774):m.add_breakpoint(pc,lambda _:True)
                    for n in range(16):m.set_reg('r'+str(n),0x1000+n*0x111)
                    m.set_reg('r8',key);m.set_reg('r15',0x207f0000);m.core.psw=0x40
                    original=[m.get_reg('r'+str(n)) for n in range(16)]
                    stop=m.call(e.symbols[f'rv4_hook_{hook:02}']['value'],(),0x207e0000,200000)
                    assert stop.reason=='breakpoint' and stop.pc==target,(hook,rows,gate,key,stop,list(m.tail))
                    assert not writes and not m.visits[replay] and not m.visits[0x20268774]
                    assert m.get_reg('r15')==0x207f0000 and m.get_reg('r14')==0x207e0000
                    assert m.core.psw==0x40 and m.get_reg('r8')==0
                    for n in (0,1,2,3,4,5,6,7,9,10,11,12,13):
                        assert m.get_reg('r'+str(n))==original[n],(n,m.get_reg('r'+str(n)),original[n])
                    cases.append(dict(hook=f'H{hook:02}',rows=rows,gate=gate,key=key,status='PASS',
                                      native_setter_visits=0,settings_writes=0,skip=hex(target),steps=stop.steps,
                                      sp_restored=True,lr_restored=True,psw_restored=True))
    after={str(p.relative_to(b.ROOT)):b.sha(p) for p in inputs};assert after==before
    result=dict(status='PASS',cases=cases,total=len(cases),native_setter_visits=0,
                settings_writes=0,model='bounded M32R interpreter, hook entry through safe native continuation',
                full_native_key_path=False,full_DAT_replay=False,hardware=False,
                code_address='0x21000000',same_compiled_objects=True,
                target_native_profile='UNKNOWN, no task probe or capability grant',
                elf_sha256=b.sha(b.LOCAL/'resident-host-machine.elf'),inputs=before)
    b.write(b.REPORT/'machine-tests.json',result)
    print(json.dumps({k:result[k] for k in ('status','total','native_setter_visits','settings_writes','code_address','same_compiled_objects')},indent=2))


if __name__=='__main__':main()
