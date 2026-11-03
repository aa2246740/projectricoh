#!/usr/bin/env python3
"""Candidate-only straight-line constant/call index for fresh M32R disassembly."""
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mine',HERE/'mine.py')
mine=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mine)

LINE=re.compile(r'^([0-9a-f]{8}):\s+((?:[0-9a-f]{2} ){1,4})\s*(.*)$')
REG=r'(r\d+|fp|lr|sp)'
NUM=r'(-?0x[0-9a-f]+|-?\d+)'

def index(name):
    im=mine.Image(name)
    refs=[]; calls=[]; instructions=0
    for p in sorted(mine.EVIDENCE.glob(name+'-segment*.asm')):
        regs={}
        for no,line in enumerate(p.read_text().splitlines(),1):
            m=LINE.match(line)
            if not m: continue
            va=int(m[1],16)
            raw=bytes.fromhex(m[2])
            assert im.read(va,len(raw))==raw
            instructions+=1
            for op in re.split(r'\s*(?:\|\||->)\s*',m[3]):
                op=op.strip()
                dest=None; value=None
                q=re.fullmatch(r'(ldi|ld24|seth) '+REG+',#?'+NUM,op)
                if q:
                    dest=q[2]; value=int(q[3],0)
                    if q[1]=='seth': value<<=16
                else:
                    q=re.fullmatch(r'(or3|add3|and3) '+REG+','+REG+',#'+NUM,op)
                    if q:
                        dest=q[2]; v=regs.get(q[3]); k=int(q[4],0)
                        if v is not None: value={'or3':lambda:v|k,'add3':lambda:v+k,'and3':lambda:v&k}[q[1]]()
                    else:
                        q=re.fullmatch(r'mv '+REG+','+REG,op)
                        if q: dest=q[1]; value=regs.get(q[2])
                        else:
                            q=re.fullmatch(r'(addi|slli|srli|srai) '+REG+',#'+NUM,op)
                            if q:
                                dest=q[2]; v=regs.get(dest); k=int(q[3],0)
                                if v is not None:
                                    value={'addi':lambda:v+k,'slli':lambda:v<<(k&31),'srli':lambda:v>>(k&31),
                                           'srai':lambda:((v^0x80000000)-0x80000000)>>(k&31)}[q[1]]()
                if dest:
                    regs.pop(dest,None)
                    if value is not None:
                        value&=0xffffffff
                        regs[dest]=value
                        if value>=0x05000000:
                            refs.append(dict(vma=va,file_offset=im.offset(va),value=value,register=dest,
                                             operation=op,source=p.name,line=no))
                    continue
                q=re.fullmatch(r'(neg|not) '+REG+','+REG,op)
                binary=re.fullmatch(r'(add|sub|or|and) '+REG+','+REG,op)
                if q or binary:
                    q=q or binary
                    dest=q[2]; right=regs.get(q[3]); left=regs.get(dest)
                    regs.pop(dest,None)
                    if right is not None and (q[1] in ('neg','not') or left is not None):
                        value={'neg':lambda:-right,'not':lambda:~right,'add':lambda:left+right,
                               'sub':lambda:left-right,'or':lambda:left|right,'and':lambda:left&right}[q[1]]()&0xffffffff
                        regs[dest]=value
                        if value>=0x05000000:
                            refs.append(dict(vma=va,file_offset=im.offset(va),value=value,register=dest,
                                             operation=op,source=p.name,line=no))
                    continue
                q=re.fullmatch(r'jl '+REG,op)
                direct=re.fullmatch(r'bl (0x[0-9a-f]+)',op)
                if q or direct:
                    target=regs.get(q[1]) if q else int(direct[1],16)
                    if target is not None:
                        calls.append(dict(vma=va,file_offset=im.offset(va),target=target,
                                          args={r:regs[r] for r in ('r4','r5','r6','r7') if r in regs},
                                          source=p.name,line=no))
                    for r in [f'r{i}' for i in range(8)]: regs.pop(r,None)
                    continue
                q=re.match(r'(?:ld\w*|pop|neg|mul\w*|xor\w*|not|add|sub|or|and) '+REG,op)
                if q: regs.pop(q[1],None)
                if op.startswith(('jmp ','bra ','rte')): regs.clear()
    result=dict(note='Candidate index only; no CFG merge, code/data separation or indirect-memory resolution. Re-read windows.',
                image=name,instructions_byte_checked=instructions,refs=refs,calls=calls)
    mine.save(mine.LOCAL/(name+'-index.json'),result)
    print(name,'instructions',instructions,'refs',len(refs),'calls',len(calls))

def query(name,kind,value):
    data=json.loads((mine.LOCAL/(name+'-index.json')).read_text())
    value=int(value,0)
    key='target' if kind=='calls' else 'value'
    for row in data[kind]:
        if row[key]==value:
            print(json.dumps({k:hex(v) if isinstance(v,int) and k!='line' else v for k,v in row.items()}))

if __name__=='__main__':
    if sys.argv[1]=='index': index(sys.argv[2])
    else: query(*sys.argv[1:])
