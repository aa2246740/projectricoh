"""Independent Python structure/CRC checks and read-only codec roundtrip."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def main():
    guard();raw=(PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes();records=0
    for unit in range(3):
        directory=u32(raw,156)+64*unit;at=u32(raw,directory+16)+32
        for slot in range(1,17):
            row=raw[at+64*(slot-1):at+64*slot]
            assert row[0]==slot and u32(row,60)==crc(row[:60]);records+=1
    sys.path.insert(0,str(ROOT/'studio/src'))
    from gxr_studio.camdata import datcodec
    parsed=datcodec.parse(raw);assert datcodec.pack(parsed)==raw
    detail=strict_effects(raw);assert detail['count']==15
    result=dict(status='PASS',dat_sha256=sha(raw),records=records,complete_fx_count=15,codec_byte_roundtrip=True)
    save(HERE/'evidence/python.json',result);print(json.dumps(result))


if __name__=='__main__':main()
