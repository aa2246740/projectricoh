#!/usr/bin/env python3
"""Execute the final policy instructions, decoded only by the pinned objdump.

This bounded subset is a host model, without interrupts, concurrent native UI,
pipeline, caches or actual device execution. External calls are named doubles.
"""
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import re
import struct
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local/policy-machine'
OBJDUMP=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
spec=importlib.util.spec_from_file_location('policy_elf',ROOT/'firmware/stage2l_switch/tools/build.py')
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
END=0x20301234
ROOT_ADDRESS=0x20054700
SESSION=0x20710000
FRAME=0x20680000
NATIVE=0x205a279c

def reg(name):
    return {'sp':15,'fp':13,'lr':14}.get(name,int(name[1:]) if re.fullmatch(r'r\d+',name) else -1)

class Program:
    def __init__(self,name,path):
        self.elf=reader.Elf(path);self.name=name
        self.symbols={k:v['value'] for k,v in self.elf.symbols.items()}
        self.spans=[(s['va'],self.elf.content(s)) for s in self.elf.sections if s['flags']&2 and s['type']==1]
        text=subprocess.check_output([str(OBJDUMP),'-d',str(path)],text=True)
        (LOCAL/(name+'.disasm')).write_text(text)
        self.code={};self.width={};self.verified_bytes=0
        for m in re.finditer(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*?)\s*$',text,re.M):
            pc=int(m[1],16);raw=bytes.fromhex(m[2]);assert 0<len(raw)<=16
            assert raw==bytes(self.byte(pc+i) for i in range(len(raw))),(name,hex(pc),'objdump bytes')
            self.verified_bytes+=len(raw)
            if len(raw) not in (2,4):continue
            self.width[pc]=len(raw)
            parts=re.split(r' -> | \|\| ',m[3])
            self.code[pc]=tuple(self.parse(op) for op in parts)
        self.sha256=hashlib.sha256(path.read_bytes()).hexdigest()
    def byte(self,address):
        for start,data in self.spans:
            if start<=address<start+len(data):return data[address-start]
        return 0
    @staticmethod
    def parse(op):
        op=re.sub(r' <[^>]*>','',op).strip();name,*tail=op.split(' ',1)
        args=re.split(r',(?=[^)]*(?:\(|$))',tail[0]) if tail else []
        # The only parenthesized operand is @(signed offset,base register).
        if tail:args=re.findall(r'@\([^)]*\)|[^,]+',tail[0])
        return name,tuple(args)

