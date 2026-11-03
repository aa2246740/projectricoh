"""Retain native facts as locations, labels and hashes, never firmware bytes."""
from pathlib import Path
import hashlib
import json
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
listing = scope.load(scope.ROOT/'research/unit28_stock/m32r_listing.py', 'review144_listing')
body_path = scope.ROOT/'firmware/package_v38_g137/local/SD_ROOT/ilaunch3'
body = body_path.read_bytes()
u32 = lambda at: int.from_bytes(listing.read(body, at, 4), 'big')
index_path = scope.ROOT/'research/stage1_ui/text-resource-index.json'
index = json.loads(index_path.read_text())
inverse = {int(g,16): c for c,g in index['ascii_conversion_map'].items()}
resource_path = scope.ROOT/'artifacts/firmware/gxr-1.51/ilaunch4'
resource = resource_path.read_bytes()
entry = index['english_resource']
start = int(entry['file_offset'], 16)
length = int(entry['length'],0) if isinstance(entry['length'],str) else entry['length']
strings = resource[start:start+length].split(b'\0')
rows = []
names = u32(0x2022f650)
for row in range(listing.read(body,0x2022f654,1)[0]):
    ptr = u32(names+4*row)
    resource_id = (ptr-0x205be300)//4
    raw = strings[resource_id]
    label = ''.join(inverse[g] for g in struct.unpack('>%dH'%(len(raw)//2),raw))
    rows.append(dict(row=row+1,resource_id=hex(resource_id),text=label,
        stored_value=listing.read(body,0x2037f4b9+row+1,1)[0]))
eighth = listing.read(body,0x2023fd8c,12)
assert eighth == bytes(12)
ascii_keys = listing.read(body,0x2023bc6f,60) + listing.read(body,0x2023bcab,34)
assert max(ascii_keys.count(c) for c in range(32,127)) <= 1
languages = []
for language in range(10):
    upper, lower = u32(0x202224e0+4*language), u32(0x2022250c+4*language)
    listing.read(body,upper,120)
    listing.read(body,lower,68)
    languages.append(dict(language=language,upper=hex(upper),lower=hex(lower)))
converter = listing.read(body,0x201d330c,0x201d37d4-0x201d330c)
scope.save(scope.HERE/'native-metadata.json',dict(body_sha256=scope.sha(body_path),
    resource_sha256=scope.sha(resource_path), character_index_sha256=scope.sha(index_path),
    exposure_compensation=dict(field='S+0x63b', getter='0x2026d85c', setter='0x202712e4',
        constructor='0x2028b678', descriptor='0x2022f650', labels=rows,
        parameter_store='0x202d45a8', parameter_offset='0x17',
        legal_stored_range=[3,19],invalid_value_replacement=9),
    detail_row8=dict(address='0x2023fd8c',size=12,zero=True,sha256=hashlib.sha256(eighth).hexdigest()),
    ascii_converter=dict(address='0x201d330c',sha256=hashlib.sha256(converter).hexdigest(),
        frame_bytes=556, printable_input=[32,126], max_matches_per_ascii=1,
        max_output_for_8_chars=17,languages=languages, language_10_normalized_to=1)))
print('NATIVE_METADATA_PASS',len(rows),'EV labels; row8 details zero',flush=True)
