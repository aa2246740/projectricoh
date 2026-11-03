#!/usr/bin/env python3
"""Search initialized jlaunch3 data for conventional nine-word CCM shapes."""
import runpy
import struct
from pathlib import Path

x=runpy.run_path(str(Path(__file__).with_name('audit.py')))
im=x['Image']();data=im.data[:len(im.data)//4*4]
words=struct.unpack('>'+str(len(data)//4)+'I',data)
rows=[]
for q in (7,8,9,10,11,12,13,14,16):
    one=1<<q
    for i in range(len(words)-8):
        if not(one//2<=words[i]<=3*one and one//2<=words[i+4]<=3*one and one//2<=words[i+8]<=3*one):continue
        v=[w-0x100000000 if w&0x80000000 else w for w in words[i:i+9]]
        if min(v)>=0 or any(abs(k)>4*one for k in v):continue
        sums=[sum(v[k:k+3]) for k in (0,3,6)]
        cols=[sum(v[k::3]) for k in range(3)]
        if any(abs(k-one)>2 for k in sums) and any(abs(k-one)>2 for k in cols):continue
        off=4*i;a=im.address(off)
        rows.append(dict(q=q,vma=None if a is None else hex(a),file_offset=hex(off),values=v))
x['save']('evidence/matrix-heuristic-s32.json',dict(image_sha256=x['sha'](im.data),
    scope='all jlaunch3 initialized file bytes, four-byte alignment, nine signed big-endian words',
    predicate='positive diagonal 0.5..3 unity, some negative terms, row OR column sums unity +/- 2',
    limits='Not an exclusion of implicit diagonals, packed fields, runtime generation, other normalizations or hardware capabilities',
    candidates=rows))
print('32-bit candidates',len(rows))
for r in rows[:30]:print(r)
