#!/usr/bin/env python3
"""Execute final M32R IRQ bytes and replay stubs in a bounded instruction subset."""
import importlib.util
import json
from pathlib import Path
import random
import struct

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local'
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
b=module(HERE/'resident/build.py','v3_machine_build')
Elf=module(ROOT/'firmware/stage2l_switch/tools/build.py','v3_machine_elf').Elf

def extract(path,symbol):
    e=Elf(path);s=e.symbols[symbol];section=e.sections[s['section']]
    return e.content(section)[s['value']-section['va']:s['value']-section['va']+s['size']],s['value']

class IRQ:
    def __init__(self,psw):self.psw=psw;self.r=[0]*16;self.r[14]=0x20301234
    def half(self,h):
        h&=0x7fff;d=(h>>8)&15;s=h&15
        if h==0x7000:return False
        if h&0xf0f0==0x1090:
            assert s==0;self.r[d]=self.psw
        elif h&0xf0f0==0x10a0:
            assert d==0;self.psw=self.r[s]
        elif h&0xfff0==0x1fc0:
            assert s==14;return True
        else:raise AssertionError(f'unknown IRQ half {h:04x}')
        return False
    def run(self,code):
        for at in range(0,len(code),4):
            word=struct.unpack_from('>I',code,at)[0]
            if word&0x80000000:
                d=(word>>24)&15;s=(word>>16)&15
                if word&0xf0f00000==0x80c00000:self.r[d]=self.r[s]&(word&0xffff)
                elif word&0xf0f00000==0x80e00000:self.r[d]=self.r[s]|(word&0xffff)
                else:raise AssertionError(f'unknown IRQ word {word:08x}')
            else:
                if self.half(word>>16):return
                if self.half(word&65535):return
        raise AssertionError('missing return')

def irq_checks():
    rows=[];canonical=None;restore=None
    for label,path in [('resident',LOCAL/'resident/build/resident.elf'),('services',LOCAL/'resident/engine-services/services-linkcheck.elf')]:
        raw,va=extract(path,'rv_irq_save');res,rva=extract(path,'rv_irq_restore')
        # Assembly symbols do not carry a size in this toolchain.
        if not raw:
            e=Elf(path);sec=next(s for s in e.sections if s['name']=='.payload');payload=e.content(sec)
            raw=payload[va-sec['va']:va-sec['va']+12];res=payload[rva-sec['va']:rva-sec['va']+4]
        assert len(raw)==12 and len(res)==4
        if canonical is None:canonical,restore=raw,res
        assert raw==canonical and res==restore
        rows.append(dict(name=label,address=va,save_bytes=raw.hex(),restore_bytes=res.hex(),raw=raw))
    for kind,name in [('product','base'),('product','huzi'),('probes','life'),('probes','notice'),('probes','view')]:
        path=LOCAL/kind/'candidates'/name/'GXRCE.DAT';raw=path.read_bytes();off,n=struct.unpack_from('>II',raw,132);code=raw[off:off+n]
        at=code.find(canonical+restore);assert at>=0 and code.find(canonical+restore,at+1)<0
        rows.append(dict(name=name,address=off+at,save_bytes=canonical.hex(),restore_bytes=restore.hex(),raw=canonical))
    for row in rows:
        for incoming in range(65536):
            m=IRQ(incoming);m.run(row['raw']);assert m.psw==(incoming&0xffbf) and m.r[0]==incoming
            m.run(restore);assert m.psw==incoming
        nested=0
        for incoming in (0,1,0x40,0x41,0x80,0x81,0xc0,0xc1):
            m=IRQ(incoming);m.run(row['raw']);outer=m.r[0];m.run(row['raw']);inner=m.r[0]
            assert not m.psw&0x40;m.r[0]=inner;m.run(restore);assert not m.psw&0x40
            m.r[0]=outer;m.run(restore);assert m.psw==incoming;nested+=1
        del row['raw'];row.update(raw_16bit_vectors=65536,nested_legal_vectors=nested,status='PASS')
    old=bytearray(canonical);old[4:8]=struct.pack('>I',0x81e00040)
    failures=[]
    for incoming in (0,1,0x40,0x41,0x80,0x81,0xc0,0xc1):
        m=IRQ(incoming);m.run(old)
        if m.psw&0x40:failures.append(dict(incoming=incoming,observed=m.psw))
    assert len(failures)==8
    result=dict(status='PASS',artifacts=rows,old_or3_negative_control=failures,
                total_raw_vectors=7*65536,native_m32r_execution=False,
                limits='instruction subset; no interrupts, pipeline, cache or hardware PSW banking')
    (LOCAL/'irq-machine.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS IRQ final bytes: artifacts={len(rows)} vectors={7*65536} old_polarity_rejected=8')

def replay():
    # Reuse only the read-only review interpreter class, not its import-time I/O.
    source=(ROOT/'research/review_flash_v2/local/m32r_replay.py').read_text()
    definition=source[source.index('def sign('):source.index('\ncases=0')]
    elf=Elf(LOCAL/'resident/build/resident.elf');sec=next(s for s in elf.sections if s['name']=='.payload')
    namespace=dict(struct=struct,random=random,SEC=sec,CODE=elf.content(sec),OBSERVE=elf.symbols['rv_hook_observe']['value'])
    exec(definition,namespace);Machine=namespace['Machine'];cases=0
    hooks=json.loads((LOCAL/'resident/hooks.json').read_text())
    for h in hooks:
        n=h['number']
        if n not in (1,2,5,6,7,8,9):continue
        for psw in (0,1,0x40,0x41,0x80,0x81,0xc0,0xc1):
            for seed in range(16):
                rng=random.Random(seed);regs=[rng.getrandbits(32) for _ in range(16)]
                regs[0]=0x20730000;regs[14]=0x20301234;regs[15]=0x05017ffc
                before={0x20730000:0xabcddcba};expected=Machine(regs,psw,before,seed)
                displaced=bytes.fromhex(h['original_bytes'])
                for off in range(0,len(displaced),4):
                    expected.pc=int(h['va'],16)+off
                    assert expected.word(struct.unpack_from('>I',displaced,off)[0]) is None
                actual=Machine(regs,psw,before,seed)
                actual.run(elf.symbols[f'rv_hook_{n:02}']['value'],int(h['replay_resume'],16))
                assert actual.r==expected.r and actual.psw==expected.psw and actual.ids==[n]
                for address,value in expected.mem.items():assert actual.read(address)==value
                # Scratch stack words below the returned SP are deliberately ignored.
                for address,value in actual.mem.items():
                    if address>=actual.r[15]:assert value==expected.mem.get(address,0xdeadbeef)
                cases+=1
    (LOCAL/'replay-machine.json').write_text(json.dumps(dict(status='PASS',cases=cases,hooks=7,
        c_policy='PASS interception and register/C clobbering',native_m32r_execution=False),indent=2)+'\n')
    print(f'PASS original-word replay: hooks=7 vectors={cases}')

if __name__=='__main__':
    b.preflight();irq_checks();replay()
