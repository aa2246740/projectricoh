"""Independent file, directory, package and legacy-data identity checks."""
from pathlib import Path
import hashlib
import json
import struct
import zlib

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()
raw=(ROOT/'firmware/package_v36_g124/SD_ROOT/GXRCE.DAT').read_bytes()
assert len(raw)==58196 and sha(raw)=='ebf07faa3c5b8dcec411da7f7217fb58488adafb942045999bd2cdf7ce98f803'
assert digest(ROOT/'firmware/image_v36/local/package/SD_ROOT/ilaunch3')=='50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008'
frozen=json.loads((OUT/'inputs-before.json').read_text())
expected={p:h for h,p in (line.split('  ',1) for line in (ROOT/'research/g124_ui_v2/SHA256SUMS').read_text().splitlines())}
bad=[p for p,h in expected.items() if frozen.get(p)!=h]
assert not bad,bad
sd=ROOT/'firmware/package_v36_g124/SD_ROOT';old=ROOT/'firmware/package_v36_g120b/SD_ROOT'
card=[]
for line in (ROOT/'firmware/package_v36_g124/CARD_SHA256SUMS').read_text().splitlines():
    h,p=line.split('  ',1);q=sd.parent/p
    assert digest(q)==h,p
    if q.name!='GXRCE.DAT':assert q.read_bytes()==(old/q.name).read_bytes(),q.name
    card.append(p)
assert len(card)==30
u32=lambda p,o:struct.unpack_from('>I',p,o)[0]
assert u32(raw,24)==zlib.crc32(raw[256:])&0xffffffff
header=bytearray(raw[:256]);header[20:24]=bytes(4)
assert u32(raw,20)==zlib.crc32(header)&0xffffffff
comparisons=[]
for generation in (121,123):
    previous=(ROOT/f'firmware/package_v36_g{generation}/SD_ROOT/GXRCE.DAT').read_bytes()
    items=[]
    for unit in range(3):
        d=u32(raw,156)+64*unit;e=u32(previous,156)+64*unit
        a=u32(raw,d+12);b=u32(previous,e+12)
        assert raw[a:a+152]==previous[b:b+152]
        a=u32(raw,d+16)+32;b=u32(previous,e+16)+32
        assert raw[a:a+1024]==previous[b:b+1024]
        items.append(dict(unit=unit,mapping_identical=True,records16_identical=True))
    comparisons.append(dict(generation=generation,units=items))
assert (OUT/'source-change-vs-g123.patch').read_bytes()==(ROOT/'research/g124_ui_v2/source-change-vs-g123.patch').read_bytes()
result=dict(status='PASS',DAT_bytes=len(raw),DAT_sha256=sha(raw),provided_manifest_files=len(expected),provided_manifest_mismatches=bad,
    card_files=len(card),fixed_files_identical=29,comparisons=comparisons,source_patch_reproduced=True)
(OUT/'evidence/input-identity.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS',len(expected),'provided hashes, 30 card hashes, 29 fixed files; gen121/gen123 mappings and 48 slots identical')