class Cpu:
    def __init__(self,program):
        self.p=program;self.r=[0]*16;self.r[14]=END;self.r[15]=0x206ffffc
        self.psw=0xc1;self.mem={};self.forbidden=[];self.accesses=[];self.stubs={};self.calls=[]
    def check(self,address,n,kind):
        assert 0x20000000<=address and address+n<=0x20800000,(kind,hex(address),n)
        assert not any(address<end and address+n>start for start,end in self.forbidden),(kind,'forbidden',hex(address),n)
        self.accesses.append((kind,address,n))
    def read(self,address,n=4):
        self.check(address,n,'read')
        return int.from_bytes(bytes(self.mem.get(address+i,self.p.byte(address+i)) for i in range(n)),'big')
    def write(self,address,value,n=4):
        self.check(address,n,'write')
        for i,b in enumerate((value&((1<<(8*n))-1)).to_bytes(n,'big')):self.mem[address+i]=b
    def seed(self,address,value,n=4):
        for i,b in enumerate((value&((1<<(8*n))-1)).to_bytes(n,'big')):self.mem[address+i]=b
    def address(self,operand):
        m=re.fullmatch(r'@\((-?\d+),(\w+)\)',operand)
        if m:return (self.r[reg(m[2])]+int(m[1]))&0xffffffff
        assert operand.startswith('@');return self.r[reg(operand[1:])]
    def condition(self,value):self.psw=(self.psw&~1)|int(value)
    def op(self,name,args,pc):
        a=args[0] if args else '';d=reg(a);s=reg(args[1]) if len(args)>1 else -1
        imm=lambda value:int(value.removeprefix('#'),0)
        if name=='nop':return
        if name=='push':self.r[15]-=4;self.write(self.r[15],self.r[d])
        elif name=='pop':self.r[d]=self.read(self.r[15]);self.r[15]+=4
        elif name=='mv':self.r[d]=self.r[s]
        elif name=='mvfc':assert args[1] in ('psw','cbr');self.r[d]=self.psw if args[1]=='psw' else self.psw&1
        elif name=='mvtc':assert args[1]=='psw';self.psw=self.r[d]
        elif name=='ldi':self.r[d]=imm(args[1])&0xffffffff
        elif name=='ld24':self.r[d]=int(args[1],16)
        elif name=='seth':self.r[d]=imm(args[1])<<16
        elif name in ('ld','ldub','ldb','lduh','ldh'):
            n=4 if name=='ld' else 2 if name in ('lduh','ldh') else 1
            value=self.read(self.address(args[1]),n)
            if name in ('ldb','ldh') and value&(1<<(8*n-1)):value-=1<<(8*n)
            self.r[d]=value&0xffffffff
        elif name in ('st','stb','sth'):self.write(self.address(args[1]),self.r[d],4 if name=='st' else 1 if name=='stb' else 2)
        elif name in ('add','sub','and','or','xor','mul','srl','sll'):
            x,y=self.r[d],self.r[s]
            value={'add':lambda:x+y,'sub':lambda:x-y,'and':lambda:x&y,'or':lambda:x|y,
                   'xor':lambda:x^y,'mul':lambda:x*y,'srl':lambda:x>>(y&31),'sll':lambda:x<<(y&31)}[name]()
            self.r[d]=value&0xffffffff
        elif name in ('or3','and3','add3','xor3'):
            x,y=self.r[s],imm(args[2]);self.r[d]=({'or3':x|y,'and3':x&y,'add3':x+y,'xor3':x^y}[name])&0xffffffff
        elif name in ('addi','slli','srli'):
            x,y=self.r[d],imm(args[1]);self.r[d]=({'addi':lambda:x+y,'slli':lambda:x<<y,'srli':lambda:x>>y}[name]())&0xffffffff
        elif name in ('cmpu','cmpui','cmpeq'):
            y=imm(args[1])&0xffffffff if name=='cmpui' else self.r[s]
            self.condition(self.r[d]==y if name=='cmpeq' else self.r[d]<y)
        elif name in ('bra','bl','bc','bnc'):
            take=name in ('bra','bl') or bool(self.psw&1)==(name=='bc')
            if take:
                if name=='bl':self.r[14]=(pc&~3)+4
                return int(a,16)
        elif name in ('beqz','bnez','bgtz','blez','bgez','bltz'):
            value=self.r[d];signed=value-(1<<32) if value&(1<<31) else value
            take={'beqz':value==0,'bnez':value!=0,'bgtz':signed>0,'blez':signed<=0,'bgez':signed>=0,'bltz':signed<0}[name]
            if take:return int(args[1],16)
        elif name in ('beq','bne'):
            if (self.r[d]==self.r[s])==(name=='beq'):return int(args[2],16)
        elif name in ('jmp','jl'):
            target=self.r[d]&~3
            if name=='jl':self.r[14]=(pc&~3)+4
            return target
        else:raise AssertionError((self.p.name,hex(pc),name,args))
    def run(self,symbol,args=(),bound=2000):
        for i,value in enumerate(args):self.r[i]=value
        self.r[14]=END;pc=self.p.symbols[symbol];sp=self.r[15]
        for _ in range(bound):
            if pc==END:
                assert self.r[15]==sp,(symbol,'SP imbalance');return self.r[0]
            if pc in self.stubs:
                self.calls.append(pc);self.stubs[pc](self);pc=self.r[14];continue
            assert pc in self.p.code,(self.p.name,symbol,'unmapped PC',hex(pc))
            target=None
            for i,(name,operands) in enumerate(self.p.code[pc]):
                target=self.op(name,operands,pc+2*i)
                if target is not None:break
            pc=pc+self.p.width[pc] if target is None else target
        raise AssertionError((symbol,'instruction bound',hex(pc)))

def fresh(program):
    c=Cpu(program);c.seed(ROOT_ADDRESS,0x52565333);c.seed(ROOT_ADDRESS+4,32,1)
    c.seed(ROOT_ADDRESS+5,3,1);c.seed(ROOT_ADDRESS+212,0)
    c.seed(0x2022f5a8,0x2022d610);c.seed(0x2022f5ac,7,1)
    c.seed(0x2022f725,1,1);c.seed(0x2022f726,1,1)
    c.seed(0x205a27d8,NATIVE);c.seed(0x205a27d4,1,1)
    c.seed(NATIVE,33,1);c.seed(NATIVE+4,0x2022f71c)
    return c

