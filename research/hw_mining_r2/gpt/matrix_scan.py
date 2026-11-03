#!/usr/bin/env python3
"""Bounded heuristic data search, not proof of matrix use or absence."""
import runpy
import argparse
import struct
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--wide',action='store_true');args=p.parse_args()
x=runpy.run_path(str(Path(__file__).with_name('audit.py')))
im=x['Image']()
raw=im.data[:len(im.data)//2*2]
u16=struct.unpack('>'+str(len(raw)//2)+'H',raw)
formats=[('s16_q'+str(q),q,[v-65536 if v&32768 else v for v in u16]) for q in (8,9,10,11,12,13,14)]
formats.append(('signmag12_q10',10,[-(v&2047) if v&2048 else v&2047 for v in u16]))
rows=[]
for name,q,values in formats:
    one=1<<q
    for i in range(len(values)-8):
        if not(one//2<=values[i]<=3*one and one//2<=values[i+4]<=3*one and one//2<=values[i+8]<=3*one):continue
        v=values[i:i+9]
        if min(v)>=0 or any(abs(k)>4*one for k in v):continue
        if name.startswith('signmag') and any(k>0xfff for k in u16[i:i+9]):continue
        sums=[sum(v[k:k+3]) for k in (0,3,6)]
        columns=[sum(v[c::3]) for c in range(3)]
        if args.wide:
            if any(k<one//2 or k>3*one//2 for k in sums):continue
            if sum(k<0 for k in v)<3:continue
            a=im.address(2*i)
            if a is None or not 0x2012b000<=a<0x20141534:continue
        elif any(abs(k-one)>2 for k in sums) and any(abs(k-one)>2 for k in columns):continue
        if any(abs(v[3*r+c])>v[4*r] for r in range(3) for c in range(3) if r!=c):continue
        off=2*i;a=im.address(off)
        rows.append(dict(format=name,file_offset=hex(off),vma=None if a is None else hex(a),
            coefficients=v,row_sums=sums,raw=raw[off:off+18].hex()))
x['save']('evidence/matrix-heuristic-'+('wide' if args.wide else 'strict')+'.json',dict(
    image_sha256=x['sha'](im.data),scope='all jlaunch3 bytes, big-endian halfword alignment',
    predicate=('3 negative terms, dominant positive diagonal, row sums 0.5..1.5 unity, ISP data area' if args.wide else
        'negative off-diagonal, positive dominant diagonal, each row OR column sum unity +/- 2, 9 consecutive halfwords'),
    limitations=['Does not find implicit diagonal, 32-bit, separated fields, generated or non-row-normalized matrices.',
        'Data-looking bytes in executable sections are not proof of execution or hardware consumption.'],candidates=rows))
print('heuristic candidates:',len(rows))
for r in rows[:35]:print(r['format'],r['vma'],r['coefficients'])
