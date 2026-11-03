#!/usr/bin/env python3
"""Replay emitted M32R instructions with explicit external-service models.

No camera, hardware MMIO, timing, or cache behavior is emulated. Positive
cache cases are assumptions used to test ordering and failure detection.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BUILD=HERE/'local/build'
OUT=ROOT/'research/stage2k_p0/local'
HALT=0xeeee0000
CACHE=0x20705000
STACK=0x30010000
MCCR=0xfffffffc


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decode(text,bias=0):
    code={}
    for line in text.splitlines():
        m=re.match(r'\s*([0-9a-f]+):\s*((?:[0-9a-f]{2}\s+){3}[0-9a-f]{2})\s+(.*)',line)
        if m:
            assert len(m[2].split())==4
            operations=re.split(r'\s*(?:->|\|\|)\s*',re.sub(r' <[^>]*>','',m[3]))
            code[int(m[1],16)+bias]=(operations,bias,'||' in m[3])
    return code


class VM:
    def __init__(self,code):
        self.code=copy.deepcopy(code)
        self.r=[0x11000000+i*0x101 for i in range(16)]
        self.r[14]=HALT
        self.r[15]=STACK
        self.initial=self.r[:]
        self.mem={}
        self.c=False
        self.callbacks={}
        self.trace=[]
        self.steps=0
        self.minimum_sp=STACK
        self.heap_word=None
        self.heap_calls=[]
        self.sync_count=0
        self.last_sync=0
        self.write_generation=0
        self.instruction_cache={}
        self.stale=False
        # MCCR model. ASSUMPTION (native contract at 0x2004bacc/0x20093114/
        # 0x200932cc, not hardware-proven): when caches are on (bit0), a store
        # of a value with bits 0x101 set writes back D-cache and invalidates
        # I-cache. With bit0 clear, memory is treated as coherent.
        self.mccr_writes=[]
        self.mccr_effective=True

    @staticmethod
    def reg(s):
        return {'sp':15,'lr':14,'fp':13}.get(s,int(s[1:]) if s.startswith('r') else -1)

    def put(self,address,value,size=4):
        value &= (1<<(8*size))-1
        if address==MCCR:
            assert size==4, 'MCCR must be written as a full word'
            before=self.get(MCCR)
            self.mccr_writes.append((before,value))
            # The native sites only ever OR 0x101 into a value whose bit0 was
            # set; any other configuration change would be a different action.
            assert before&1, 'MCCR written while caches were reported off'
            assert value&~0x101==before&~0x101, 'MCCR configuration bits changed'
            if value&0x101==0x101:
                # The store is ordered after the heap write (ordering proof).
                self.last_sync=self.write_generation
                # Whether it actually drops stale I-cache lines is the on-camera
                # unknown; mccr_effective=False models an ineffective write.
                if self.mccr_effective:
                    self.instruction_cache.clear()
        for i,b in enumerate(value.to_bytes(size,'big')):
            self.mem[address+i]=b
        if address==self.heap_word and size==4:
            self.write_generation+=1

    def get(self,address,size=4,signed=False):
        data=bytes(self.mem.get(address+i,0) for i in range(size))
        return int.from_bytes(data,'big',signed=signed)&0xffffffff

    def data(self,address,data):
        for i,b in enumerate(data):
            self.mem[address+i]=b

    def string(self,address,limit=100):
        data=bytearray()
        for i in range(limit):
            b=self.mem.get(address+i,0)
            if b==0:
                return data.decode('ascii')
            data.append(b)
        raise AssertionError('unterminated string')

    def address(self,s):
        if s.startswith('@('):
            m=re.fullmatch(r'@\((-?\d+),(\w+)\)',s)
            assert m,s
            return (self.r[self.reg(m[2])]+int(m[1]))&0xffffffff
        assert s.startswith('@'),s
        return self.r[self.reg(s[1:])]

    def ret(self,value,native=False):
        target=self.r[14]
        for i in range(14 if native else 8):
            self.r[i]=0xcccc0000+i
        self.r[14]=0xcccccccc
        self.r[0]=value&0xffffffff
        return target

    def run(self,pc,limit=20000):
        for _ in range(limit):
            self.steps+=1
            self.minimum_sp=min(self.minimum_sp,self.r[15])
            if pc==HALT:
                return
            if pc in self.callbacks:
                pc=self.callbacks[pc](self)
                continue
            if pc==self.heap_word:
                caches_on=bool(self.get(MCCR)&1)
                assert self.last_sync==self.write_generation or not caches_on, \
                    'heap fetch before successful synchronization'
                word=self.get(pc)
                if caches_on:
                    word=self.instruction_cache.setdefault(pc,word)
                assert word>>24==0x60 and word&0xffff==0x1fce, 'not a four-byte return stub'
                value=(word>>16)&0xff
                self.heap_calls.append(value)
                self.trace.append(('heap',value))
                pc=self.ret(value)
                continue
            assert pc in self.code,f'unknown execution target {pc:#x}'
            operations,bias,parallel=self.code[pc]
            assert not parallel or operations[-1]=='nop', 'non-nop parallel issue is outside this model'
            next_pc=pc+4
            for ins in operations:
                op,_,tail=ins.partition(' ')
                args=re.split(r',\s*(?![^()]*\))',tail) if tail else []
                r=self.r
                reg=self.reg
                imm=lambda s:int(s.lstrip('#'),0)
                if op=='nop':
                    continue
                if op=='push':
                    r[15]-=4
                    self.put(r[15],r[reg(args[0])])
                elif op=='pop':
                    r[reg(args[0])]=self.get(r[15])
                    r[15]+=4
                elif op=='mv':
                    r[reg(args[0])]=r[reg(args[1])]
                elif op=='ldi':
                    r[reg(args[0])]=imm(args[1])&0xffffffff
                elif op=='ld24':
                    r[reg(args[0])]=int(args[1],16)
                elif op=='seth':
                    r[reg(args[0])]=imm(args[1])<<16
                elif op in ('or3','and3','add3','sll3','sra3','srl3'):
                    a=r[reg(args[1])]
                    b=imm(args[2])
                    value={'or3':lambda:a|b,'and3':lambda:a&b,'add3':lambda:a+b,
                        'sll3':lambda:a<<b,'srl3':lambda:a>>b,
                        'sra3':lambda:self.signed(a)>>b}[op]()
                    r[reg(args[0])]=value&0xffffffff
                elif op in ('addi','slli','srli','srai'):
                    a=r[reg(args[0])]
                    b=imm(args[1])
                    value={'addi':lambda:a+b,'slli':lambda:a<<b,'srli':lambda:a>>b,
                           'srai':lambda:self.signed(a)>>b}[op]()
                    r[reg(args[0])]=value&0xffffffff
                elif op in ('add','sub','and','or','mul','divu','remu'):
                    a=r[reg(args[0])]
                    b=r[reg(args[1])]
                    value={'add':lambda:a+b,'sub':lambda:a-b,'and':lambda:a&b,
                        'or':lambda:a|b,'mul':lambda:a*b,'divu':lambda:a//b,
                        'remu':lambda:a%b}[op]()
                    r[reg(args[0])]=value&0xffffffff
                elif op in ('ld','ldub','lduh','ldb','ldh'):
                    size={'ld':4,'ldub':1,'lduh':2,'ldb':1,'ldh':2}[op]
                    r[reg(args[0])]=self.get(self.address(args[1]),size,op in ('ldb','ldh'))
                elif op in ('st','stb','sth'):
                    self.put(self.address(args[1]),r[reg(args[0])],{'st':4,'stb':1,'sth':2}[op])
                elif op in ('cmp','cmpu','cmpi','cmpui'):
                    a=r[reg(args[0])]
                    b=imm(args[1]) if op.endswith('i') else r[reg(args[1])]
                    self.c=(a&0xffffffff)<(b&0xffffffff) if 'u' in op else self.signed(a)<self.signed(b)
                elif op in ('bl','bra'):
                    if op=='bl':
                        r[14]=pc+4
                    next_pc=int(args[0],16)+bias
                    break
                elif op in ('jl','jmp'):
                    target=r[reg(args[0])]
                    if op=='jl':
                        r[14]=pc+4
                    next_pc=target
                    break
                elif op in ('beq','bne','beqz','bnez','bltz','bgez','bgtz','blez','bc','bnc'):
                    if op in ('bc','bnc'):
                        take=self.c if op=='bc' else not self.c
                    elif op in ('beq','bne'):
                        take=(r[reg(args[0])]==r[reg(args[1])]) == (op=='beq')
                    else:
                        value=self.signed(r[reg(args[0])])
                        take={'beqz':value==0,'bnez':value!=0,'bltz':value<0,
                              'bgez':value>=0,'bgtz':value>0,'blez':value<=0}[op]
                    if take:
                        next_pc=int(args[-1],16)+bias
                        break
                else:
                    raise AssertionError('unsupported instruction: '+ins)
            pc=next_pc
        raise AssertionError('execution limit reached')

    @staticmethod
    def signed(value):
        value &= 0xffffffff
        return value-(1<<32) if value>>31 else value


def fixture(code,symbols,slot=8,*,opened=1,busy=0,occupied=1,load_status=0,
            present=False,read_count=None,close=0,alloc=True,corrupt=False,
            sync=None,heap=0x20708004,cache=CACHE,mccr=0x00000001,mccr_effective=True):
    vm=VM(code)
    vm.r[0]=slot
    vm.initial=vm.r[:]
    vm.data(MCCR,mccr.to_bytes(4,'big'))  # initial value, not a modeled write
    vm.mccr_effective=mccr_effective
    vm.data(CACHE,bytes(3548))
    vm.put(CACHE+3532,busy,1)
    vm.put(CACHE+3533,opened,1)
    vm.put(CACHE+3524,load_status)
    vm.put(0x2022f726,1,1)
    for i in range(16):
        vm.put(CACHE+1668+50*i,occupied,1)
    helper=(BUILD/'P0.BIN').read_bytes()
    elfmod=load('p0_old_elf',ROOT/'firmware/stage2j/tools/build.py')
    pe=elfmod.Elf(BUILD/'probe.elf')
    for s in pe.sections:
        if s['name'] in ('.early','.late','.probe'):
            vm.data(s['va'],pe.content(s))
    vm.heap_word=heap
    vm.formatted=[]
    vm.module_entered=False
    vm.events=[]
    def current(v):
        return v.ret(cache)
    def is_open(v):
        return v.ret(opened)
    def apply(v):
        v.events.append(('apply',v.r[1]))
        return v.ret(0)
    def file_open(v):
        assert v.string(v.r[0])=='/ATA1/P' and v.r[1]==0
        v.events.append(('open',))
        return v.ret(7 if present else -1)
    def allocate(v):
        assert v.r[0]==len(helper)
        v.events.append(('alloc',v.r[0]))
        return v.ret(heap if alloc else 0)
    def read(v):
        assert v.r[:3]==[7,heap,len(helper)]
        data=bytearray(helper)
        if corrupt:
            data[21]^=1
        n=len(helper) if read_count is None else read_count
        v.data(heap,data[:max(0,min(n,len(data)))])
        v.events.append(('read',n))
        return v.ret(n)
    def file_close(v):
        assert v.r[0]==7
        v.events.append(('close',))
        return v.ret(close)
    def free(v):
        assert v.r[4]==heap, 'native free did not receive the owned original pointer in r4'
        v.events.append(('free',v.r[4]))
        return v.ret(0,native=True)
    def crc(v):
        value=zlib.crc32(bytes(v.mem.get(v.r[0]+i,0) for i in range(v.r[1])))
        v.events.append(('crc',value))
        return v.ret(value)
    def sync_model(v):
        v.sync_count+=1
        v.events.append(('sync_assumption',v.sync_count))
        ok=(sync=='ok' or sync=='stale' or (sync=='second_fails' and v.sync_count==1))
        if ok:
            v.last_sync=v.write_generation
            if sync!='stale':
                v.instruction_cache.clear()
        return v.ret(int(ok))
    vm.callbacks.update({symbols['current']:current,symbols['rfw_is_open']:is_open,
        symbols['rv1_apply']:apply,symbols['gxr_open']:file_open,
        symbols['gxr_alloc']:allocate,symbols['gxr_read']:read,
        symbols['gxr_close']:file_close,symbols['rv1_crc32']:crc,
        0x2005c038:free})
    if sync is not None:
        vm.callbacks[pe.symbols['p0_sync']['value']]=sync_model
    vm.code.update(decode((BUILD/'module-disasm.txt').read_text(),heap))
    def measured(v):
        v.events.append(('measurement_assumption',v.r[0]))
        assert v.r[0] in (1<<22,1<<24)
        return v.ret(100 if v.r[0]==1<<22 else 400)
    def language(v):
        return v.ret(0)
    def ascii_text(v):
        text=v.string(v.r[0])
        assert len(text)==v.r[1]
        assert CACHE+128<=v.r[2]<CACHE+1664
        v.formatted.append(text)
        v.data(v.r[2],text.encode()+b'\0')
        return v.ret(0)
    vm.callbacks[heap+0x14]=measured
    vm.callbacks[0x2005280c]=language
    vm.callbacks[0x20052800]=ascii_text
    return vm


def application_memory(vm):
    return {k:v for k,v in vm.mem.items() if not STACK-0x1000<=k<STACK
            and not 0x2005276c<=k<0x20054800}


def main():
    load('p0_capture',ROOT/'research/stage2k_p0/capture.py').preflight()
    elfmod=load('p0_elf',ROOT/'firmware/stage2j/tools/build.py')
    old=elfmod.Elf(ROOT/'firmware/stage2j/build/payload.elf')
    symbols={name:item['value'] for name,item in old.symbols.items()}
    old_code=decode((ROOT/'firmware/stage2j/build/payload-disasm.txt').read_text())
    new_code=dict(old_code)
    new_code.update(decode((BUILD/'probe-disasm.txt').read_text()))
    resident=elfmod.Elf(BUILD/'probe.elf')
    entry=resident.symbols['p0_select']['value']
    sync_va=resident.symbols['p0_sync']['value']
    free_va=resident.symbols['p0_free']['value']
    new_code[0x2005324c]=([f'bl {entry:08x}'],0,False)
    results=[]
    def record(name,**details):
        results.append(dict(case=name,passed=True,**details))
    for slot in range(18):
        for opened,busy,occupied,status in ((1,0,1,0),(0,0,1,0),(1,1,1,0),
                                           (1,0,0,0),(1,0,1,6)):
            a=fixture(old_code,symbols,slot,opened=opened,busy=busy,occupied=occupied,load_status=status)
            b=fixture(new_code,symbols,slot,opened=opened,busy=busy,occupied=occupied,load_status=status)
            a.run(symbols['rfw_select'])
            b.run(symbols['rfw_select'])
            assert a.r[0]==b.r[0] and a.r[8:]==b.r[8:]
            assert application_memory(a)==application_memory(b)
            assert [x for x in a.events if x[0]=='apply']==[x for x in b.events if x[0]=='apply']
            assert b.r[8:]==b.initial[8:]
            assert all(x[0]=='apply' or x==('open',) for x in b.events)
            if slot!=8 or not opened or busy:
                assert not any(x[0]=='open' for x in b.events)
            record(f'disabled/{slot}/{opened}/{busy}/{occupied}/{status}')
    # Failure before the A/B ever runs: every path must close, free, clear the
    # busy flag, apply nothing, and return NULL (modeled as slot 6 == r0 6).
    # 'fail'/'stale'/'second_fails' install a cache MODEL in place of the real
    # p0_sync, standing in for on-camera behaviors the host cannot emulate:
    #   fail         -> sync reports failure (our real routine cannot, but the
    #                   error path is proven to clean up anyway)
    #   stale        -> sync claims success yet the I-cache keeps old bytes;
    #                   B reads A's magic (49) twice and the B-check rejects it
    #   second_fails -> first sync ok, second fails
    for description,options in [
        ('allocation-failure',dict(alloc=False)),
        ('read-error',dict(read_count=-1)),('short-read',dict(read_count=20)),
        ('overcount',dict(read_count=10000)),('close-error',dict(close=-1)),
        ('CRC-reject',dict(corrupt=True)),('sync-reject-assumption',dict(sync='fail')),
        ('second-sync-reject-assumption',dict(sync='second_fails')),
        ('stale-instruction-assumption',dict(sync='stale')),
        # Real emitted p0_sync, but modeled as an INEFFECTIVE 0x101 write:
        # ordering holds, invalidation does not -> same stale rejection.
        ('ineffective-sync-rejected',dict(mccr_effective=False))]:
        v=fixture(new_code,symbols,present=True,**options)
        v.run(symbols['rfw_select'])
        assert v.r[0]==6 and v.r[8:]==v.initial[8:]
        assert v.get(CACHE+3532,1)==0
        assert sum(x[0]=='close' for x in v.events)==1
        assert sum(x[0]=='free' for x in v.events)==int(options.get('alloc',True))
        assert not v.formatted and not any(x[0]=='apply' for x in v.events)
        if description in ('stale-instruction-assumption','ineffective-sync-rejected'):
            assert v.heap_calls==[49,49]
        record(description,events=v.events,heap_calls=v.heap_calls,modeled_stack_from_select_entry=STACK-v.minimum_sp)
    # Success path. Two models, both exercising the REAL emitted p0_sync:
    #   mccr=on + effective  -> 0x101 write invalidates I-cache
    #   mccr=off             -> sync no-ops and returns success; coherent memory
    # Plus the explicit 'ok' callback model for comparison. All must run A then
    # B from the heap and then the measurement helper.
    for label,options in [('real-sync-cache-on',dict(mccr=0x00000001)),
                          ('real-sync-cache-off',dict(mccr=0x00000000)),
                          ('cache-model-ok',dict(sync='ok'))]:
        for heap in (0x20708004,0x20712010,0x20744000):
            v=fixture(new_code,symbols,present=True,heap=heap,**options)
            v.run(symbols['rfw_select'])
            assert v.heap_calls==[49,82]
            assert v.formatted==['06 T00000100','07 T00000400','08 AB ?M']
            assert not any(x[0]=='apply' for x in v.events)
            assert v.get(CACHE+3532,1)==0 and v.r[8:]==v.initial[8:]
            assert sum(x[0]=='free' for x in v.events)==1
            for i in (5,6,7):
                assert v.get(CACHE+64+i*4)==CACHE+128+i*96
            if label=='real-sync-cache-on':
                # Exactly one MCCR store per A/B step, each = old | 0x101.
                assert v.mccr_writes==[(0x1,0x101),(0x101,0x101)], v.mccr_writes
            elif label=='real-sync-cache-off':
                assert v.mccr_writes==[]
            record('A-B-and-helper/'+label,heap=hex(heap),labels=v.formatted,
                   mccr_writes=[(hex(a),hex(b)) for a,b in v.mccr_writes],
                   modeled_stack_from_select_entry=STACK-v.minimum_sp)
    # Direct unit test of the emitted p0_sync over several MCCR values.
    for initial in (0x00000000,0x00000001,0x12340001,0x12340000,0x00000101,0xfffffefe,0xffffffff):
        v=VM(new_code)
        v.data(MCCR,initial.to_bytes(4,'big'))
        v.run(sync_va)
        expect=initial|0x101 if initial&1 else initial
        assert v.get(MCCR)==expect and v.r[0]!=0
        assert v.r[8:]==v.initial[8:] and v.r[15]==STACK
        assert v.mccr_writes==([(initial,expect)] if initial&1 else [])
        record('p0_sync-unit',mccr_in=hex(initial),mccr_out=hex(expect),returns_nonzero=True)
    # Execute the actual short loop and the complete native ABI adapter.
    for count,start,end in ((1,100,107),(7,1000,1033),(19,0xfffffff0,0x10)):
        base=0x20712010
        v=VM(decode((BUILD/'module-disasm.txt').read_text(),base))
        v.r[0]=count
        initial=v.r[:]
        samples=iter((start,end))
        observed=[]
        def clock(t):
            observed.append(t.r[8])
            return t.ret(next(samples),native=True)
        v.callbacks[0x2005f164]=clock
        v.run(base+0x14)
        assert v.r[0]==(end-start)&0xffffffff
        assert v.r[8:]==initial[8:] and observed==[count,0]
        record('native-clock-bridge-and-loop',count=count,tick_delta=v.r[0],
               local_stack_bytes=STACK-v.minimum_sp)
    # Both real callers reject non-ADJ activity before they can enter P0.
    for caller in ('rfw_cursor_commit','rfw_apply_action'):
        v=fixture(new_code,symbols,present=True)
        v.r[0]=1
        v.callbacks[symbols['rfw_ui_active']]=lambda t:t.ret(0)
        v.run(symbols[caller])
        assert not v.events and not v.heap_calls
        record('non-menu-caller-rejected',caller=caller)
    # Three negative controls: break actual emitted control flow and require
    # the behavioral check to notice. These are decoded-instruction mutants.
    v=fixture(new_code,symbols,present=True,sync='ok')
    sync_sites=[pc for pc,(ops,_,_) in v.code.items()
                if any(op==f'bl {sync_va:08x}' for op in ops)]
    assert len(sync_sites)==1
    v.code[sync_sites[0]]=(['ldi r0,#1','nop'],0,False)
    try:
        v.run(symbols['rfw_select'])
    except AssertionError as exc:
        assert 'before successful synchronization' in str(exc)
    else:
        raise AssertionError('missing-sync mutant survived')
    record('negative-control/missing-sync-rejected')
    # Mutant of the REAL p0_sync: drop its MCCR store. With caches on, the
    # heap fetch must be rejected as unsynchronized.
    v=fixture(new_code,symbols,present=True)
    store_sites=[pc for pc,(ops,_,_) in v.code.items()
                 if sync_va<=pc<sync_va+0x18 and any(op=='st r1,@r0' for op in ops)]
    assert len(store_sites)==1
    v.code[store_sites[0]]=(['nop'],0,False)
    try:
        v.run(symbols['rfw_select'])
    except AssertionError as exc:
        assert 'before successful synchronization' in str(exc)
    else:
        raise AssertionError('store-less sync mutant survived')
    record('negative-control/sync-without-MCCR-store-rejected')
    for mutant in ('skip-free','skip-B-check'):
        v=fixture(new_code,symbols,present=True,sync='stale' if mutant=='skip-B-check' else 'ok')
        needle=f'bl {free_va:08x}' if mutant=='skip-free' else 'bne r0,r9'
        sites=[pc for pc,(ops,_,_) in v.code.items() if any(op.startswith(needle) for op in ops)]
        assert len(sites)==1
        v.code[sites[0]]=(['nop'],0,False)
        v.run(symbols['rfw_select'])
        if mutant=='skip-free':
            assert not any(x[0]=='free' for x in v.events)
        else:
            assert v.formatted and v.heap_calls==[49,49]
        record('negative-control/'+mutant+'-detected')
    (OUT/'replay.json').write_text(json.dumps(dict(
        status='HOST_INSTRUCTION_REPLAY_ONLY',camera_executed=False,
        hardware_cache_emulated=False,time_source_emulated=False,
        service_model='explicit models for current/open/IO/allocator/CRC/preview boundary',
        tests=results,count=len(results)),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(replay_cases=len(results),passed=True,hardware_cache_proven=False)))


if __name__=='__main__':
    main()
