"""Read-only native image and gen115 row decoding."""
import struct
import zlib
import boundary as b

ENGINE = b.ROOT / 'firmware/engine_v36_r28'
CARD = b.ROOT / 'artifacts/card-b-mount/card-b-after-gen115-test-20261026T084138Z'
OLD_CARD = b.ROOT / 'artifacts/card-b-mount/card-b-after-v34c-first-run-20261026T032356Z'
ROW_SIZES = (62,33,96,56)
KINDS = (0,1,2,3,0,1,1,1,0,1)
OFFSETS = (20,82,115,216,284,346,379,412,456,518)
SPECS = (('A5',62,20,8,0,0),('B5',33,82,12,0,2),('colour',96,115,16,0,0),
         ('matrix',56,216,212,1,0),('A20',62,284,272,16,0),('B20',33,346,276,16,1),
         ('CD',66,379,280,2,0),('A14',62,456,448,0,0),('B14',33,518,452,0,1))

def u16(p,o): return struct.unpack_from('>H',p,o)[0]
def u32(p,o): return struct.unpack_from('>I',p,o)[0]
def crc(p): return zlib.crc32(p)&0xffffffff
def read(path): return b.add(path).read_bytes()

def native_span(image,va,n):
    found=[]
    for i in range(16):
        source,base,length,_,_=struct.unpack_from('>5I',image,32+20*i)
        if base<=va and va+n<=base+length:
            off=512+source+va-base
            found.append((image[off:off+n],off,i))
    assert len(found)==1,hex(va)
    return found[0]

def parse():
    path=ENGINE/'local/staged/SD_ROOT/GXRCE.DAT';raw=read(path)
    assert b.sha(path)=='a9743bb9f0ace0ebba1d807af124210a2a098ad64f31c27083412923c841c4b8'
    assert read(CARD/'root/GXRCE.OK')==raw
    assert len(raw)==65252 and u32(raw,28)==115
    header=bytearray(raw[:256]);header[20:24]=bytes(4)
    assert crc(header)==u32(raw,20) and crc(raw[256:])==u32(raw,24)
    sections=[(u32(raw,132+12*i),u32(raw,136+12*i)) for i in range(7)]
    shared=sections[5][0];pools=[]
    for k,size in enumerate(ROW_SIZES):
        n,stride,off,digest=struct.unpack_from('>HHII',raw,shared+16+12*k)
        assert stride==size
        chunk=raw[shared+off:shared+off+n*size];assert crc(chunk)==digest
        pools.append([chunk[i*size:(i+1)*size] for i in range(n)])
    modules=[]
    for mi in range(3):
        di=sections[2][0]+64*mi;name=raw[di:di+8].rstrip(b'\0').decode()
        mo,ba,tb,me=[u32(raw,di+12+4*i) for i in range(4)]
        mapping=raw[mo:mo+152];entries={};records={};descriptors=[]
        n=raw[di+30]
        for j in range(n):
            de=raw[tb+16+20*j:tb+36+20*j];slot=de[0]
            rows=[pools[k][ref] for k,ref in zip(KINDS,de[8:18])]
            e=bytearray(552);e[:2]=de[:2];e[4:8]=de[4:8];e[445:447]=de[2:4]
            for off,row in zip(OFFSETS,rows):e[off:off+len(row)]=row
            for _,size,off,co,_,_ in SPECS:struct.pack_into('>I',e,co,crc(e[off:off+size]))
            entries[slot]=dict(descriptor=de,rows=rows,entry=bytes(e),offset=tb+16+20*j)
            descriptors.append(slot)
        for slot in range(1,17):records[slot]=raw[ba+32+64*(slot-1):ba+96+64*(slot-1)]
        stock=entries[4];pin=crc(mapping+b''.join(stock['rows'])+stock['descriptor'][2:4])
        assert pin==u32(raw,di+32)
        visible=0
        for slot in range(1,17):
            index=raw[me+28*(slot-1)+24];owner=raw[tb+16+20*index]
            if slot!=4 and owner!=4:visible=slot
        modules.append(dict(name=name,map=mapping,entries=entries,records=records,pin=pin,
            directory_offset=di,map_offset=mo,bank_offset=ba,table_offset=tb,meta_offset=me,
            owners=descriptors,visible_rows=visible))
    return raw,modules
