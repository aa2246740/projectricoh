"""Execute the changed observer/ownership instructions and reject v3.2."""
import importlib.util
import itertools
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('entry_policy',HERE/'policy_machine.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


def observe(program,hook,count,tag,row,state):
    cpu=p.fresh(program)
    cpu.seed(p.ROOT_ADDRESS+156,0x2022d610);cpu.seed(p.ROOT_ADDRESS+180,0x20724100)
    cpu.seed(0x2022f5a8,0x20724100);cpu.seed(0x205d9bf8,8);cpu.seed(0x205d9c00,56)
    cpu.seed(0x205a280f,2,1);cpu.seed(0x205a27d4,count,1)
    cpu.seed(p.NATIVE+8*(count-1),tag,1);cpu.seed(p.NATIVE+8*(count-1)+4,state)
    layout=json.loads((HERE/'local/resident/target-layout.json').read_text())['RvSession']['fields']
    cpu.seed(p.SESSION+layout['cursor']['offset'],row-1)
    cpu.seed(p.FRAME+60,99);cpu.seed(p.FRAME+28,99);cpu.seed(p.FRAME+52,0xabcdef00)
    cpu.stubs={program.symbols['rv_check']:lambda c:c.r.__setitem__(0,0),
               program.symbols['rv_session']:lambda c:c.r.__setitem__(0,p.SESSION),
               program.symbols['rv_engine']:lambda c:c.r.__setitem__(0,1)}
    cpu.run('rv_hook_observe',[p.ROOT_ADDRESS,hook,p.FRAME])
    return cpu


def main():
    p.LOCAL.mkdir(parents=True,exist_ok=True)
    current=p.Program('v33',HERE/'local/resident/build/resident.elf')
    old=p.Program('v32',ROOT/'firmware/resident_v32/local/resident/build/resident.elf')
    rows=[]
    for hook,count,tag,row,state in itertools.product((1,2,5),(1,2),(31,32,33),(1,3,5,8),(0x2022f71c,0x2022d610)):
        cpu=observe(current,hook,count,tag,row,state)
        expected=(tag==33 and state==0x2022f71c) or (hook<=2 and count==1 and tag==32)
        target=current.symbols[f'rv_skip_{hook:02}'] if expected else 0
        assert cpu.read(p.FRAME+4)==target,(hook,count,tag,row,state)
        if expected and hook<=2:assert cpu.read(p.FRAME+(60 if hook==1 else 28))==row
        if hook==5:
            assert cpu.read(p.FRAME+52)==(cpu.read(p.ROOT_ADDRESS+184) if expected else 0xabcdef00)
        assert cpu.read(0x2022f725,1)==cpu.read(0x2022f726,1)==1
        rows.append(dict(hook=hook,count=count,tag=tag,row=row,state=hex(state),skip=expected))
    for hook in (6,7,8):
        cpu=observe(current,hook,1,32,3,0x2022d610)
        assert not cpu.read(p.FRAME+4) and current.symbols['rv_engine'] not in cpu.calls
    negative=[]
    for hook,row in itertools.product((1,2),(1,3,5,8)):
        cpu=observe(old,hook,1,32,row,0x2022d610)
        assert not cpu.read(p.FRAME+4)
        negative.append(dict(hook=hook,row=row,old_first_frame_assertion_rejected=True))
    source_equal=[]
    for name in ('resident.c','shared.c','hooks.c','runtime.c','validate_envelope.inc.c','bridges.S','abi.h','gxrce.h'):
        assert (HERE/'resident'/name).read_bytes()==(ROOT/'firmware/resident_v33/resident'/name).read_bytes()
        source_equal.append(name)
    assert (HERE/'local/resident/linked_hooks.S').read_bytes()==(ROOT/'firmware/resident_v32/local/resident/linked_hooks.S').read_bytes()
    result=dict(status='PASS',instruction_cases=len(rows)+3,negative_controls=negative,cases=rows,
        unchanged_runtime_sources=source_equal,handwritten_and_generated_asm_equal=True,
        objdump_bytes_verified=current.verified_bytes,native_execution=False)
    (HERE/'local/entry-machine.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS entry instructions:',len(rows)+3,'v32 negative controls:',len(negative))


if __name__=='__main__':main()
