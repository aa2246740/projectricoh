#!/usr/bin/python3 -I
"""Check that identity comparison accepts identity edits and rejects other edits."""
from pathlib import Path
import json
import os
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from identity_compare import compare
from static_check import BASE, Elf, ROOT, checksum, offset

temp = Path(os.environ['REVIEW_TEMP'])
old_elf = ROOT / 'firmware/resident_v39/local/resident/build/resident.elf'
old_body = ROOT / 'firmware/image_v39/local/ilaunch3'
elf = Elf(old_elf)
trust = elf.symbols['rv_trust'][0]
content = elf.sections['.resident']['data']
section_at = elf.raw.index(content)
assert elf.raw.count(content) == 1
new_elf = temp / 'resident.elf'
new_body = temp / 'ilaunch3'


def fixture(elf_address, body_address, update_checksum=True):
    a, b = bytearray(elf.raw), bytearray(old_body.read_bytes())
    if elf_address is not None:
        a[section_at + elf_address - BASE] ^= 1
    b[body_address] ^= 1
    if update_checksum:
        struct.pack_into('>I', b, 0x16c, checksum(b))
    new_elf.write_bytes(a)
    new_body.write_bytes(b)


fixture(trust + 32, offset(trust + 32))
result = compare(old_elf, new_elf, old_body, new_body)
assert result['build_id_changed'] and not result['abi_id_changed']
rows = [{'case': 'identity_only', 'accepted': True}]
for name, a, b, update in (('code_byte', BASE + 20, offset(BASE + 20), True),
                          ('replacement_word', None, offset(0x2028709c) + 1, True),
                          ('root_pin', None, offset(0x200547f4), True),
                          ('checksum', trust + 32, offset(trust + 32), False)):
    fixture(a, b, update)
    try:
        compare(old_elf, new_elf, old_body, new_body)
    except AssertionError:
        rows.append({'case': name, 'accepted': False})
    else:
        raise AssertionError(name)
out = ROOT / 'research/review_body_v39/evidence/identity-check.json'
out.write_text(json.dumps({'status': 'PASS', 'cases': rows}, indent=1) + '\n')
print(json.dumps({'status': 'PASS', 'cases': len(rows)}))
