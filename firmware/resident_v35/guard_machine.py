"""Execute the final engine's rejected-card guard bytes with storage call doubles."""
import importlib.util
import itertools
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name,path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    p = module(HERE/'policy_machine.py','guard_cpu')
    p.LOCAL = HERE/'local/recovery/guard-machine'
    p.LOCAL.mkdir(parents=True,exist_ok=True)
    program = p.Program('r9',HERE/'acceptance/local/product-r9/m32r-lto/translated.elf')

    class Cpu(p.Cpu):
        def check(self,address,n,kind):
            assert 0x20000000 <= address and address+n <= 0x22000000,(kind,hex(address),n)
            self.accesses.append((kind,address,n))

    rows = []
    for source,capability,opened,closed in itertools.product((1,2,3),(0,-1),(0,2,-1),(0,-1)):
        cpu=Cpu(program)
        cpu.seed(program.symbols['n']+4,0x20720000)
        cpu.seed(0x20720010,0x20710000)
        cpu.seed(0x20710000+328,source)
        calls=[]

        def zero(c):
            for offset in range(c.r[1]):c.write(c.r[0]+offset,0,1)

        def storage(c):
            op,q,reply=c.r[2],c.r[3],c.read(c.r[15])
            assert c.r[1]==1 and c.read(q)==0x10040
            assert op in (1,2,6)
            calls.append(op)
            if op==1:
                assert all(c.read(q+8+4*i)==0 for i in range(14))
                c.write(reply+20,7);status=capability
            elif op==2:
                assert [c.read(q+8+4*i) for i in range(14)] == [7,0,1,0,0,1,0,0,0,0,0,0,0,0]
                c.write(reply+16,19);status=opened
            else:
                assert [c.read(q+8+4*i) for i in range(14)] == [7,19,0,0,0,0,0,0,0,0,0,0,0,0]
                status=closed
            c.r[0]=status&0xffffffff
            for register in (1,2,3):c.r[register]=0xbad00000+register

        cpu.stubs={program.symbols['ig_zero']:zero,program.symbols['pn_call.isra.0']:storage}
        result=cpu.run('rejected_card_present')
        expected=0 if source==3 or (capability==0 and opened==2) else 1
        assert result==expected,(source,capability,opened,closed,result)
        want=[] if source==3 else [1] if capability else [1,2,6] if not opened else [1,2]
        assert calls==want
        rows.append(dict(source=source,capability=capability,opened=opened,closed=closed,result=result,operations=calls))
    # Check the final packed engine contains exactly the compiled IRQ helper.
    machine=module(HERE/'machine_checks.py','final_irq')
    reader=machine.Elf(HERE/'local/resident/build/resident.elf')
    section=next(s for s in reader.sections if s['name']=='.payload')
    code=reader.content(section)
    save=reader.symbols['rv_irq_save']['value']-section['va']
    restore=reader.symbols['rv_irq_restore']['value']-section['va']
    a,b=code[save:save+12],code[restore:restore+4]
    raw=(HERE/'acceptance/local/full-r9/GXRCE.DAT').read_bytes()
    offset,size=struct.unpack_from('>II',raw,132)
    assert raw[offset:offset+size].count(a+b)==1
    for incoming in range(65536):
        cpu=machine.IRQ(incoming);cpu.run(a)
        assert cpu.psw==incoming&0xffbf and cpu.r[0]==incoming
        cpu.run(b);assert cpu.psw==incoming
    result=dict(status='PASS',guard_instruction_cases=len(rows),guard_storage_calls_only=[1,2,6],
        cases=rows,full_r9_irq_vectors=65536,total_irq_vectors_with_resident_and_r8=655360,
        objdump_bytes_verified=program.verified_bytes,native_execution=False)
    (p.LOCAL/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS guard instructions',len(rows),'full-r9 IRQ vectors',65536)


if __name__=='__main__':
    main()
