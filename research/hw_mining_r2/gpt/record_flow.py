#!/usr/bin/env python3
"""Find bounded, linear consumers of unit-record pointers; not an alias proof."""
import re
import runpy
from pathlib import Path

x=runpy.run_path(str(Path(__file__).with_name('audit.py')))
im=x['Image']()
regs={};accesses=[];calls=[]
BASE=0x200c4f7c
SHADOW=0x2029f30c
def record_offset(v):
    for b in (BASE,SHADOW):
        if b<=v<b+2048:return v-b
    return None

for pc,code,line in im.lines():
    for insn in re.split(r'\s*(?:->|\|\|)\s*',code):
        a=insn.split(None,1);op=a[0] if a else '';args=a[1].split(',') if len(a)>1 else []
        dest=args[0] if args else '';v=None;mem=None
        m=re.search(r'@\((-?\d+),(r\d+|fp|sp|lr)\)|@(\+?)(r\d+|fp|sp|lr)(\+?)',insn)
        if m:
            if m[2]:base=m[2];disp=int(m[1]);inc=0
            else:base=m[4];disp=4 if m[3] else 0;inc=4 if m[3] or m[5] else 0
            if base in regs:mem=(regs[base]+disp)&0xffffffff
            if mem is not None and record_offset(mem) is not None:
                off=record_offset(mem)
                accesses.append(dict(pc=hex(pc),file_offset=hex(im.offset(pc)),address=hex(mem),record_offset=hex(off),
                    matrix_region=0xd8<=off<0x168,text=line))
            if inc and base in regs:regs[base]=(regs[base]+inc)&0xffffffff
        try:
            if op in ('seth','ldi','ld24') and len(args)==2:
                v=int(args[1].lstrip('#'),0)
                if op=='seth':v<<=16
            elif op in ('or3','and3','add3') and len(args)==3 and args[1] in regs:
                s=regs[args[1]];i=int(args[2].lstrip('#'),0)
                v=s|i if op=='or3' else s&i if op=='and3' else s+i
            elif op=='mv' and len(args)==2:v=regs.get(args[1])
            elif op=='addi' and dest in regs:v=regs[dest]+int(args[1].lstrip('#'),0)
            elif op in ('add','sub') and len(args)==2 and all(k in regs for k in args):
                s,t=(regs[k] for k in args);v=s+t if op=='add' else s-t
            elif op in ('slli','srli') and dest in regs:
                n=int(args[1].lstrip('#'),0);v=regs[dest]<<n if op=='slli' else regs[dest]>>n
            elif op in ('jl','bl'):
                t=regs.get(dest) if op=='jl' else int(dest,0)
                related={k:hex(z) for k,z in regs.items() if k in ('r4','r5','r6','r7') and record_offset(z) is not None}
                if related:
                    calls.append(dict(pc=hex(pc),callee=None if t is None else hex(t),record_args=related,
                        other_args={k:hex(z) for k,z in regs.items() if k in ('r4','r5','r6','r7')},text=line))
                flag=regs.get('r4')
                for r in ['r'+str(k) for k in range(8)]+['lr']:regs.pop(r,None)
                if t==0x20052fa8 and flag is not None:regs['r0']=SHADOW if flag==1 else BASE
                continue
            elif op=='jmp':regs.clear();continue
        except (ValueError,IndexError):pass
        if v is not None and re.fullmatch(r'r\d+|fp|sp|lr',dest):regs[dest]=v&0xffffffff
        elif re.fullmatch(r'r\d+|fp|sp|lr',dest) and op not in (
            'st','sth','stb','push','cmp','cmpi','cmpu','cmpui','beq','bne','beqz','bnez','bgez','blez','bltz','bgtz'):
            regs.pop(dest,None)

rows=dict(limit='Linear candidates only. Getter(1) models shadow, other known flags model original; unknown flags are not modeled. '
    'No branch merge, interprocedural alias closure, or proof of no other consumers.',accesses=accesses,calls=calls)
x['save']('evidence/unit-record-pointer-consumers.json',rows)
print('record accesses',len(accesses),'matrix-region accesses',sum(z['matrix_region'] for z in accesses),'pointer calls',len(calls))
for r in accesses:
    if r['matrix_region']:print(r)
for r in calls:print(r)
