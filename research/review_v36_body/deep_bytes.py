"""Compare actual RPC-visible bytes to independently unpacked shipped rows."""
import hashlib
import struct
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,save as original_save
exec(compile((HERE/"adversarial.py").read_text().split('selected=sys.argv')[0],str(HERE/"adversarial.py"),"exec"),globals())
def save(name,value):original_save("deep-bytes-"+name,value)
u16=lambda b,o:int.from_bytes(b[o:o+2],"big")
u32=lambda b,o:int.from_bytes(b[o:o+4],"big")
def unpack(dat,unit,slot):
    d=dat[u32(dat,156)+64*unit:u32(dat,156)+64*(unit+1)]
    table=u32(d,20);shared=u32(dat,192)
    desc=next(dat[table+16+20*i:table+36+20*i] for i in range(dat[table+5]) if dat[table+16+20*i]==slot)
    e=bytearray(552);e[:2]=desc[:2];e[4:8]=desc[4:8];e[445:447]=desc[2:4]
    for off,size,kind,index in zip((20,82,115,216,284,346,379,412,456,518),(62,33,96,56,62,33,33,33,62,33),(0,1,2,3,0,1,1,1,0,1),desc[8:18]):
        pool=shared+16+12*kind;assert u16(dat,pool+2)==size
        at=shared+u32(dat,pool+4)+size*index
        e[off:off+size]=dat[at:at+size]
    return bytes(e),dat[u32(d,12):u32(d,12)+152]
def check(p,slot):
    entry,mapping=unpack(p.dat,0,slot);stock,_=unpack(p.dat,0,4)
    rows=[]
    for i in range(9):
        r=mapping[32+12*i:44+12*i]
        address,n,off,bit=u32(r,0),u16(r,4),u16(r,6),r[10]
        source=stock if bit and not(entry[1]&bit) else entry
        expected=source[off:off+n]
        actual=bytearray()
        for a in range(address,address+n):
            word=p.rpc.half(a&~1)
            assert word is not None
            actual.append((word>>(8 if not(a&1) else 0))&255)
        mismatches=[j for j,(a,b) in enumerate(zip(actual,expected)) if a!=b]
        rows.append(dict(index=i,address=hex(address),bytes=n,entry_offset=off,mask_bit=bit,
            actual_sha256=hashlib.sha256(actual).hexdigest(),expected_sha256=hashlib.sha256(expected).hexdigest(),mismatches=mismatches))
    result=dict(slot=slot,mode=pe.settings_byte(p.h)[1],t=p.rpc.t,expected_t=u16(entry,445),rows=rows,
                overlay_sha256=snapshot(p.h,p)["deep_sha256"],all_bytes_equal=not any(x["mismatches"] for x in rows))
    assert result["all_bytes_equal"] and result["mode"]==1 and result["t"]==result["expected_t"],result
    return result
h,p,w=boot();rec=dict(name="real_01_02_04_bytes",steps=[]);reports.append(rec)
checks=[]
step(rec,"open",h,p,w,lambda:publish(h,p,w))
for slot in (1,2,4):
    if slot!=1:step(rec,"reopen",h,p,w,lambda:reopen(h,p,w))
    step(rec,f'scroll to {slot:02}',h,p,w,lambda slot=slot:moves_to(h,slot))
    step(rec,"OK",h,p,w,lambda:fr.press(h,0x23))
    checks.append(check(p,slot))
    step(rec,"MENU",h,p,w,lambda:fr.press(h,0x29))
original_save("deep-rows-comparison.json",checks)
print("PASS actual RPC bytes equal shipped effective 01, 02, 04: nine rows and T each",flush=True)
