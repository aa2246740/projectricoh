#!/usr/bin/env python3
"""Replay the research trampoline object with symbolic relocation boundaries."""
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import evidence as e
spec=importlib.util.spec_from_file_location('bridge_replay_tools',HERE/'replay.py')
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

class Program:
    def __init__(self):
        self.name='research_trampoline_relocatable_object'
        obj=e.OUT/'sizing/bridge_trampoline.o'
        self.elf=r.native.p.reader.Elf(obj)
        section,=[s for s in self.elf.sections if s['name']=='.text.storage_trampoline']
        self.raw=self.elf.content(section)
        self.code,self.width,self.symbols={},{},{}
        self.ports={'port_match_and_run':0x206f0000,
            'port_native_post_handler':0x206f0010,'port_native_after_receive':0x206f0020}
        relocations=[]
        for line in (e.OUT/'sizing/trampoline-disasm.txt').read_text().splitlines():
            match=re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)\s*(.*?)\s*$',line)
            if match:
                pc,raw=int(match[1],16),bytes.fromhex(match[2])
                assert raw==self.raw[pc:pc+len(raw)]
                self.code[pc]=tuple(r.native.p.Program.parse(x) for x in re.split(r' -> | \|\| ',match[3]))
                self.width[pc]=len(raw)
            reloc=re.match(r'^\s*([0-9a-f]+):\s+R_M32R_26_PCREL_RELA\s+(\w+)\s*$',line)
            if reloc:
                pc,name=int(reloc[1],16),reloc[2]
                assert name in self.ports
                op=self.code[pc][0][0]
                assert op in ('bl','bra')
                self.code[pc]=((op,(hex(self.ports[name]),)),)
                relocations.append(dict(offset=hex(pc),symbol=name,boundary=hex(self.ports[name])))
        assert len(relocations)==3
        self.relocations=relocations

    def byte(self,address):
        return self.raw[address] if 0<=address<len(self.raw) else 0

def main():
    e.preflight()
    p=Program()
    rows=[]
    for received in (0,48,140,0xffffffff):
        for handled in (0,1):
            c=r.CPU(p)
            for i in range(15):c.r[i]=0x12340000+0x101*i
            c.r[0]=received
            c.psw=0x8041
            before=list(c.r)
            observed=[]
            def match(cc):
                observed.append(cc.r[4:6])
                for k in range(8):cc.r[k]=0xaabbccdd
                cc.psw=0x8000
                return handled
            r.stub(c,p.ports['port_match_and_run'],'private_match_boundary',hook=match)
            reached=[]
            def stop(cc):
                reached.append(cc.r.copy())
                raise r.base.Stop()
            c.stubs[p.ports['port_native_post_handler']]=stop
            c.stubs[p.ports['port_native_after_receive']]=stop
            try:c.call(0,(),bound=1000)
            except r.base.Stop:pass
            else:raise AssertionError('native continuation boundary not reached')
            expected=before.copy()
            expected[14]=r.native.p.END
            if not handled:expected[1]=0xffffffff
            assert c.r==expected,(received,handled,c.r,expected)
            assert c.psw==0x8041
            assert observed==[[received,0x204f41b4]]
            target=p.ports['port_native_post_handler' if handled else 'port_native_after_receive']
            assert target in c.calls
            rows.append(dict(received=hex(received),handled=bool(handled),
                reached='native_post_handler' if handled else 'native_after_receive',
                preserved_registers=True,psw=hex(c.psw),stack_balanced=True))
    result=dict(status='PASS_HOST_RESEARCH_TRAMPOLINE',cases=rows,relocations=p.relocations,
       limits=['Boundary behavior is synthetic; this does not implement the private handler.',
          'Relocations are mapped to host interpreter stop addresses; no firmware image is linked.',
          'No interrupt delivery, scheduling, instruction cache or physical CPU validation.'])
    e.save('trampoline-replay.json',result)
    print(result['status'],len(rows),'cases')

if __name__=='__main__':main()
