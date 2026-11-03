#!/usr/bin/env python3
"""Print saved disassembly by VMA, or find bounded constant candidates.

Candidate pairing is not a control-flow or complete value-flow proof.
"""
from pathlib import Path
import argparse
import json
import re
import runpy
import struct

HERE=Path(__file__).resolve().parent
H=runpy.run_path(str(HERE/'inspect.py'))
FW=H['FW']

p=argparse.ArgumentParser()
p.add_argument('mode',choices=['code','xref','data'])
p.add_argument('name')
p.add_argument('start')
p.add_argument('end',nargs='?')
a=p.parse_args()
b=(FW/a.name).read_bytes()
start=int(a.start,0)
end=int(a.end,0) if a.end else start+0x100
if a.mode=='data':
    off=H['fileoff'](b,start)
    for i in range(0,end-start,16):
        chunk=b[off+i:off+min(i+16,end-start)]
        print(f'{start+i:08x} [file {off+i:08x}]: {chunk.hex(" "):<47} '+''.join(chr(v) if 32<=v<127 else '.' for v in chunk))
elif a.mode=='code':
    files=sorted((HERE/'disasm').glob(a.name+'-*.txt'))
    seen=set()
    for f in files:
        found=[]
        for l in f.read_text().splitlines():
            m=re.match(r'\[file [0-9a-f]+\]\s+([0-9a-f]+):',l)
            if m and start<=int(m[1],16)<end and int(m[1],16) not in seen:
                found.append(l);seen.add(int(m[1],16))
        if found:
            print('#',f.name);print('\n'.join(found))
else:
    hits=[]
    needle=struct.pack('>I',start)
    off=0
    while True:
        off=b.find(needle,off)
        if off<0:break
        hits.append(dict(kind='BE32 literal',file_offset=hex(off),vma=[hex(v) for v in H['maps'](b,off)]));off+=1
    seen=set()
    for f in sorted((HERE/'disasm').glob(a.name+'-*.txt')):
        window=[]
        for l in f.read_text().splitlines():
            m=re.match(r'\[file ([0-9a-f]+)\]\s+([0-9a-f]+):.*\t([^\t]+)$',l)
            if not m:continue
            va=int(m[2],16)
            # Only seth + or3/add3 candidates; intervening clobbers and branches
            # must be read by an analyst. No negative result excludes aliases.
            for ins in re.split(r' -> | \|\| ',m[3]):
                lo=re.fullmatch(r'(or3|add3) (r\d+|fp|sp|lr),(r\d+|fp|sp|lr),#(-?0x[0-9a-f]+|-?\d+)',ins)
                if lo:
                    for hi in reversed(window[-16:]):
                        if hi[0]==lo[3]:
                            v=(hi[1] | int(lo[4],0)) if lo[1]=='or3' else (hi[1]+int(lo[4],0))&0xffffffff
                            if v==start and (va,hi[2]) not in seen:
                                hits.append(dict(kind='seth-pair candidate',vma=hex(va),file_offset='0x'+m[1],high_vma=hex(hi[2]),line=l.strip()))
                                seen.add((va,hi[2]))
                            break
                hi=re.fullmatch(r'seth (r\d+|fp|sp|lr),#0x([0-9a-f]+)',ins)
                if hi:window.append((hi[1],int(hi[2],16)<<16,va))
            window=[x for x in window if va-x[2]<=96]
    print(json.dumps(dict(image=a.name,target=hex(start),coverage='BE32 literals and seth-pair candidates within 96 bytes; not complete cross-references',hits=hits),indent=2))
