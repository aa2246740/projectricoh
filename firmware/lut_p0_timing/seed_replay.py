"""Execute rv_native_seed from the final packed probe, without service stubs."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('seed_replay', Path(__file__).with_name('replay.py'))
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
c = r.c


def main():
    c.guard();r.m.LOCAL=c.LOCAL/'seed-replay';r.m.LOCAL.mkdir(exist_ok=True)
    p=r.m.Program('packed-probe-seed',c.LOCAL/'build/translated.elf')
    elf=c.Elf(c.LOCAL/'build/probe.elf');dat=(c.LOCAL/'GXRCE.DAT').read_bytes()
    section=next(s for s in elf.sections if s['name']=='.engine')
    assert elf.content(section)==dat[256:256+section['size']]
    image=next(s for s in p.elf.sections if s['name']=='.engine')
    context,private=0x20710000,0x20711000;stack=(0x206f0000,0x20700000)
    state=c.native(0x2022f71c,32);table=c.native(0x2022f56c,72);rows=[]
    cases=[(kind,0x2022f56c,256,True) for kind in (0,4,9,5)]
    cases += [(5,0x2022f000,256,True),(0,0x2022f000,256,False),
              (0,0,256,False),(0,0x2022f56c,235,False),(0,0x2022f56c,236,True)]
    for kind,address,capacity,accepted in cases:
        cpu=r.Cpu(p)
        cpu.ranges=[(image['va'],image['va']+image['size']),stack,
                    (0x2022f000,0x2022f800),(context,context+120),(private,private+256)]
        cpu.writable=[stack,(context+68,context+72),(private,private+capacity)]
        cpu.r[15]=stack[1]-16
        for i,b in enumerate(state):cpu.seed(0x2022f71c+i,b,1)
        for location in (0x2022f56c,0x2022f000):
            for i,b in enumerate(table):cpu.seed(location+i,b,1)
        for i in range(256):cpu.seed(private+i,0xa7,1)
        cpu.seed(0x2022f71c,kind,1);cpu.seed(0x2022f720,address)
        cpu.seed(context+64,private);cpu.seed(context+68,0);cpu.seed(context+72,capacity)
        before=bytes(cpu.read(0x2022f71c+i,1) for i in range(32))
        saves=[0xabc00000+i for i in range(6)];cpu.r[8:14]=saves
        result=cpu.run('rv_native_seed',[context],bound=10000)
        assert result==(0 if accepted else 2),(kind,hex(address),capacity,result)
        assert cpu.r[8:14]==saves and cpu.psw&0x40
        assert bytes(cpu.read(0x2022f71c+i,1) for i in range(32))==before
        assert bytes(cpu.read(0x2022f56c+i,1) for i in range(72))==table
        actual=bytes(cpu.read(private+i,1) for i in range(256))
        expected=(b'\x05'+before[1:]+table+bytes(132)+b'\xa7'*20) if accepted else b'\xa7'*256
        assert actual==expected and cpu.read(context+68)==(236 if accepted else 0)
        rows.append(dict(kind=kind,table=hex(address),capacity=capacity,accepted=accepted,
                         return_value=result,native_unchanged=True,private_bytes_exact=True))
    c.save(c.LOCAL/'seed-replay-results.json',dict(status='PASS',dat_sha256=c.sha(c.LOCAL/'GXRCE.DAT'),
        cases=rows,actual_dat_code_equal=True,service_calls_stubbed=False,
        scope='Final packed seed, copy and clear instructions; native inputs are bounded test parameters.'))
    print('PASS packed M32R seed: 9 cases, private snapshot exact, no native writes')


if __name__=='__main__':main()
