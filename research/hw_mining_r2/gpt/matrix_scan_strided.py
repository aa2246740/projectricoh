#!/usr/bin/env python3
"""Search two common row layouts and small signed encodings. Static heuristic only."""
import runpy
import struct
import argparse
import json
from pathlib import Path

x=runpy.run_path(str(Path(__file__).with_name('audit.py')));im=x['Image']()
p=argparse.ArgumentParser();p.add_argument('--params',action='store_true');args=p.parse_args()
raw=im.data[:len(im.data)//2*2];known=None
if args.params:
    d=json.loads((x['OUT']/'evidence/jlaunch8-parameter-decode.json').read_text())
    sparse={int(k):v for k,v in d['bytes'].items()}
    raw=bytes(sparse.get(i,0) for i in range(65536))
    known=[2*i in sparse and 2*i+1 in sparse for i in range(32768)]
u=struct.unpack('>'+str(len(raw)//2)+'H',raw)
rows=[]
for bits,encoding in [(11,'twos'),(12,'twos'),(13,'twos'),(16,'twos'),(12,'signmag'),(16,'signmag')]:
    sign=1<<(bits-1);mask=(1<<bits)-1
    if encoding=='twos':v=[(z&mask)-(1<<bits) if z&sign else z&mask for z in u]
    else:v=[-(z&(sign-1)) if z&sign else z&(sign-1) for z in u]
    for stride in (3,4):
        indexes=(0,1,2,stride,stride+1,stride+2,2*stride,2*stride+1,2*stride+2)
        for i in range(len(v)-2*stride-2):
            if known is not None and not all(known[i+k] for k in indexes):continue
            if v[i]<=0 or v[i+stride+1]<=0 or v[i+2*stride+2]<=0:continue
            m=[v[i+k] for k in indexes]
            if min(m)>=0:continue
            if bits<16 and any(u[i+k]>mask for k in indexes):continue
            if any(abs(m[3*r+c])>m[4*r] for r in range(3) for c in range(3) if r!=c):continue
            sums=[sum(m[k:k+3]) for k in (0,3,6)]
            cols=[sum(m[c::3]) for c in range(3)]
            qs=[q for q in range(6,15) if all(abs(z-(1<<q))<=2 for z in sums) or all(abs(z-(1<<q))<=2 for z in cols)]
            if not qs:continue
            off=2*i;va=None if args.params else im.address(off)
            rows.append(dict(format=f'{encoding}{bits}',q=qs,row_stride_halfwords=stride,
                offset_kind='T offset' if args.params else 'file offset',offset=hex(off),vma=None if va is None else hex(va),coefficients=m,
                row_sums=sums,column_sums=cols,raw=raw[off:off+2*(indexes[-1]+1)].hex()))
x['save']('evidence/matrix-heuristic-'+('params' if args.params else 'strided')+'.json',dict(
    input_sha256=d['sha256'] if args.params else x['sha'](im.data),
    scope=('Known sparse shipped parameter-script halfwords only' if args.params else 'All initialized jlaunch3 bytes')+
        '; halfword aligned; 3 or 4 halfwords per row; Q6..Q14',
    predicate='Positive dominant diagonal, at least one negative, row OR column sums unity +/-2',
    limitations='Does not prove execution, hardware consumption, or absence of generated/non-normalized/implicit matrices.',candidates=rows))
print('Strided signed-matrix heuristic candidates',len(rows))
for r in rows[:30]:print(r)
