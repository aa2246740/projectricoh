"""Prepare a valid Vivid-09 logical S fixture without modifying either DAT."""
from pathlib import Path
import json
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import accept_r2 as A
C.setup();C.compute_gate('acceptance-r2-Vivid09-fixture');A.DIR.mkdir(exist_ok=True)
source=C.ROOT/'research/field_gate_r1/local/inputs-v3-auto/g156-test-B.bin'
block=bytearray(source.read_bytes());assert len(block)==4096 and block[0x36e]==9 and block[0x6dd:0x6df]==b'\x09\x09'
raw=C.artifact('test','model')['dat'].read_bytes();assert C.sha(raw)==A.EXPECTED['test']
levels=[100,1,0,0,0,0,0,0,0,0]
record=b'GXR2'+bytes((3,3,2,1))+struct.pack('>10h',*levels)+raw[20:28]
record+=zlib.crc32(record).to_bytes(4,'big');block[0xfd4:0xffc]=record
block[-4:]=(sum(struct.unpack('>2046H',block[:4092]))&0xffffffff).to_bytes(4,'big')
target=A.DIR/'mount-Vivid09-HCBW-plus1-S.bin';target.write_bytes(block)
C.save(A.DIR/'Vivid09-fixture.json',dict(status='PASS',source=str(source.relative_to(C.ROOT)),source_sha256=C.sha(source.read_bytes()),
    fixture=str(target.relative_to(C.ROOT)),sha256=C.sha(block),DAT_sha256=C.sha(raw),native_Vivid_code=9,WB=[9,9],saved_slot=3,saved_levels=levels,
    changed_offsets=[i for i,(x,y) in enumerate(zip(source.read_bytes(),block)) if x!=y],
    boundary='Declared complete logical S read input before MAIN. No CPU/device checkpoint, late RAM forcing or NAND shutdown claim.'))
print(json.dumps(dict(status='PASS',fixture=str(target),selector=9,levels=levels)))