def f08(resident,services):
    cases=[]
    for p,abort in ((resident,'rv_ui_abort'),(services,'es_ui_abort')):
        capture='es_ui_capture' if p is services else None
        if capture:
            for array in (NATIVE,NATIVE+4,0x205b0000,0x20720000,0x207ffff0,0xffffffff,0):
                c=fresh(p);c.seed(0x205a27d8,array);c.forbidden=[(0x20720000,0x20720010)]
                result=c.run(capture,[ROOT_ADDRESS]);assert result==(1 if array==NATIVE else 0)
                assert not any(k=='write' and a in (0x2022f5a8,0x2022f5ac) for k,a,n in c.accesses)
                cases.append(dict(artifact=p.name,case='fixed-array-admission',array=f'{array:08x}',result=result))
        for which in ('expired-slot','reused-slot','two-fixed-slots','buried-fixed-slot','native-replacement','expired-snapshot','forged-old-record'):
            c=fresh(p);snap=0x20724000
            if which in ('expired-slot','reused-slot'):
                c.seed(0x205a27d8,0x20720000);c.forbidden=[(0x20720000,0x20720010)]
            else:
                c.seed(ROOT_ADDRESS+156,0x2022d610);c.seed(ROOT_ADDRESS+160,7)
                c.seed(ROOT_ADDRESS+196,1);c.seed(ROOT_ADDRESS+200,1);c.seed(ROOT_ADDRESS+204,snap)
                c.seed(NATIVE+4,snap)
                c.seed(NATIVE+8,33 if which=='two-fixed-slots' else 41,1)
                c.seed(NATIVE+12,snap if which=='two-fixed-slots' else 0x20240000)
                c.seed(0x205a27d4,2,1)
                if which=='native-replacement':c.seed(NATIVE+4,0x20240000)
                if which=='forged-old-record':c.seed(ROOT_ADDRESS+168,0x20720004);c.seed(ROOT_ADDRESS+188,0x2072000c)
                c.forbidden=[(0x20720000,0x20725000)]
            result=c.run(abort,[ROOT_ADDRESS]);assert result==0 and c.psw==0xc1
            assert c.read(0x2022f5a8)==0x2022d610 and c.read(0x2022f5ac,1)==7
            if which not in ('expired-slot','reused-slot'):
                assert c.read(NATIVE+4)==(0x20240000 if which=='native-replacement' else 0x2022f71c)
                assert c.read(NATIVE+12)==(0x2022f71c if which=='two-fixed-slots' else 0x20240000)
            writes=sorted({a for k,a,n in c.accesses if k=='write' and NATIVE<=a<NATIVE+16})
            assert all(a in (NATIVE+4,NATIVE+12) for a in writes)
            cases.append(dict(artifact=p.name,case=which,status='PASS',view_writes=[f'{a:08x}' for a in writes]))
    return cases

def h07(p):
    layout=json.loads((HERE/'local/resident/target-layout.json').read_text())
    fields=layout['RvSession']['fields'];qoff=fields['call_request']['offset'];roff=fields['call_reply']['offset']
    rows=[]
    for keep,result,psw in itertools.product(range(2),range(4),(0,1,0x40,0x41,0x80,0x81,0xc0,0xc1)):
        c=fresh(p);c.psw=psw;snap=0x20724000
        c.seed(ROOT_ADDRESS+156,0x2022d610);c.seed(ROOT_ADDRESS+160,7)
        c.seed(ROOT_ADDRESS+136,snap)
        c.seed(ROOT_ADDRESS+180,0x20724100);c.seed(ROOT_ADDRESS+196,1);c.seed(ROOT_ADDRESS+200,1);c.seed(ROOT_ADDRESS+204,snap)
        c.seed(0x2022f5a8,0x20724100);c.seed(NATIVE+4,snap)
        c.seed(0x205d9bf8,8);c.seed(0x205d9c00,56);c.seed(0x205a280f,2,1)
        c.seed(FRAME+44,keep);c.seed(FRAME+28,0x29);c.seed(FRAME+64,0x202bd890)
        observed=[]
        def check(cpu):cpu.r[0]=0
        def session(cpu):cpu.r[0]=SESSION
        def engine(cpu):
            assert cpu.r[2]==SESSION+qoff and cpu.r[3]==SESSION+roff
            q=cpu.r[2];observed.append(tuple(cpu.read(q+8+4*i) for i in (8,9,12,13)))
            if result==3:cpu.seed(ROOT_ADDRESS+5,6,1);cpu.seed(ROOT_ADDRESS+212,33)
            cpu.r[:8]=[0xc0010000+i for i in range(8)];cpu.r[0]=result
        c.stubs={p.symbols['rv_check']:check,p.symbols['rv_session']:session,p.symbols['rv_engine']:engine}
        c.run('rv_hook_observe',[ROOT_ADDRESS,7,FRAME])
        close=keep==0 or result>=2
        assert c.read(FRAME+4)==p.symbols['rv_close_07' if close else 'rv_skip_07'],(keep,result,psw,hex(c.read(FRAME+4)),observed)
        assert c.read(FRAME+60)==1 and observed==[(7,keep,0x202bd890,0x29)]
        assert (c.read(ROOT_ADDRESS+156)==0)==(keep==0 or result!=1)
        rows.append(dict(native_keep=keep,engine_result=result,psw=psw,route='close' if close else 'keep',status='PASS'))
    return rows

