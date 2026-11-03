"""Replay packed target code against a separately written numeric oracle."""
from pathlib import Path
import hashlib
import importlib.util
import random
import struct
import zlib

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('review_runner',HERE/'run_review.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
r=driver.load(driver.SOURCE/'replay.py','review_instruction_replay')
c=driver.c


def location(value):
    if value==255:return 15,256
    return divmod(value*4096//255,256)


def oracle_pixel(y,u,v,nodes):
    coordinates=[location(x) for x in (y,u,v)]
    cell=[x[0] for x in coordinates]
    a,b,d=[x[1] for x in coordinates]
    if a>=b:
        order=(0,1,2) if b>=d else ((0,2,1) if a>=d else (2,0,1))
    else:
        order=(1,0,2) if a>=d else ((1,2,0) if b>=d else (2,1,0))
    fractions=[(a,b,d)[axis] for axis in order]
    weights=(256-fractions[0],fractions[0]-fractions[1],fractions[1]-fractions[2],fractions[2])
    result=[0,0,0]
    for vertex,weight in enumerate(weights):
        if vertex:cell[order[vertex-1]]+=1
        offset=(cell[2]*289+cell[1]*17+cell[0])*3
        for channel in range(3):result[channel]+=weight*nodes[offset+channel]
    return result


def oracle(word,nodes):
    y0,y1,u,v=word.to_bytes(4,'big')
    first=oracle_pixel(y0,u,v,nodes)
    second=oracle_pixel(y1,u,v,nodes)
    values=((first[0]+32768)//65536,(second[0]+32768)//65536,
            (first[1]+second[1]+65536)//131072,(first[2]+second[2]+65536)//131072)
    return bytes(max(0,min(255,x)) for x in values)


def main():
    driver.freeze()
    r.m.LOCAL=HERE/'independent-machine'
    r.m.LOCAL.mkdir(exist_ok=True)
    program=r.m.Program('packed-code',c.LOCAL/'build/translated.elf')
    image=next(s for s in program.elf.sections if s['name']=='.engine')
    section=c.Elf(c.LOCAL/'build/probe.elf')
    packed=(c.LOCAL/'GXRCE.DAT').read_bytes()
    data_section=next(s for s in section.sections if s['name']=='.engine')
    assert section.content(data_section)==packed[256:256+data_section['size']]
    coords=program.symbols['p0_coord']
    for value in range(256):
        cell,fraction=location(value)
        actual=int.from_bytes(bytes(program.byte(coords+value*4+j) for j in range(4)),'big')
        assert actual==(cell<<16)|fraction
    raw=bytes(program.byte(program.symbols['p0_table']+i) for i in range(29478))
    mixed=list(struct.unpack('>14739H',raw))
    rng=random.Random(0x26A0D17)
    inputs=[r.v.input_word(i) for i in range(4096)]
    inputs += [(x<<24)|((255-x)<<16)|(x<<8)|x for x in range(256)]
    inputs += [(x<<24)|(x<<16)|0xff00 for x in range(256)]
    inputs += [rng.getrandbits(32) for _ in range(512)]
    identity=[];extremes=[]
    for v in range(17):
        for u in range(17):
            for y in range(17):
                identity += [y*4080,u*4080,v*4080]
                extremes += [65535*((y+u+v+k)%2) for k in range(3)]
    tables=[('mixed',mixed,inputs),('identity',identity,inputs),('extremes',extremes,inputs),
            ('random',[rng.randrange(65536) for _ in range(14739)],inputs[:1024])]
    rows=[]
    for name,nodes,words in tables:
        base,table=0x20708000,0x20720000
        stack=(0x206f0000,0x20700000)
        cpu=r.Cpu(program)
        cpu.ranges=[(image['va'],image['va']+image['size']),stack,
                    (base,base+len(words)*4+8),(table,table+29478)]
        cpu.writable=[stack,(base,base+len(words)*4)]
        cpu.r[15]=stack[1]-16
        for i,w in enumerate(words):cpu.seed(base+4*i,w)
        for i,x in enumerate(nodes):cpu.seed(table+2*i,x,2)
        saves=[0xacf00000+i for i in range(6)]
        cpu.r[8:14]=saves
        cpu.run('p0_kernel',[base,len(words),table,coords],bound=8000000)
        accesses=list(cpu.accesses)
        output=b''.join(cpu.read(base+4*i).to_bytes(4,'big') for i in range(len(words)))
        expected=b''.join(oracle(word,nodes) for word in words)
        assert output==expected,name
        if name=='identity':assert output==b''.join(w.to_bytes(4,'big') for w in words)
        assert cpu.r[8:14]==saves and cpu.psw&0x40
        scratch_reads=[(a,n) for k,a,n in accesses if k=='read' and base<=a<base+len(words)*4]
        scratch_writes=[(a,n) for k,a,n in accesses if k=='write' and base<=a<base+len(words)*4]
        assert scratch_reads==scratch_writes==[(base+4*i,4) for i in range(len(words))]
        assert len([1 for k,a,n in accesses if k=='read' and table<=a<table+29478 and n==2])==24*len(words)
        assert len([1 for k,a,n in accesses if k=='read' and coords<=a<coords+1024 and n==4])==4*len(words)
        (HERE/(name+'-output.bin')).write_bytes(output)
        rows.append(dict(table=name,pairs=len(words),bytes_equal=True,crc32=f'{zlib.crc32(output):08x}',
                         sha256=hashlib.sha256(output).hexdigest(),node_reads_per_pair=24,coord_reads_per_pair=4,
                         group_read_write=1,callee_saves=True))
        print('PASS independent oracle table='+name+' pairs='+str(len(words)),flush=True)
    c.save(HERE/'independent-kernel-results.json',dict(status='PASS',pairs=sum(x['pairs'] for x in rows),
        tables=rows,dat_sha256=c.sha(c.LOCAL/'GXRCE.DAT'),
        reference='This file: explicit six-way tetrahedron selection and direct barycentric sum; no vectors.transform/pixel/coordinates.',
        limitations='Shared bounded instruction interpreter; no silicon, scheduler, cache, DMA or cycle model.'))
    driver.freeze()


if __name__=='__main__':main()
