"""Change only the 40-byte record in a proven g156 restoration input."""
from pathlib import Path
import json
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
old=C.ROOT/'research/tweak_memory_r1/local/p1final-50-menu1-final-S-persistent.bin'
control=C.ORIGINAL/'local/r4-reference-test-50mm-flow-settings.bin'
a,b=old.read_bytes(),control.read_bytes()
assert len(a)==len(b)==4096
old_record,new_record=a[0xfd4:0xffc],b[0xfd4:0xffc]
old_dat=(C.ROOT/'firmware/package_v310_g155c_test/GXRCE.DAT').read_bytes()
new_dat=(C.PACKAGES['test']/'GXRCE.DAT').read_bytes()
assert old_record[:28]==new_record[:28]
assert old_record[28:36]==old_dat[20:28] and new_record[28:36]==new_dat[20:28]
assert zlib.crc32(old_record[:36])==int.from_bytes(old_record[36:40],'big')
assert zlib.crc32(new_record[:36])==int.from_bytes(new_record[36:40],'big')
fixture=bytearray(b);fixture[0xfd4:0xffc]=old_record
fixture[-4:]=(sum(struct.unpack('>2046H',fixture[:4092]))&0xffffffff).to_bytes(4,'big')
assert b[:0xfd4]==fixture[:0xfd4] and b[0xffc:4092]==fixture[0xffc:4092]
out=C.LOCAL/'g155c-record-in-g156-settings.bin';out.write_bytes(fixture)
C.save(C.HERE/'evidence/old-record-fixture.json',dict(status='PASS',
    source=str(old.relative_to(C.ROOT)),source_sha256=C.sha(a),
    control=str(control.relative_to(C.ROOT)),control_sha256=C.sha(b),
    fixture=str(out.relative_to(C.ROOT)),fixture_sha256=C.sha(fixture),
    changed_offsets=[i for i,(x,y)in enumerate(zip(b,fixture))if x!=y],
    old_record=old_record.hex(),current_record=new_record.hex(),
    same_category_unit_flags_and_nonzero_levels=True,only_DAT_pair_and_record_checksum_differ=True))
print(json.dumps(dict(status='PASS',fixture=str(out.relative_to(C.ROOT)))))
