"""Generate fixed-capacity effects and R3 knobs from frozen local inputs."""
from pathlib import Path
import json
import struct
import zlib

ROOT=Path(__file__).resolve().parents[5]
WORK=ROOT/'research/looks_g152'
KINDS=(0,1,2,3,0,1,1,1,0,1)
LENGTHS=(62,33,96,56)
OFFSETS=(20,82,115,216,284,346,379,412,456,518)
CAPACITY=10
CAPS=(0,16,12,12)
align4=lambda n:(n+3)&~3
u16=lambda b,o:struct.unpack_from('>H',b,o)[0]
u32=lambda b,o:struct.unpack_from('>I',b,o)[0]

def compact_knobs():
    raw=(ROOT/'firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT').read_bytes()
    at=u32(raw,204)+3392
    old=raw[at:at+17384]
    assert old[:8]==b'GXKV2R2\0'
    out=bytearray(old[:3664]);runs={}
    for i in range(201):
        item=448+16*i;count=old[item+1];offset=u32(old,item+12)
        values=[]
        for j in range(count):
            level,dose=struct.unpack_from('>hh',old,offset+4*j)
            expected=min(j*old[item+9],150) if old[item]==0 else struct.unpack_from('>h',old,item+2)[0]+j
            assert level==expected
            values.append(dose)
        key=struct.pack('>'+'h'*count,*values)
        if key not in runs:runs[key]=len(out);out+=key
        struct.pack_into('>I',out,item+12,runs[key])
    assert len(runs)==117 and len(out)==7902
    out+=bytes(align4(len(out))-len(out));out[:8]=b'GXKV2R3\0'
    struct.pack_into('>I',out,12,len(out));struct.pack_into('>H',out,26,2119)
    struct.pack_into('>H',out,32,2);out[16:20]=bytes(4)
    struct.pack_into('>I',out,16,zlib.crc32(out))
    return bytes(out)

def effect_area(buckets):
    path=WORK/'local/effects.json'
    effects=json.loads(path.read_text()) if path.exists() else []
    assert len(effects)<=CAPACITY
    pools=[[] for _ in LENGTHS];entries=[]
    for effect in effects:
        name=effect['name'].encode('ascii')
        assert 1<=len(name)<=12 and all(chr(x).isalnum() or chr(x) in ' -+._()/&' for x in name)
        e=bytes.fromhex(effect['entry_hex']);assert len(e)==552
        refs=[]
        for kind,off in zip(KINDS,OFFSETS):
            row=e[off:off+LENGTHS[kind]]
            if row in buckets[kind]:index=buckets[kind].index(row)
            else:
                if row not in pools[kind]:pools[kind].append(row)
                index=128+pools[kind].index(row)
            assert index<256
            refs.append(index)
        # Identity binds base, flags, T, all ten encoded rows, and unit mask.
        identity=e[:2]+e[445:447]+bytes([effect['mask']])+b''.join(e[o:o+LENGTHS[k]] for k,o in zip(KINDS,OFFSETS))
        content=zlib.crc32(identity)
        entries.append(struct.pack('>BBHI10BBB12s',effect['base'],e[1],u16(e,445),content,*refs,effect['mask'],0,name))
    out=bytearray(32);out+=b''.join(entries)+bytes((CAPACITY-len(entries))*32)
    for kind,length in enumerate(LENGTHS):
        assert len(pools[kind])<=CAPS[kind]
        raw=b''.join(pools[kind]);out+=raw+bytes(align4(CAPS[kind]*length)-len(raw))
    assert len(out)==32+32*CAPACITY+sum(align4(n*s) for n,s in zip(CAPS,LENGTHS))
    struct.pack_into('>4s6H',out,0,b'GXFX',1,32,CAPACITY,len(entries),32,0)
    out[16:20]=bytes(CAPS);out[20:24]=bytes(map(len,pools))
    struct.pack_into('>I',out,24,zlib.crc32(out[32:]));struct.pack_into('>I',out,28,zlib.crc32(out[:28]))
    return bytes(out)
