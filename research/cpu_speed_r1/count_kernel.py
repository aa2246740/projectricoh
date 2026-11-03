#!/usr/bin/env python3
"""Count an existing M32R LUT kernel. Does not build/link firmware or call hardware."""
from pathlib import Path
import collections
import hashlib
import importlib.util
import json
import random
import struct

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'evidence/kernel'

def module(path,name):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m

replay=module(ROOT/'firmware/lut_p0_timing/replay.py','cpu_speed_replay')
replay.m.LOCAL=OUT

class Cpu(replay.Cpu):
    def __init__(self,p):
        super().__init__(p)
        self.ops=collections.Counter()
        self.taken=collections.Counter()
        self.pc_ops=collections.Counter()
        self.nop_serial=0
        self.nop_parallel=0
    def op(self,name,args,pc):
        self.ops[name]+=1
        self.pc_ops[pc]+=1
        if name=='nop':
            if pc not in self.p.width and self.p.byte(pc)&0x80:self.nop_parallel+=1
            else:self.nop_serial+=1
        result=super().op(name,args,pc)
        if result is not None:self.taken[name]+=1
        return result

def run(p,words,label):
    cpu=Cpu(p)
    image=next(s for s in p.elf.sections if s['name']=='.engine')
    buf=0x20708000;table=0x20720000;stack=(0x206f0000,0x20700000)
    coord=p.symbols['p0_coord']
    cpu.ranges=[(image['va'],image['va']+image['size']),stack,
                (buf,buf+4*len(words)+8),(table,table+17**3*6)]
    cpu.writable=[stack,(buf,buf+4*len(words))]
    cpu.r[15]=stack[1]-16
    nodes=replay.v.table()
    for i,w in enumerate(words):cpu.seed(buf+4*i,w)
    for i,w in enumerate(nodes):cpu.seed(table+2*i,w,2)
    cpu.run('p0_kernel',[buf,len(words),table,coord],bound=12000000)
    accesses=list(cpu.accesses)
    actual=b''.join(cpu.read(buf+4*i).to_bytes(4,'big') for i in range(len(words)))
    expected=b''.join(replay.v.transform(w,nodes,replay.v.coordinates()) for w in words)
    assert actual==expected
    n=len(words)
    nonnop=sum(v for k,v in cpu.ops.items() if k!='nop')
    branches=sum(v for k,v in cpu.taken.items())
    reads=collections.Counter()
    for kind,a,width in accesses:
        if kind=='read':
            area='stack' if stack[0]<=a<stack[1] else 'lut' if table<=a<table+17**3*6 else 'coord' if coord<=a<coord+1024 else 'buffer'
            reads[area]+=1
    result=dict(label=label,pairs=n,non_nop_instructions=nonnop,ops=dict(cpu.ops),taken=dict(cpu.taken),
                per_pair=nonnop/n,reads=dict(reads),stack_bytes=(stack[1]-16)-min(a for kind,a,w in accesses if kind=='write' and stack[0]<=a<stack[1]),
                serial_nops=cpu.nop_serial,parallel_nops=cpu.nop_parallel,
                zero_wait_base_cycles=nonnop+cpu.nop_serial+2*cpu.ops['mul']+2*branches,
                output_matches_existing_reference=True,
                scope='Instruction count only. Base-cycle sum assumes original M32R, perfect fetch, no load-use stalls; not silicon time.')
    (OUT/(label+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/'firmware/lut_p0_timing/local/build/translated.elf'
    p=replay.m.Program('existing-translated-probe',source)
    elf=replay.c.Elf(ROOT/'firmware/lut_p0_timing/local/build/probe.elf')
    dat=(ROOT/'firmware/lut_p0_timing/local/GXRCE.DAT').read_bytes()
    sec=next(s for s in elf.sections if s['name']=='.engine')
    assert elf.content(sec)==dat[256:256+sec['size']]
    rng=random.Random(0x43505531)
    results=[]
    for label,words in [
        ('short',[replay.v.input_word(i) for i in range(64)]),
        ('mixed',[replay.v.input_word(i) for i in range(4096)]),
        ('random',[rng.getrandbits(32) for _ in range(4096)]),
        ('ties',[(i<<24)|((255-i)<<16)|(i<<8)|i for i in range(256)]),
        ('all_zero',[0]*4096),
        ('all_white',[0xffffffff]*4096)]:
        r=run(p,words,label);results.append(r)
        print(label,r['per_pair'],r['zero_wait_base_cycles']/r['pairs'],r['reads'],flush=True)
    (OUT/'summary.json').write_text(json.dumps(dict(existing_elf=str(source),elf_sha256=p.sha256,
        dat_sha256=hashlib.sha256(dat).hexdigest(),decoded_bytes_verified=p.verified_bytes,
        firmware_built=False,camera_executed=False,results=results),indent=2)+'\n')

if __name__=='__main__':main()
