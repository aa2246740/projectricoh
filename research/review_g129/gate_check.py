"""Exercise the final seventh section through the integrated open path."""
from pathlib import Path
import ctypes as ct
import hashlib
import json
import struct
import zlib

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent

def put32(data,offset,value):struct.pack_into('>I',data,offset,value)
def crc(data,offset):
    copy=bytearray(data);put32(copy,offset,0)
    return zlib.crc32(copy)&0xffffffff

def main():
    lib=ct.CDLL(str(WORK/'local/integrated-host/host/engine.dylib'))
    lib.g129_open.argtypes=[ct.c_void_p,ct.c_uint,ct.c_uint]
    lib.eng_validated_view.restype=ct.c_void_p
    lib.uv_validate.argtypes=[ct.c_void_p]
    raw=(ROOT/'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'
    seventh=struct.unpack_from('>I',raw,204)[0];assert len(raw)-seventh==20776
    extension=seventh+1408;block=extension+1984
    changes=[('section_length',208,'u32',20772),
             ('generation',28,'u32',127),
             ('legacy_magic',extension,'byte',0),
             ('legacy_reserved',extension+52,'byte',1),
             ('block_magic',block,'byte',0),
             ('block_reserved',block+56,'byte',1),
             ('recipe_control_count',block+66,'byte',8),
             ('recipe_display_repeat',block+71,'byte',1),
             ('item_reserved',block+448+10,'byte',1),
             ('item_point_offset',block+448+12,'u32',0xfffffff0),
             ('point_level',block+3664,'byte',1),
             ('block_crc',block+16,'byte',0)]
    results=[]
    def opened(data,unit):
        memory=(ct.c_uint8*len(data)).from_buffer_copy(data)
        result=lib.g129_open(memory,len(data),unit)
        if result==0 and not lib.uv_validate(lib.eng_validated_view()):return -3
        return result
    for unit in range(3):
        assert opened(raw,unit)==0
        for name,offset,kind,value in changes:
            data=bytearray(raw)
            if kind=='u32':put32(data,offset,value)
            else:data[offset]=value
            if name!='block_crc':put32(data,block+16,crc(data[block:],16))
            put32(data,extension+16,crc(data[extension:extension+1984],16))
            put32(data,24,zlib.crc32(data[256:])&0xffffffff)
            put32(data,20,crc(data[:256],20))
            result=opened(data,unit)
            results.append({'unit':unit,'case':name,'returncode':result,'rejected':result!=0})
            assert result!=0,('seventh_section_case',unit,name)
            assert opened(raw,unit)==0,('clean_reopen',unit,name)
    value={'status':'PASS','dat_sha256':hashlib.sha256(raw).hexdigest(),
           'negative_cases':len(results),'clean_reopens':len(results)+3,'cases':results,
           'scope':'Host gate, engine open, and the adapter validation predicate; no target scheduling claim.'}
    (WORK/'gate-results.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'name':'seventh_section_gate','returncode':0,'negative_cases':len(results)}))

if __name__=='__main__':main()
