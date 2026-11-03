#!/usr/bin/python3
"""Prepare declared v3 records from final DAT bytes and cold-observed settings."""
import hashlib
import json
from pathlib import Path
import struct
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    dat=(ROOT/'firmware/package_v310_g155_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    records=[]
    cases=[('mount-builtin',2,'builtin',6),('mount-look',2,'look',1),
           ('mount-user',2,'user',2),('28mm-builtin',1,'builtin',6),('50mm-user',0,'user',2)]
    for name,unit,kind,number in cases:
        levels=[100]+[0]*9
        code=number if kind=='builtin' else 0x40+number-1 if kind=='look' else 0x80+number-1
        if kind=='user':
            at=int.from_bytes(dat[204:208],'big')+1408+1216+24*(number-1)
            item=dat[at:at+24]
            for source,destination in enumerate((1,2,3,5)):
                levels[destination]=int.from_bytes(item[10+source:11+source],'big',signed=True)
        record=b'GXR2'+bytes([3,code,unit,1])+struct.pack('>10h',*levels)+dat[20:28]
        record+=struct.pack('>I',zlib.crc32(record))
        assert len(record)==40
        base_path=HERE/'local'/('nodat-'+('50mm' if unit==0 else '28mm' if unit==1 else 'mount')+'-r1-S.bin')
        baseline=base_path.read_bytes()
        assert len(baseline)==4096 and baseline[0xfd4:0xffc]==bytes(40)
        block=bytearray(baseline);block[0xfd4:0xffc]=record
        struct.pack_into('>I',block,0xffc,sum(struct.unpack('>2046H',block[:0xffc]))&0xffffffff)
        target=ROOT/'research/g155/evidence/outputs'/f'{unit}-{kind}-{number}-g155.bin'
        assert target.stat().st_size==552
        for suffix,data in (('record.bin',record),('settings.bin',block),('target.bin',target.read_bytes())):
            (HERE/'local'/f'{name}-{suffix}').write_bytes(data)
        changed=[i for i,(a,b) in enumerate(zip(baseline,block)) if a!=b]
        assert all(0xfd4<=i<0x1000 for i in changed)
        records.append(dict(name=name,unit=unit,kind=kind,number=number,levels=levels,
            record_hex=record.hex(),record_source='记录来源为声明放置，非真实手动保存',
            baseline=str(base_path.relative_to(ROOT)),baseline_sha256=hashlib.sha256(baseline).hexdigest(),
            changed_offsets=changed,container_checksum=f'{int.from_bytes(block[-4:],"big"):08x}',
            settings_sha256=hashlib.sha256(block).hexdigest(),target_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            dat_sha256=hashlib.sha256(dat).hexdigest()))
    # Negative records change only the declared record, plus the native container checksum.
    normal=(HERE/'local/mount-builtin-settings.bin').read_bytes()
    for name,change in [('mount-bad-crc',lambda b:b.__setitem__(0xffb,b[0xffb]^1)),
                        ('mount-cross-unit',lambda b:b.__setitem__(slice(0xfd4,0xffc),(HERE/'local/28mm-builtin-record.bin').read_bytes()))]:
        block=bytearray(normal);change(block)
        struct.pack_into('>I',block,0xffc,sum(struct.unpack('>2046H',block[:0xffc]))&0xffffffff)
        (HERE/'local'/f'{name}-settings.bin').write_bytes(block)
    block=bytearray((HERE/'local/50mm-user-settings.bin').read_bytes())
    block[0xfd4:0xffc]=(HERE/'local/28mm-builtin-record.bin').read_bytes()
    struct.pack_into('>I',block,0xffc,sum(struct.unpack('>2046H',block[:0xffc]))&0xffffffff)
    (HERE/'local/50mm-cross-unit-settings.bin').write_bytes(block)
    (HERE/'evidence/declared-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(records=len(records),negative_records=3)))


if __name__=='__main__':main()
