"""Byte-checked native continuation, view push and descriptor consumer replay.

H01/H02 results and external graphics/scheduler boundaries are explicit models.
This does not execute the camera, its scheduler, or its LCD renderer.
"""
import importlib.util
import itertools
import json
from pathlib import Path
import re
import struct
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

p=load(ROOT/'firmware/resident_v34c/policy_machine.py','review_native_cpu')
a=load(HERE/'artifact_review.py','review_artifact')

class Program:
    def __init__(self):
        self.name='official-byte-checked';self.spans=[];self.code={};self.width={};self.verified_bytes=0
        raw=(ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
        for i in range(16):
            off,base,size,_,_=struct.unpack_from('>5I',raw,32+20*i)
            if size:self.spans.append((base,raw[512+off:512+off+size]))
        self.symbols={'constructor':0x20287080,'draw':0x201fd360,'rows':0x201fdd10,'view_init':0x201c05a8}
        for name,start,end in [('rows',0x201fdd10,0x201ff3d4),('labels',0x201fdc70,0x201fdcd0)]:
            data,_=a.mapped(raw,start,end-start);(HERE/(name+'.bin')).write_bytes(data)
            text=subprocess.check_output([str(a.OBJDUMP),'-D','-b','binary','-m','m32r','-EB',
                '--adjust-vma='+hex(start),str(HERE/(name+'.bin'))],text=True)
            (HERE/(name+'.disasm')).write_text(text)
        for name in ('image','common','view','draw','rows','labels'):
            text=(HERE/(name+'.disasm')).read_text()
            for m in re.finditer(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*?)\s*$',text,re.M):
                pc=int(m[1],16);code=bytes.fromhex(m[2])
                assert code==bytes(self.byte(pc+i) for i in range(len(code)))
                self.verified_bytes+=len(code)
                if len(code) not in (2,4):continue
                self.width[pc]=len(code)
                self.code[pc]=tuple(p.Program.parse(op) for op in re.split(r' -> | \|\| ',m[3]))
    def byte(self,address):
        for base,data in self.spans:
            if base<=address<base+len(data):return data[address-base]
        return 0

class Cpu(p.Cpu):
    def __init__(self,program):
        super().__init__(program);self.events=[];self.handlers={};self.pc=0;self.visits=[]
    def op(self,name,args,pc):
        if name in ('sll3','srl3'):
            d,s=p.reg(args[0]),p.reg(args[1]);n=int(args[2].lstrip('#'),0)
            self.r[d]=(self.r[s]<<n if name=='sll3' else self.r[s]>>n)&0xffffffff;return
        if name in ('cmp','cmpi'):
            x=self.r[p.reg(args[0])];x=x-(1<<32) if x&(1<<31) else x
            y=int(args[1].lstrip('#'),0) if name=='cmpi' else self.r[p.reg(args[1])]
            if y&(1<<31):y-=1<<32
            self.condition(x<y);return
        if name=='add3':
            d,s=p.reg(args[0]),p.reg(args[1]);imm=int(args[2].lstrip('#'),0)
            if 0<=imm<=0xffff and imm&0x8000:imm-=0x10000
            self.r[d]=(self.r[s]+imm)&0xffffffff;return
        return super().op(name,args,pc)
    def check(self,address,n,kind):
        assert 0x20000000<=address and address+n<=0x22000000,(kind,hex(self.pc),hex(address),n)
        if n>1:assert address%n==0,('unaligned',hex(self.pc),hex(address),n)
        self.accesses.append((kind,address,n))
    def run(self,symbol,args=(),bound=50000):
        for i,v in enumerate(args):self.r[i]=v
        self.r[14]=p.END;pc=self.p.symbols[symbol];sp=self.r[15]
        for steps in range(bound):
            self.pc=pc;self.visits.append(pc)
            if pc==p.END:
                assert self.r[15]==sp,(symbol,'SP',hex(self.r[15]),hex(sp));return
            if pc in self.handlers:
                pc=self.handlers[pc](self);continue
            if pc in self.stubs:
                self.calls.append(pc);self.stubs[pc](self);pc=self.r[14];continue
            assert pc in self.p.code,('unmapped native PC',symbol,hex(pc))
            jump=None
            for j,(op,operands) in enumerate(self.p.code[pc]):
                jump=self.op(op,operands,pc+2*j)
                if jump is not None:break
            pc=pc+self.p.width[pc] if jump is None else jump
        raise AssertionError(('native instruction bound',symbol,hex(pc)))

def main():
    program=Program();results=[]
    for prior,row,custom,category in itertools.product((0,4,9,5),range(1,9),(False,True),(0,1)):
        cpu=Cpu(program)
        # Field assumptions: parent stack already has one view, part 2 enabled.
        cpu.seed(0x205a27d8,0x205a279c);cpu.seed(0x205a27d4,1,1)
        cpu.seed(0x205a279c,32,1);cpu.seed(0x205a27a0,0x2022d610)
        cpu.seed(0x205a280e,2,1);cpu.seed(0x205a280f,2,1)
        cpu.seed(0x2022f71c,prior,1)
        # A real ADJ constructor has filled these before Image Settings.
        for i,v in enumerate((1,2,3,4,5)):cpu.seed(0x205d9bcc+i,v,1)
        no_op=lambda c:c.r.__setitem__(0,0)
        cpu.stubs={addr:no_op for addr in (0x20331d18,0x20331d14,0x201d82b4,
            0x201c3fd4,0x201d82fc,0x201c092c,0x20270d78)}
        cpu.stubs[0x2026c314]=lambda c:c.r.__setitem__(0,category)
        cpu.stubs[0x20271fec]=lambda c:c.r.__setitem__(0,1)
        def h01(c):
            if not custom:return 0x2028709c+4
            # Mirror the independently checked C publication result.
            c.seed(0x2022f5a8,0x20726000);c.seed(0x2022f5ac,8,1)
            c.seed(0x2022f725,row,1);c.seed(0x2022f726,row,1)
            c.r[8]=row
            return 0x20287118
        if custom:cpu.handlers[0x2028709c]=h01
        cpu.run('constructor')
        assert cpu.read(0x2022f71c,1)==5 and cpu.read(0x2022f720)==0x2022f56c
        assert cpu.read(0x2022f5a8)==(0x20726000 if custom else 0x2022d610)
        assert cpu.read(0x2022f5ac,1)==(8 if custom else 7)
        assert cpu.read(0x2022f726,1)==(row if custom else 2)
        assert cpu.read(0x205a27d4,1)==1 and cpu.read(0x205a279c,1)==33
        assert cpu.read(0x205a27a0)==0x2022f71c
        assert 0x2028579c in cpu.visits and 0x2028712c in cpu.visits
        results.append(dict(prior_type=prior,row=row,custom=custom,native_category_result=category,
            final_state=bytes(cpu.read(0x2022f71c+i,1) for i in range(32)).hex(),
            descriptor_names=hex(cpu.read(0x2022f5a8)),descriptor_count=cpu.read(0x2022f5ac,1),
            view_count=1,top_tag=33,top_state='0x2022f71c',steps=len(cpu.visits)))
    # Execute the real descriptor-read prefix, including a rejected-table counterexample.
    consumers=[]
    for table,count in ((0x2022f56c,8),(0x2022f56c,7),(0,7)):
        cpu=Cpu(program);cpu.seed(0x2022f71c,5,1);cpu.seed(0x2022f720,table)
        cpu.seed(0x2022f5ac,count,1)
        def done(c):return p.END
        cpu.handlers[0x201fdd90]=done
        if table:
            cpu.r[4:7]=[2,0x2022f71c,0]
            # Stop early, before this function's stack epilogue.
            original_sp=cpu.r[15];cpu.handlers[0x201fdd90]=lambda c:(c.r.__setitem__(15,original_sp) or p.END)
            cpu.run('rows');assert cpu.r[11]==5
            consumers.append(dict(table=hex(table),count=count,read_count=count,accepted=True))
        else:
            cpu.r[4:7]=[2,0x2022f71c,0]
            try:cpu.run('rows')
            except AssertionError as e:
                assert cpu.pc==0x201fdd4c,(hex(cpu.pc),e)
                consumers.append(dict(table='0x0',accepted=False,pc=hex(cpu.pc),read_address='0x40',error=str(e)))
            else:raise AssertionError('null table should fault at the native consumer')
    render=[]
    for count in (8,11):
        for row in range(1,count+1):
            cpu=Cpu(program);state=0x2022f71c if count==8 else 0x20724000
            table=0x2022f56c if count==8 else state+32
            for i in range(32):cpu.seed(state+i,program.byte(0x2022f71c+i),1)
            for i in range(72):cpu.seed(table+i,program.byte(0x2022f56c+i),1)
            cpu.seed(state,5,1);cpu.seed(state+4,table);cpu.seed(state+9,row,1);cpu.seed(state+10,row,1)
            cpu.seed(table+60,0x20726000);cpu.seed(table+64,count,1);cpu.seed(table+68,0)
            glyphs=[]
            for i in range(count):
                cpu.seed(0x20726000+4*i,0x20726100+4*i)
                cpu.seed(0x20726100+4*i,0x20727000+96*i)
                cpu.seed(0x20727000+96*i,0x01410000)
            def glyph(c):
                value=c.read(c.r[5]+8)
                if 0x20727000<=value<0x20728000:glyphs.append(value)
                c.r[0]=0
            cpu.stubs={address:(glyph if address==0x201d7170 else (lambda c:c.r.__setitem__(0,0)))
                for address in (0x201d7170,0x201d74a8,0x201d709c,0x201d7b88,0x201dba08,0x201fdcd0,0x201dcbbc)}
            def zero_fill(c):
                for i in range(c.r[6]):c.write(c.r[4]+i,c.r[5],1)
                c.r[0]=c.r[4]
            cpu.stubs[0x20062750]=zero_fill
            def h05(c):c.r[2]=0x20725000;return 0x201febec
            cpu.handlers[0x201febe4]=h05
            cpu.r[4:7]=[2,state,0];cpu.run('rows')
            assert len(glyphs)==len(set(glyphs))==min(count,9)
            assert all(0x20727000<=g<0x20727000+96*count for g in glyphs)
            reads=[addr for kind,addr,n in cpu.accesses if kind=='read' and 0x20726000<=addr<0x20726080]
            assert all(addr<0x20726000+count*4 for addr in reads)
            render.append(dict(count=count,cursor=row,glyph_pointers=[hex(g) for g in glyphs],
                label_reads=[hex(x) for x in reads],external_calls=sorted(set(hex(x) for x in cpu.calls))))
    (HERE/'native_flow.json').write_text(json.dumps(dict(status='PASS_BOUNDED_NATIVE_MODEL',
        verified_instruction_bytes=program.verified_bytes,constructor_cases=results,consumers=consumers,render=render,
        stubs=['H01/H02 bridge publication result','native graphics registration and layer dispatch',
               'category probes return 0 or 1','scheduler/interrupts are not modeled']),indent=2)+'\n')
    print('PASS full native continuation and view push',len(results),'cases; descriptor consumer',len(consumers),
          'cases; native row iteration',len(render),'cases')

if __name__=='__main__':main()
