#!/usr/bin/env python3
"""Exercise native format limits and signed zero with an independent fixture."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ctypes as ct
import json
import struct
import subprocess
import runtime as r
import tweak as t
import verify


def main():
    r.setup();src,surface,base,entries=r.baseline()
    lib=ct.CDLL(str(r.LOCAL/'native/libtweak_r2.dylib'))
    ptr=ct.POINTER(ct.c_uint8);array=lambda b:(ct.c_uint8*len(b)).from_buffer_copy(b)
    lib.rt_saturation.argtypes=[ptr,ptr,ct.c_int,ct.c_int,ptr,ptr,ct.POINTER(ct.c_uint16)]
    lib.rt_saturation.restype=ct.c_int;lib.check_wb.argtypes=[ptr,ptr];lib.check_wb.restype=ct.c_int
    c=bytes([127,255,0,128]*24);words=list(struct.unpack('>28H',entries['01']['rows'][3]))
    for j in (0,14):
        for i in range(3,9):words[j+i]=1279|((i%2)*2048)
    m=struct.pack('>28H',*words);co=(ct.c_uint8*96)();mo=(ct.c_uint8*56)();g=(ct.c_uint16*3)()
    expected_c,expected_m,info=t.saturation(c,m,8)
    assert lib.rt_saturation(array(c),array(m),8,1,co,mo,g)==3
    assert bytes(co)==expected_c==c and bytes(mo)==expected_m==m
    assert list(g)==[t.GAINS[-1],4096,4096]
    # Even this saturated synthetic entry must pass the real format validators.
    index=src.TABLE_SLOTS.index(1);raw=base[16+index*448:16+(index+1)*448]
    rows=list(entries['01']['rows']);rows[2]=c;rows[3]=m
    encoded=t.encode_entry(raw,rows)
    blob=verify.reused_functions()['table_with'](src,base,1,encoded)
    src.parse(blob,surface)
    cp=subprocess.run([str(r.LOCAL/'native/validator')],input=bytes([1])+blob,capture_output=True,timeout=55)
    assert cp.returncode==0
    # Negative zero must survive under- and oversaturation.
    zero=bytes([0,128]*48)
    for level in (-8,0,8):
        ec,em,info=t.saturation(zero,entries['01']['rows'][3],level)
        assert lib.rt_saturation(array(zero),array(entries['01']['rows'][3]),level,1,co,mo,g)>=0
        assert ec==bytes(co)==zero and em==bytes(mo)
    wb_invalid=0;out=(ct.c_uint8*2)()
    for slot in r.SLOTS:
        recipe=src.recipe_struct(surface,int(slot))
        for value in (-9,9):
            candidate=recipe[:-2]+bytes((value&255,0))
            assert lib.check_wb(array(candidate),out)==-1;wb_invalid+=1
    malformed=bytearray(m);malformed[6]|=0x10
    assert lib.rt_saturation(array(c),array(malformed),0,1,co,mo,g)==-1
    r.dump(r.LOCAL/'edge_checks.json',dict(passed=True,synthetic_full_headroom_limit_flags=3,
        synthetic_default_bytes_preserved=True,signed_zero_preserved=True,
        original_native_validator_stdout=cp.stdout.decode().strip(),
        bad_native_WB_recipes_rejected=wb_invalid,invalid_chroma_matrix_rejected=True))
    print(json.dumps(dict(passed=True,bad_native_WB_rejected=wb_invalid)))


if __name__=='__main__':main()
