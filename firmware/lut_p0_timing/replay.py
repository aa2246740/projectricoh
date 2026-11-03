"""Replay the actual linked kernel instructions against an independent reference."""
import importlib.util
from pathlib import Path
import random
import struct
import zlib

def module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

c=module(Path(__file__).with_name('common.py'),'replay_common')
v=module(Path(__file__).with_name('vectors.py'),'replay_vectors')
m=module(c.ROOT/'firmware/resident_v34c/policy_machine.py','pinned_instruction_model')


class Cpu(m.Cpu):
    def op(self,name,args,pc):
        if name in ('srl3','sll3','sra3'):
            x=self.r[m.reg(args[1])];shift=int(args[2].lstrip('#'),0)
            if name=='sra3' and x&0x80000000:x-=1<<32
            self.r[m.reg(args[0])]=((x<<shift) if name=='sll3' else (x>>shift))&0xffffffff
            return
        if name in ('ld','st','lduh') and (args[1].endswith('+') or args[1].startswith('@+')):
            size=2 if name=='lduh' else 4;operand=args[1]
            pre=operand.startswith('@+');r=m.reg(operand[2:] if pre else operand[1:-1])
            if pre:self.r[r]+=size
            a=self.r[r]
            if name=='st':self.write(a,self.r[m.reg(args[0])],size)
            else:self.r[m.reg(args[0])]=self.read(a,size)
            if not pre:self.r[r]+=size
            return
        return super().op(name,args,pc)

    def check(self,a,n,kind):
        assert any(b<=a and a+n<=e for b,e in self.ranges),(kind,hex(a),n)
        if kind=='write':
            assert any(b<=a and a+n<=e for b,e in self.writable),('nonprivate write',hex(a),n)
        self.accesses.append((kind,a,n))


