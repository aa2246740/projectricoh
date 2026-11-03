"""Independently confirm rejected record fields and the final byte round trip."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *


def record_errors(raw):
    errors=[]
    for unit in range(3):
        start=u32(raw,u32(raw,156)+64*unit+16)+32
        for slot in range(1,17):
            r=raw[start+64*(slot-1):start+64*slot]
            if r[0]!=slot:
                errors.append(dict(unit=unit,slot=slot,field='record slot',actual=r[0],expected=slot))
            if u32(r,60)!=crc(r[:60]):
                errors.append(dict(unit=unit,slot=slot,field='record CRC',actual=u32(r,60),expected=crc(r[:60])))
    return errors


def main():
    guard()
    original=(HERE/'local/initial-candidate/GXRCE.DAT').read_bytes()
    errors=record_errors(original)
    assert len(errors)==6 and all(e['slot']==6 for e in errors)
    raw=(PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes()
    assert record_errors(raw)==[]
    sys.path.insert(0,str(ROOT/'studio/src'))
    from gxr_studio.camdata import datcodec
    parsed=datcodec.parse(raw)
    assert datcodec.pack(parsed)==raw
    result=dict(status='PASS',backend='Python',initial_candidate_sha256=sha(original),
                initial_bank_rejection_confirmed=errors,final_dat_sha256=sha(raw),
                final_records_valid=48,studio_byte_round_trip=True)
    save(HERE/'evidence/python.json',result)
    print(json.dumps(result))


if __name__=='__main__':
    main()
