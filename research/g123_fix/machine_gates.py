"""Exercise file capabilities in the final relocated DAT dispatcher."""
from pathlib import Path
import json
import struct
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import ROOT, OUT, save, load, sha
import run_native as review

review.configure('50mm','machine-gates')
ux,m,fr,pe,v=review.ux,review.m,review.fr,review.pe,review.v
h,p,w=m.boot('50mm');m.published(h,p,w)
R=pe.ROOT_ADDR;s=h.u(R+56);image=p.image_base
assert h.u(s+340)==0xe7fff
rows=[]

def storage(op,args):
    q,reply=pe.SCRATCH+0x300,pe.SCRATCH+0x380
    h.b.write(q,struct.pack('>HHI14I',1,64,0,*args));h.b.write(reply,bytes(32))
    # Direct service-boundary fixture: rv_engine would set this ownership flag.
    # This flag is not used to create or move any native menu state.
    h.put(R+6,1,1)
    try: result=p.call(p.symbol_pc('rv_call'),(1,op,q,reply),steps=2000000)
    finally:h.put(R+6,0,1)
    assert result['ok'],result
    parsed=struct.unpack('>HHi i IIIII',h.b.read(reply,32));assert result['signed']==parsed[2]
    row=dict(operation=op,status=result['signed'],token=parsed[5],capabilities=parsed[7]);rows.append(row)
    save('storage-case-history.json',rows)
    return row

epoch=h.u(R+52)
assert storage(1,[0]*14)['capabilities']==3
for op in (3,7,8,9):
    a=[0]*14;a[0]=epoch;a[2]=1 if op==9 else 2;a[3]=1;a[5]=1 if op==9 else 4
    if op==3:a[8]=240
    if op==7:a[9]=2
    if op==9:a[3]=0;a[9]=5;a[10]=2
    assert storage(op,a)['status']==-12
a=[0]*14;a[0]=epoch;a[2]=1;a[5]=1
fd=storage(2,a);assert fd['status']==0 and fd['token']
assert h.u(s+292)==0
a=[0]*14;a[0]=epoch;a[1]=fd['token'];a[6]=image;a[7]=16
assert storage(5,a)['status']==-10
a[6]=a[7]=0;assert storage(6,a)['status']==0
reinit=p.engine(0,[]);assert reinit['ok'] and reinit['reply_status']==0
assert h.u(s+340)==0xe7fff
save('machine-gates.json',dict(status='PASS',artifacts=dict(dat=sha(p.dat),elf=sha(p.elf.raw),body=h.image.sha256),capabilities=hex(h.u(s+340)),cases=rows,
     reinit=reinit,zero_file_mutations=m.no_writes(p),native_log=p.native_log,
     fixture='Direct final dispatcher; test supplies service inflight ownership only; no native UI seeding'))
print('PASS final M32R: CAP query=3; create/rename/delete/mark=-12; readonly write=-10; close=0; caps=0xE7FFF',flush=True)
