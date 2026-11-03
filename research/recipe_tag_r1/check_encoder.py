"""Compare the standalone host C serializer with the independent Python codec."""
import ctypes as ct
import json
from pathlib import Path
import random
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import metadata as m
c=m.c


class Record(ct.Structure):
    _fields_=[('catalog',ct.c_uint8*32),('entry_crc',ct.c_uint32),('levels',ct.c_int16*10),
              ('ref',ct.c_uint8),('unit',ct.c_uint8),('name_bytes',ct.c_uint8),('verified',ct.c_uint8),
              ('name',ct.POINTER(ct.c_uint8))]


def main():
    path=c.TMP/'libtag_encoder.dylib';lib=ct.CDLL(str(path))
    lib.recipe_tag_encode.argtypes=[ct.POINTER(ct.c_uint8),ct.POINTER(Record)]
    lib.recipe_tag_encode.restype=ct.c_int
    rng=random.Random(155)
    for case in range(104):
        name=('配方'*13 if case==0 else '配'*13 if case==2 else '' if case==3 else 'GR Bleach').encode('utf-8')
        levels=([-32768,32767]*5 if case==1 else [rng.randrange(-7,8) for _ in range(10)])
        catalog=bytes(rng.randrange(256) for _ in range(32));crc=rng.randrange(2**32)
        ref=[1,8,0x40,0x49,0x80,0x9f][case%6];unit=case%3;quality='V' if case%2 else 'U'
        name_buffer=(ct.c_uint8*len(name)).from_buffer_copy(name)
        record=Record((ct.c_uint8*32).from_buffer_copy(catalog),crc,(ct.c_int16*10)(*levels),
                      ref,unit,len(name),quality=='V',name_buffer)
        out=(ct.c_uint8*264)()
        if case==0:
            # Thirteen two-character names exceed the explicit 39-byte limit.
            assert lib.recipe_tag_encode(out,ct.byref(record))==-1
            continue
        assert lib.recipe_tag_encode(out,ct.byref(record))==264
        expected=m.tag_bytes(ref,name.decode('utf-8'),unit,levels,catalog.hex(),crc,quality)
        assert bytes(out)==expected
        assert m.parse_tag(bytes(out))['levels']==levels
    c.dump('encoder_host_check.json',dict(status='PASS',cases=104,valid=103,rejected=1,
           bytes_per_record=264,byte_equal_to_python=True,library_sha256=c.sha(path),
           source_sha256=c.sha(c.HERE/'tag_encoder.c'),scope='host C execution and Python codec; no camera hook'))
    c.finish('encoder-host')
    print('PASS',104)


if __name__=='__main__':main()