def grain(resident,stage):
    modes=[stage.byte(stage.symbols['rfw_defaults']+49*i+33) for i in range(6)]
    mode=modes[0];assert 0<=mode<=6
    cache=0x20600000;tables=0x20604000;settings=0x20500000;packet=0x20502000
    c=fresh(resident);old=Cpu(stage)
    old.stubs[stage.symbols['current']]=lambda cpu:cpu.r.__setitem__(0,cache)
    old.seed(cache+0xdd1,0,1);old.seed(cache+0xdd4,1,1);old.seed(cache+0xdd0,1,1);old.seed(cache+0xdd8,tables)
    old.seed(tables+16+448,1,1);old.seed(tables+16+448+1,8,1)
    c.seed(ROOT_ADDRESS+7,0x80|mode,1)
    for cpu in (c,old):
        cpu.seed(0x200c0dac,settings);cpu.seed(0x200c0db0,4096);cpu.seed(settings+0x36e,mode,1)
    baseline=bytes((i*37+11)&255 for i in range(128))
    baseline=bytearray(baseline)
    for i in (0x1a,0x14,0x75,0x1e,0x26):baseline[i]=0
    count=0;digest=hashlib.sha256()
    def compare(level,size,category=0,gate=None,length=4096,s_address=settings,selector=None):
        nonlocal count
        sample=bytearray(baseline)
        if gate is not None:sample[gate]=1
        for cpu in (c,old):
            cpu.seed(0x200c0dac,s_address);cpu.seed(0x200c0db0,length)
            current=s_address or settings
            cpu.seed(current+0x36e,mode if selector is None else selector,1)
            cpu.seed(current+0x3aa,size,1);cpu.seed(current+0xc9d,level,1);cpu.seed(0x205d9a7f,category,1)
            for i,value in enumerate(sample):cpu.seed(packet+i,value,1)
            cpu.accesses.clear()
        c.run('rv_grain',[ROOT_ADDRESS,packet]);old.run('rfw_grain_check',[packet])
        a=bytes(c.mem[packet+i] for i in range(128));b=bytes(old.mem[packet+i] for i in range(128))
        assert a==b,(level,size,category,gate,length,s_address,a.hex(),b.hex())
        allowed=size in (1,2,5,8,12,16) and category in (0,4) and gate is None and length>=0xc9e and s_address!=0 and selector in (None,mode)
        expected=bytearray(sample)
        if allowed:expected[0x1a]=21;expected[0x10]=0;expected[0x32]=1;expected[0x6f]=level if 1<=level<=3 else 1
        assert a==expected,(level,size,'independent literal packet')
        digest.update(a);count+=1
    for level,size in itertools.product(range(256),range(256)):compare(level,size,4 if level&1 else 0)
    for category in range(256):compare(3,1,category)
    for offset in (0x1a,0x14,0x75,0x1e,0x26):compare(3,1,gate=offset)
    for length in (0,0xc9d,0xc9e,4096):compare(2,2,length=length)
    compare(2,2,s_address=0)
    compare(1,2,s_address=0x20504000)
    for slot,mode in enumerate(modes,1):
        c.seed(ROOT_ADDRESS+7,0x80|mode,1);old.seed(tables+16+448,slot,1)
        for selector,level,size in itertools.product(range(8),(0,1,2,3,4,255),(0,1)):
            compare(level,size,selector=selector)
    return dict(status='PASS',packet_cases=count,packet_bytes=128,levels=256,sizes=256,categories=256,
                allowed_sizes=[1,2,5,8,12,16],result_sha256=digest.hexdigest(),stage_base_modes=modes,
                current_double='valid Stage2l cache; committed entry has GRAIN; tables_ok=1, uncertain=0',
                current_S_read_on_every_call=True)

