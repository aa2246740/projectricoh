#!/usr/bin/env python3
"""Offline M32R excerpts and bounded candidate searches; writes only beside this file."""
import argparse
import csv
import hashlib
import json
import re
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FW = ROOT / 'artifacts/firmware/gxr-1.51'
DIS = ROOT / 'research/tooling_m32r/disasm'

def sections(data):
    return [(s+512,v,n) for s,v,n,_,_ in
            (struct.unpack_from('>IIIII',data,32+20*i) for i in range(16))]

def offset(va, secs):
    for s,v,n in secs:
        if v <= va < v+n:
            return s+va-v
    raise ValueError(hex(va))

def instructions():
    for p in sorted(DIS.glob('jlaunch3-sec*.disasm.txt')):
        for no,line in enumerate(p.read_text().splitlines(),1):
            m = re.fullmatch(r'\s*([0-9a-f]+):\t([0-9a-f ]+)\t(.*)', line)
            if m:
                yield int(m[1],16), bytes.fromhex(m[2]), m[3], p.name, no, line

def dump(start,end,label):
    data=(FW/'jlaunch3').read_bytes(); secs=sections(data)
    out=[f'# jlaunch3 VMA {start:#x}..{end:#x}; file {offset(start,secs):#x}..{offset(end-1,secs)+1:#x}',
         '# Each original line and all emitted machine bytes are checked against the firmware.']
    count=0
    for va,b,ins,p,no,line in instructions():
        if start <= va < end:
            off=offset(va,secs)
            assert data[off:off+len(b)]==b,(hex(va),p,no)
            out.append(f'{p}:{no} | {line}'); count+=1
    (HERE/(label+'.disasm.txt')).write_text('\n'.join(out)+'\n')
    print(label,count)

def refs(target):
    with (ROOT/'research/hidden_processing/jlaunch3-refs.tsv').open() as f:
        for row in csv.DictReader(f,delimiter='\t'):
            if int(row['target'],0)==target:
                print(json.dumps(row))

def census():
    hits=[]
    for va,b,ins,p,no,line in instructions():
        nums=[int(x,0) for x in re.findall(r'#(0x[0-9a-f]+|-?\d+)|(?!)',ins) if x]
        nums += [int(x) for x in re.findall(r'@\((-?\d+),',ins)]
        if any(x in [0x2f52,0x2f53,0x2f54,0x2fb2,0x2fb7,0x10d,0x10e,0x10f,0x110,0x115] for x in nums):
            hits.append([hex(va),ins,p,no])
    with (HERE/'immediate-candidates.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['vma','instruction','original_file','original_line']);w.writerows(hits)
    inv={n:{'size':(FW/n).stat().st_size,'sha256':hashlib.sha256((FW/n).read_bytes()).hexdigest()} for n in ['jlaunch3','jlaunch4']}
    (HERE/'inventory.json').write_text(json.dumps(inv,indent=2)+'\n')
    print('immediate candidates',len(hits))

def affine_candidates():
    """Linear offset aliases, for manual review only; never a reachability proof.

    Symbol roots are arbitrary incoming values or loaded pointers. Calls retain
    only callee-saved registers. Jumps invalidate all symbolic state, so merges,
    indirect pointers, bulk copies, and unknown callees remain coverage gaps.
    """
    regs={}; hits=[]; previous=None
    wanted=set([0x2f52,0x2f53,0x2f54,*range(0x2fb2,0x2fbc)])
    for va,b,ins,p,no,line in instructions():
        if p!=previous:
            regs={};previous=p
        for op in re.split(r'\s*(?:\|\||->)\s*',ins):
            def value(r):
                if r not in regs:regs[r]=(f'incoming:{p}:{va:#x}:{r}',0)
                return regs[r]
            m=re.fullmatch(r'mv (\w+),(\w+)',op)
            if m:regs[m[1]]=value(m[2]);continue
            m=re.fullmatch(r'add3 (\w+),(\w+),#(-?\d+)',op)
            if m:
                s=value(m[2]);regs[m[1]]=None if s is None else (s[0],s[1]+int(m[3]));continue
            m=re.fullmatch(r'addi (\w+),#(-?\d+)',op)
            if m:
                s=value(m[1]);regs[m[1]]=None if s is None else (s[0],s[1]+int(m[2]));continue
            m=re.fullmatch(r'(ld\w*|st\w*) (\w+),@(?:\((-?\d+),(\w+)\)|(\w+))',op)
            if m:
                s=value(m[4] or m[5]);delta=int(m[3] or 0)
                if s is not None and s[1]+delta in wanted:
                    hits.append([hex(va),op,s[0],hex(s[1]+delta),p,no])
                if m[1].startswith('ld'):regs[m[2]]=(f'loaded:{va:#x}:{op}',0)
                continue
            if op.startswith(('jl ','bl ')):
                for r in range(8):regs[f'r{r}']=None
                continue
            if op.startswith(('jmp ','bra ')):regs={};continue
            m=re.match(r'(\w+) (r\d+|sp|lr|fp)(?:,|$)',op)
            if m and m[1] not in ['cmp','cmpu','cmpi','cmpui','beq','bne','bnez','beqz','bgez','bltz','push','st','stb','sth']:
                regs[m[2]]=None
    with (HERE/'affine-access-candidates.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['vma','instruction','unproven_base_root','effective_offset','original_file','original_line']);w.writerows(hits)
    print('affine access candidates',len(hits))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dump',nargs=3);ap.add_argument('--refs');ap.add_argument('--census',action='store_true')
    ap.add_argument('--affine',action='store_true')
    a=ap.parse_args()
    if a.dump: dump(int(a.dump[0],0),int(a.dump[1],0),a.dump[2])
    if a.refs: refs(int(a.refs,0))
    if a.census: census()
    if a.affine: affine_candidates()

if __name__=='__main__':main()
