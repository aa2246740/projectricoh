"""Can one shared curve use the existing flags7 format without extra curve rows?"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import zlib

assert sys.flags.isolated
ROOT=Path(__file__).resolve().parents[2]
LOCAL=Path(__file__).resolve().parent/'local'
if os.getpriority(os.PRIO_PROCESS,0)<15:os.nice(15-os.getpriority(os.PRIO_PROCESS,0))


def promote(entry,mask,D):
    b=bytearray(entry)
    assert b[1]==1 and b[114]>=128
    b[1]=7;b[445:447]=bytes(2);b[379:412]=b[82:115];b[412:445]=b[82:115]
    content=bytes(b[:2])+bytes(b[445:447])+bytes((mask,))
    content+=b''.join(b[o:o+n] for o,n in zip(D.OFFSETS,D.ROW_BYTES))
    b[4:8]=struct.pack('>I',zlib.crc32(content)&0xffffffff)
    for off,size,crc_off in D.CRC_FIELDS:
        struct.pack_into('>I',b,crc_off,zlib.crc32(b[off:off+size])&0xffffffff)
    assert all(D._valid_look_row(b[o:o+n],j,7) for j,(o,n) in enumerate(zip(D.OFFSETS,D.ROW_BYTES)))
    return bytes(b)


def main():
    parser=ROOT/'research/recipe_redo_r1/local/source/studio_snapshot/src/gxr_studio/camdata/datcodec.py'
    spec=importlib.util.spec_from_file_location('film_promote_parser',parser)
    D=importlib.util.module_from_spec(spec);sys.modules[spec.name]=D;spec.loader.exec_module(D)
    raw=(LOCAL/'frozen/firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    dat=D.parse(raw);shared=struct.unpack_from('>I',raw,192)[0];pools=[]
    for k in range(4):
        n,size,offset,crc=struct.unpack_from('>HHII',raw,shared+16+12*k)
        pools.append((n,size,shared+offset))
    old=D._parse_looks(dat,raw,pools);modified=copy.deepcopy(dat)
    for unit in range(3):
        for slot in (3,5):
            b=bytearray(modified.entry_of(unit,slot));b[1]=7;b[445:447]=bytes(2)
            b[379:412]=b[82:115];b[412:445]=b[82:115]
            for off,size,crc_off in D.CRC_FIELDS:struct.pack_into('>I',b,crc_off,zlib.crc32(b[off:off+size])&0xffffffff)
            assert all(D._valid_look_row(b[o:o+n],j,7) for j,(o,n) in enumerate(zip(D.OFFSETS,D.ROW_BYTES)))
            modified.modules[unit].entries[modified.modules[unit].refs[slot-1]]=bytes(b)
    area=bytearray(modified.effect_area);proof=[]
    for index,look in enumerate(old):
        at=32+index*32;descriptor=bytearray(area[at:at+32])
        b=promote(look.entry,descriptor[18],D)
        descriptor[1]=7;descriptor[2:4]=bytes(2);descriptor[4:8]=b[4:8]
        descriptor[14]=descriptor[9];descriptor[15]=descriptor[9]
        area[at:at+32]=descriptor
        proof.append(dict(name=look.name,mask=descriptor[18],base=descriptor[0],
            original_sha256=hashlib.sha256(look.entry).hexdigest(),promoted_sha256=hashlib.sha256(b).hexdigest(),
            promoted_entry_hex=b.hex(),R_G_B_curve_references_identical=True))
    struct.pack_into('>I',area,24,zlib.crc32(area[32:])&0xffffffff)
    struct.pack_into('>I',area,28,zlib.crc32(area[:28])&0xffffffff)
    modified.effect_area=bytes(area)
    parsed=D._parse_looks(modified,raw,pools)
    assert len(parsed)==18
    for item,look in zip(proof,parsed):assert bytes.fromhex(item['promoted_entry_hex'])==look.entry
    result=dict(status='PASS_EXISTING_PARSER',logical_Looks=18,base_slots=[3,5],base_flags=7,
        Look_flags=7,three_curves_reference_one_shared_row=True,extra_curve_rows=0,
        effect_area_bytes_before=len(dat.effect_area),effect_area_bytes_after=len(modified.effect_area),
        no_new_DAT_serialized_or_written=True,base_application_metadata_deliberately_preserved=True,
        default_forward_and_knob_equivalence_not_yet_verified=True,
        parser_sha256=hashlib.sha256(parser.read_bytes()).hexdigest(),proof=proof)
    (LOCAL/'promote_shared_parser_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PROMOTION PARSER PASS:',len(parsed),'Looks; flags7 withR=G=B, zero extra curve rows, same area bytes')


if __name__=='__main__':main()
