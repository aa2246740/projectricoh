"""Independent byte readers used by g152 fit and acceptance tools."""
import struct
import zlib
import hashlib

KINDS=(0,1,2,3,0,1,1,1,0,1)
LENGTHS=(62,33,96,56)
OFFSETS=(20,82,115,216,284,346,379,412,456,518)
CRC_FIELDS=((20,62,8),(82,33,12),(115,96,16),(216,56,212),(284,62,272),
            (346,33,276),(379,66,280),(456,62,448),(518,33,452))
u16=lambda b,o:struct.unpack_from('>H',b,o)[0]
u32=lambda b,o:struct.unpack_from('>I',b,o)[0]
align4=lambda n:(n+3)&~3
crc=lambda b:zlib.crc32(b)&0xffffffff
sha=lambda b:hashlib.sha256(b).hexdigest()

def seal(raw):
    out=bytearray(raw)
    struct.pack_into('>I',out,24,crc(out[256:]));out[20:24]=bytes(4)
    struct.pack_into('>I',out,20,crc(out[:256]))
    return bytes(out)

def sections(raw):
    assert raw[:8]==b'GXRCE001' and u32(raw,16)==len(raw)
    assert u32(raw,20)==crc(raw[:20]+bytes(4)+raw[24:256]) and u32(raw,24)==crc(raw[256:])
    out=[];next_offset=256
    for i in range(7):
        kind,flags,at,n=struct.unpack_from('>HHII',raw,128+12*i)
        assert kind==i+1 and not flags and at==next_offset and not at%4 and not n%4 and n<=len(raw)-at
        out.append((at,n));next_offset+=n
    assert next_offset==len(raw)
    return out

def descriptor(raw,unit,slot):
    d=u32(raw,156)+unit*64;t=u32(raw,d+20)
    return next(raw[t+16+20*i:t+36+20*i] for i in range(raw[d+30]) if raw[t+16+20*i]==slot)

def effect_area(raw):
    p=u32(raw,192)
    return p+u32(raw,p+64),u32(raw,p+68)

def raw_rows(raw,entry,effects=False):
    p=u32(raw,192);out=[]
    if effects:a,_=effect_area(raw)
    for kind,index in zip(KINDS,entry[8:18]):
        size=LENGTHS[kind]
        if effects and index&128:
            assert index&127<raw[a+20+kind]
            at=a+32+32*u16(raw,a+8)+sum(align4(raw[a+16+k]*LENGTHS[k]) for k in range(kind))
            at+=(index&127)*size
        else:
            assert index<u16(raw,p+16+12*kind)
            at=p+u32(raw,p+20+12*kind)+index*size
        assert at+size<=len(raw)
        out.append(raw[at:at+size])
    return out

def encode_entry(entry,rows):
    out=bytearray(552);out[:2]=entry[:2];out[4:8]=entry[4:8];out[445:447]=entry[2:4]
    for at,row in zip(OFFSETS,rows):out[at:at+len(row)]=row
    for at,n,field in CRC_FIELDS:struct.pack_into('>I',out,field,crc(out[at:at+n]))
    return bytes(out)

def expand(raw,unit,slot):
    e=descriptor(raw,unit,slot)
    return encode_entry(e,raw_rows(raw,e))

def expand_effect(raw,index):
    a,_=effect_area(raw);assert index<u16(raw,a+10)
    e=raw[a+32+32*index:a+64+32*index]
    return encode_entry(e,raw_rows(raw,e,True))

def refresh_entry(raw):
    out=bytearray(raw)
    for at,n,field in CRC_FIELDS:struct.pack_into('>I',out,field,crc(out[at:at+n]))
    return bytes(out)

def content_crc(entry,mask):
    return crc(entry[:2]+entry[445:447]+bytes([mask])+b''.join(entry[o:o+LENGTHS[k]] for k,o in zip(KINDS,OFFSETS)))

def strict_effects(raw):
    sections(raw);p=u32(raw,192);a,n=effect_area(raw)
    assert raw[p:p+4]==b'GXDP' and (u16(raw,p+4),u16(raw,p+6))==(2,80)
    assert a%4==0 and a>=p+80 and a+n==p+u32(raw,196) and n>=32 and not any(raw[p+72:p+80])
    assert raw[a:a+4]==b'GXFX' and (u16(raw,a+4),u16(raw,a+6),u16(raw,a+12),u16(raw,a+14))==(1,32,32,0)
    cap,count=u16(raw,a+8),u16(raw,a+10);caps=raw[a+16:a+20];used=raw[a+20:a+24]
    assert count<=cap<=48 and all(v<=c<=127 for v,c in zip(used,caps))
    assert n==32+32*cap+sum(align4(c*l) for c,l in zip(caps,LENGTHS))
    assert u32(raw,a+28)==crc(raw[a:a+28]) and u32(raw,a+24)==crc(raw[a+32:a+n])
    assert not any(raw[a+32+count*32:a+32+cap*32])
    seen=[set() for _ in LENGTHS];names=[]
    allowed=set(range(32,127))-{42,92}
    for i in range(count):
        e=raw[a+32+32*i:a+64+32*i];name=e[20:].split(b'\0')[0]
        assert e[0] in (1,2,3,5,6,7,8) and 1<=e[18]<=7 and not e[19]
        assert name and all(x in allowed for x in name) and e[20:]==name+bytes(12-len(name))
        assert u16(e,2)==(0 if e[1]&4 else 2)
        for unit in range(3):
            if e[18]>>unit&1:assert e[1]==descriptor(raw,unit,e[0])[1]
        rows=raw_rows(raw,e,True)
        assert u32(e,4)==content_crc(encode_entry(e,rows),e[18])
        for row,(kind,index) in enumerate(zip(KINDS,e[8:18])):
            if index&128:seen[kind].add(index&127)
            b=rows[row]
            if kind==0:
                values=struct.unpack('>31H',b);assert 0<values[0] and all(x<y for x,y in zip(values,values[1:]))
                assert values[-1]<=(4094 if row in (0,8) else 4095)
            elif kind==1:assert all(x<=y for x,y in zip(b,b[1:]))
            elif kind==3:
                for half in range(2):
                    for j,v in enumerate(struct.unpack('>14H',b[28*half:28*half+28])):
                        assert v<=4095
                        if j<9:assert v&2047<=(2047 if j<3 else 1279)
                        elif j in (10,11):assert 120<=v<=136
                        else:assert v==0
            if row in (6,7) and e[1]&2:assert b[32]>=128
        names.append(name.decode())
    at=a+32+32*cap
    for kind,(c,v,l) in enumerate(zip(caps,used,LENGTHS)):
        rows=[raw[at+j*l:at+(j+1)*l] for j in range(v)]
        assert seen[kind]==set(range(v)) and len(set(rows))==v
        assert not any(raw[at+v*l:at+align4(c*l)])
        at+=align4(c*l)
    return dict(capacity=cap,count=count,capacities=list(caps),used=list(used),names=names,bytes=n)