def main():
    c.guard();m.LOCAL=c.LOCAL/'replay';m.LOCAL.mkdir(exist_ok=True)
    p=m.Program('actual-linked-probe',c.LOCAL/'build/translated.elf')
    # Translated ELF is the exact same code/data after the recorded relocations.
    elf=c.Elf(c.LOCAL/'build/probe.elf');dat=(c.LOCAL/'GXRCE.DAT').read_bytes()
    sec=next(s for s in elf.sections if s['name']=='.engine')
    assert elf.content(sec)==dat[256:256+sec['size']]
    image=next(s for s in p.elf.sections if s['name']=='.engine')
    base=0x20708000;table_at=0x20720000;stack=(0x206f0000,0x20700000)
    coord_at=p.symbols['p0_coord'];results=[];rng=random.Random(0x50300001)
    coord=v.coordinates();packed_coord=struct.pack('>256I',*coord)
    assert packed_coord==bytes(p.byte(coord_at+i) for i in range(1024))
    actual_nodes=bytes(p.byte(p.symbols['p0_table']+i) for i in range(17**3*6))
    assert actual_nodes==struct.pack('>'+str(17**3*3)+'H',*v.table())
    words=[v.input_word(i) for i in range(4096)]
    # Every code value on each axis; ties, endpoints, shared chroma extremes.
    words += [(a<<24)|((255-a)<<16)|(a<<8)|a for a in range(256)]
    words += [(a<<24)|(a<<16)|(255<<8) for a in range(256)]
    words += [rng.getrandbits(32) for _ in range(512)]
    for label,nodes,inputs in [('mixed',v.table(),words),('identity',v.table('identity'),words),
                                ('extremes',v.table('extremes'),words),
                                ('random', [rng.randrange(65536) for _ in range(17**3*3)],words[:1024])]:
        cpu=Cpu(p);cpu.ranges=[(image['va'],image['va']+image['size']),stack,
                               (base,base+len(inputs)*4+8),(table_at,table_at+17**3*6)]
        cpu.writable=[stack,(base,base+len(inputs)*4)]
        cpu.r[15]=stack[1]-16
        for i,w in enumerate(inputs):cpu.seed(base+4*i,w)
        for i,w in enumerate(nodes):cpu.seed(table_at+2*i,w,2)
        before=[0xa0000000+i for i in range(8)];cpu.r[8:16]=before[:]
        cpu.r[15]=stack[1]-16;sp=cpu.r[15]
        cpu.run('p0_kernel',[base,len(inputs),table_at,coord_at],bound=8000000)
        actual=b''.join(cpu.read(base+4*i).to_bytes(4,'big') for i in range(len(inputs)))
        expected=b''.join(v.transform(w,nodes,coord) for w in inputs)
        assert actual==expected,(label,'real built kernel differs from reference')
        if label=='identity':assert actual==b''.join(w.to_bytes(4,'big') for w in inputs)
        assert cpu.r[8:14]==before[:6] and cpu.r[15]==sp,'GCC callee-save/SP'
        assert cpu.psw&0x40,'kernel changed interrupt enable'
        reads=[(a,n) for k,a,n in cpu.accesses if k=='read' and base<=a<base+len(inputs)*4]
        writes=[(a,n) for k,a,n in cpu.accesses if k=='write' and base<=a<base+len(inputs)*4]
        # Exclude the explicit output readback above.
        assert len(reads)==len(inputs)*2 and all(n==4 for _,n in reads)
        assert writes==[(base+4*i,4) for i in range(len(inputs))]
        table_reads=[n for k,a,n in cpu.accesses if k=='read' and table_at<=a<table_at+17**3*6]
        coord_reads=[n for k,a,n in cpu.accesses if k=='read' and coord_at<=a<coord_at+1024]
        assert table_reads==[2]*(24*len(inputs))
        assert coord_reads==[4]*(4*len(inputs))
        results.append(dict(table=label,pairs=len(inputs),crc32=f'{zlib.crc32(actual):08x}',
                            one_group_read_write=True,node_reads_per_pair=24,coordinate_reads_per_pair=4,
                            stack_bytes=sp-min(a for k,a,n in cpu.accesses if k=='write' and stack[0]<=a<stack[1]),
                            callee_save=True,output_equal=True))
        print('PASS replay table='+label+' pairs='+str(len(inputs)),flush=True)
    # Zero trips must touch neither input nor table.
    cpu=Cpu(p);cpu.ranges=[(image['va'],image['va']+image['size']),stack];cpu.writable=[stack]
    cpu.r[15]=stack[1]-16;cpu.run('p0_kernel',[0,0,0,0],bound=1000)
    # Tick wrapper must preserve all native callee saves, including r12/r13.
    cpu=Cpu(p);cpu.ranges=[stack];cpu.writable=[stack];cpu.r[15]=stack[1]-16
    saves=[0xabcdef00+i for i in range(6)];cpu.r[8:14]=saves
    def tick_stub(x):
        x.r[0]=0xfffffff0
        for i in range(1,14):x.r[i]=0xbad00000+i
    cpu.stubs[0x2005f164]=tick_stub
    assert cpu.run('p0_tick',bound=100)==0xfffffff0 and cpu.r[8:14]==saves
    for count in (0,4,64,512,4096):
        cpu=Cpu(p);cpu.ranges=[stack];cpu.writable=[stack]
        cpu.run('p0_decrement',[0,count,0,0],bound=10000);assert cpu.r[1]==0
        cpu.run('p0_empty',[0,count,0,0],bound=20)
    c.save(c.LOCAL/'replay-results.json',dict(status='PASS',dat_sha256=c.sha(c.LOCAL/'GXRCE.DAT'),tables=results,zero_trip=True,
        native_tick_callee_saves=True,actual_dat_code_equal=True,psw_ie_unchanged=True,
        model_sha256=c.sha(c.ROOT/'firmware/resident_v34c/policy_machine.py'),
        scope='Bounded instruction semantics; no physical timing, IRQ, cache or DMA simulation.'))


if __name__=='__main__':main()