def past_mistakes():
    p=Program('v31-negative',ROOT/'firmware/resident_v31/local/resident/build/resident.elf')
    c=fresh(p);snap=0x20724000
    c.seed(ROOT_ADDRESS+156,0x2022d610);c.seed(ROOT_ADDRESS+160,7)
    c.seed(ROOT_ADDRESS+168,0x20720004);c.seed(ROOT_ADDRESS+172,0x2022f71c);c.seed(ROOT_ADDRESS+204,snap)
    c.forbidden=[(0x20720000,0x20720010)]
    try:c.run('rv_ui_abort',[ROOT_ADDRESS])
    except AssertionError as error:
        assert error.args[0][0:2]==('read','forbidden'),error.args
        expired=dict(status='REJECTED_OLD_CODE',fault=str(error))
    else:raise AssertionError('old expired-slot bug was not detected')
    c=fresh(p);s=0x20500000;packet=0x20502000
    c.seed(ROOT_ADDRESS+7,0x84,1);c.seed(ROOT_ADDRESS+232,s);c.seed(ROOT_ADDRESS+236,4096);c.seed(ROOT_ADDRESS+240,0x103)
    c.seed(0x200c0dac,s);c.seed(0x200c0db0,4096);c.seed(s+0x36e,4,1);c.seed(s+0x3aa,1,1);c.seed(s+0xc9d,1,1)
    c.run('rv_grain',[ROOT_ADDRESS,packet]);assert c.read(packet+0x6f,1)==3
    c.seed(packet+0x1a,0,1);c.seed(s+0x3aa,2,1)
    c.run('rv_grain',[ROOT_ADDRESS,packet]);assert c.read(packet+0x1a,1)==0
    return dict(status='PASS',v31_elf_sha256=p.sha256,F08=expired,
                F10=dict(status='REJECTED_OLD_CODE',live_level=1,old_packet_level=3,
                         allowed_size_changed_1_to_2_old_passthrough=True))

def main():
    spec=importlib.util.spec_from_file_location('policy_guard',HERE/'resident/build.py')
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard);guard.preflight()
    LOCAL.mkdir(exist_ok=True)
    resident=Program('resident',HERE/'local/resident/build/resident.elf')
    services=Program('services',HERE/'local/resident/engine-services/services-linkcheck.elf')
    stage=Program('stage2l',ROOT/'firmware/stage2l_switch/build/payload.elf')
    result=dict(status='PASS',F08=f08(resident,services),H07=h07(resident),H09=grain(resident,stage),
                negative_controls=past_mistakes(),
                artifacts={p.name:dict(sha256=p.sha256,objdump_bytes_verified=p.verified_bytes) for p in (resident,services,stage)},
                native_m32r_execution=False,limits=__doc__)
    assert not any(name.startswith(('rv_post_','rv_notify','rv_epochs')) for name in resident.symbols)
    removed=[]
    for hook in (17,18,20,22):
        c=fresh(resident);c.seed(FRAME+64,END);before=dict(c.mem)
        c.run('rv_hook_observe',[ROOT_ADDRESS,hook,FRAME])
        assert all(c.mem[a]==value for a,value in before.items())
        assert all(kind!='write' or 0x206ff000<=address<0x20700000 for kind,address,n in c.accesses)
        removed.append(hook)
    result['F03']=dict(status='PASS',post_symbols_absent=True,removed_hooks_have_no_observer_effect=removed,
                       old_post_counterexample_has_no_executable_entry=True)
    (LOCAL/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS policy instructions: F08='+str(len(result['F08']))+' H07='+str(len(result['H07']))+' H09='+str(result['H09']['packet_cases']))

if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        raw=traceback.format_exc();folder=LOCAL/'failures';folder.mkdir(parents=True,exist_ok=True)
        (folder/(hashlib.sha256(raw.encode()).hexdigest()[:12]+'.log')).write_text(raw)
        raise
