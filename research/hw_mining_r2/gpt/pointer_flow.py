#!/usr/bin/env python3
"""Conservative linear pointer candidates; not a CFG or reachability proof."""
import re
import runpy
from pathlib import Path

x=runpy.run_path(str(Path(__file__).with_name('audit.py')));im=x['Image']()
P=0x20383fb8;F=0x20383e98
known={0x2037ff00:P,0x2037fefc:F,
    P+12:0x20143118,P+16:0x20142f90,P+20:0x20142f7c,P+24:0x20143004,P+28:0x201430b4,P+32:0x20142ab0,
    F+8:0x201415e8,F+20:0x20141554,F+28:0x20141584,F+32:0x201426c4,F+44:0x201426cc}
getters={0x2011a768:P,0x201130e8:F}
bands={'MCR':(0x20141584,0x20141594),'REO':(0x201415e8,0x2014160c),
    'type12':(0x201426c4,0x201426c8),'AWBCAM':(0x201426cc,0x201426e4),
    'AWBIP':(0x20142f7c,0x20142f90),'EXIP':(0x20142f90,0x20143000),
    'INP':(0x201430b4,0x20143118)}
def band(a):return next((k for k,(lo,hi) in bands.items() if lo<=a<hi),None)

regs={};stores=[];calls=[]
for pc,code,line in im.lines():
    for insn in re.split(r'\s*(?:->|\|\|)\s*',code):
        a=insn.split(None,1);op=a[0] if a else '';args=a[1].split(',') if len(a)>1 else []
        dest=args[0] if args else '';v=None;mem=None
        match=re.search(r'@\((-?\d+),(r\d+|fp|sp|lr)\)|@(\+?)(r\d+|fp|sp|lr)(\+?)',insn)
        if match:
            if match[2]:base=match[2];disp=int(match[1]);increment=0
            else:
                base=match[4];disp=4 if match[3] else 0;increment=4 if match[5] or match[3] else 0
            if base in regs:mem=(regs[base]+disp)&0xffffffff
            if op in ('st','sth','stb') and mem is not None and band(mem):
                stores.append(dict(pc=hex(pc),file_offset=hex(im.offset(pc)),band=band(mem),address=hex(mem),
                    value=None if dest not in regs else hex(regs[dest]),text=line))
            if increment and base in regs:regs[base]=(regs[base]+increment)&0xffffffff
        try:
            if op in ('seth','ldi','ld24') and len(args)==2:
                v=int(args[1].lstrip('#'),0)
                if op=='seth':v<<=16
            elif op in ('or3','and3','add3') and len(args)==3 and args[1] in regs:
                s=regs[args[1]];imm=int(args[2].lstrip('#'),0)
                v=s|imm if op=='or3' else s&imm if op=='and3' else s+imm
            elif op=='mv' and len(args)==2:v=regs.get(args[1])
            elif op=='addi' and dest in regs:v=regs[dest]+int(args[1].lstrip('#'),0)
            elif op in ('add','sub','or','and') and len(args)==2 and all(k in regs for k in args):
                l,r=(regs[k] for k in args);v=l+r if op=='add' else l-r if op=='sub' else l|r if op=='or' else l&r
            elif op=='neg' and len(args)==2 and args[1] in regs:v=-regs[args[1]]
            elif op in ('slli','srli','srai') and dest in regs:
                n=int(args[1].lstrip('#'),0);s=regs[dest]
                v=s<<n if op=='slli' else s>>n if op=='srli' else (s if s<0x80000000 else s-0x100000000)>>n
            elif op=='ld' and mem in known:v=known[mem]
            elif op in ('jl','bl'):
                t=regs.get(dest)
                if t in (0x2005199c,0x20051914) and regs.get('r4') is not None and band(regs['r4']):
                    calls.append(dict(pc=hex(pc),callee=hex(t),band=band(regs['r4']),args={k:hex(z) for k,z in regs.items()},text=line))
                for r in ['r'+str(k) for k in range(8)]+['lr']:regs.pop(r,None)
                if t in getters:regs['r0']=getters[t]
                continue
            elif op=='jmp':regs.clear();continue
        except (ValueError,IndexError):pass
        if v is not None and re.fullmatch(r'r\d+|sp|fp|lr',dest):regs[dest]=v&0xffffffff
        elif re.fullmatch(r'r\d+|sp|fp|lr',dest) and op not in ('st','sth','stb','cmp','cmpi','cmpu','cmpui','push','beq','bne','beqz','bnez','bgez','blez','bltz','bgtz'):
            regs.pop(dest,None)
x['save']('evidence/pointer-store-candidates.json',dict(
    limit='Linear candidates. Constant pointer table models derive from initialization; branches, aliases and unknown callees are incomplete.',
    known_pointer_model={hex(k):hex(v) for k,v in known.items()},stores=stores,calls=calls))
print('Candidate stores',len(stores),'candidate memcpy/memset',len(calls))
for r in stores:
    pc=int(r['pc'],16)
    if r['band']=='EXIP' and not 0x2011825c<=pc<0x20118398:print(r)
for r in calls:
    if r['band']=='EXIP':print(r)
