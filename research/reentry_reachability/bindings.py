"""Bind existing resident ELF sections and late-read sources to the pinned body."""
from pathlib import Path
import hashlib
import json
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit

EXTRA = [
    'firmware/resident_v36/local/resident/build/resident.elf',
    'firmware/resident_v36/local/resident/build/resident.map',
    'firmware/engine_v46_ui/candidate/containers/product/adapter.c',
    'firmware/engine_v45_verify/candidate/containers/product/adapter.c',
    'firmware/engine_diag_v1/candidate/containers/product/diag.c',
    'firmware/package_v36_g124/SD_ROOT/GXRCE.DAT',
    'firmware/package_v36_g123/SD_ROOT/GXRCE.DAT',
    'firmware/package_v36_g122/SD_ROOT/GXRCE.DAT',
    'firmware/package_v36_diag1/local/SD_ROOT/GXRCE.DAT',
    'research/review_g124/safety_cases.py',
    'research/review_g124/cold_reentry.py',
    'research/review_g124/reentry_all_keys.py',
    'research/review_g123/lock_nested.py',
    'research/review_diag/replay.py',
    'research/diag_dat_v1/native_support.py',
    'tools/native_harness/field_replay.py',
    'research/emulator_m2/local/task6-wait-stack.json',
    'research/emulator_m2/local/unit-ready-probe.json',
    'research/emulator_m2/local/final-ui-timeout.json',
]


def elf(path):
    data=path.read_bytes()
    assert data[:6]==b'\x7fELF\x01\x02'
    header=struct.unpack_from('>16sHHIIIIIHHHHHH',data)
    records=[struct.unpack_from('>10I',data,header[6]+i*header[11]) for i in range(header[12])]
    names=records[header[13]]
    strings=data[names[4]:names[4]+names[5]]
    sections=[]
    symbols={}
    for section_index,row in enumerate(records):
        name=strings[row[0]:].split(b'\0')[0].decode()
        sections.append(dict(index=section_index,name=name,type=row[1],flags=row[2],address=row[3],offset=row[4],size=row[5]))
        if row[1]==2:
            table=records[row[6]]
            strings2=data[table[4]:table[4]+table[5]]
            for pos in range(row[4],row[4]+row[5],row[9]):
                n,value,size,info,other,section=struct.unpack_from('>IIIBBH',data,pos)
                symbol=strings2[n:].split(b'\0')[0].decode()
                if symbol:symbols[symbol]=dict(address=value,size=size,info=info,section=section)
    return data,sections,symbols


def main():
    audit.preflight()
    before=audit.OUT/'additional-inputs-before.json'
    rows=[dict(path=rel,size=(audit.ROOT/rel).stat().st_size,sha256=audit.digest(audit.ROOT/rel)) for rel in EXTRA]
    if before.exists():
        assert json.loads(before.read_text())==rows,'additional input changed'
    else:audit.save('additional-inputs-before.json',rows)
    raw,segments=audit.image('v36')
    data,sections,symbols=elf(audit.ROOT/EXTRA[0])
    checked=[]
    for section in sections:
        if section['flags']&2 and section['type']!=8 and section['size']:
            material=data[section['offset']:section['offset']+section['size']]
            assert material==audit.at(raw,segments,section['address'],section['size']),hex(section['address'])
            checked.append({**{key:value for key,value in section.items() if key!='name'},
                'sha256':hashlib.sha256(material).hexdigest()})
    audit.save('local/resident-symbols.json',symbols)
    audit.save('local/resident-elf-binding.json',dict(status='PASS',sections=checked,
        elf_sha256=hashlib.sha256(data).hexdigest(),image_sha256=audit.IMAGES['v36'][1]))
    original,old_segments=audit.image('official')
    intervals=[(0x200628ac,0x20062b44),(0x20062f18,0x200630f4),(0x20068a98,0x20069400),
        (0x2006a53c,0x2006adcc),(0x200718b8,0x20072ef8),(0x202aeaf8,0x202b1388),
        (0x20374d00,0x20380200),(0x05000c00,0x0500f8fc)]
    comparisons=[]
    for lo,hi in intervals:
        same=audit.at(raw,segments,lo,hi-lo)==audit.at(original,old_segments,lo,hi-lo)
        assert same,(hex(lo),hex(hi))
        comparisons.append(dict(first=lo,end=hi,identical=True))
    audit.save('local/official-comparison.json',comparisons)
    print(json.dumps(dict(status='PASS',resident_sections=len(checked),original_ranges=len(comparisons),additional_inputs=len(rows))))


if __name__=='__main__':main()
