#!/usr/bin/env python3
"""Address/word facts used in the report, checked directly against official input."""
import csv
import importlib.util
import struct
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mine',HERE/'mine.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

ADDRESSES = {
    'ilaunch3': [
        (0x2015DA08,'Main image to small JPEG resize descriptor construction'),
        (0x2015DAE0,'Request 18: config+apply with r5=1'),
        (0x2015DAFC,'Submit memory image conversion/resize'),
        (0x200F1458,'High-level configuration request entry'),
        (0x200F3878,'Build ISP stage mirrors'),
        (0x200F3C10,'Apply selected ISP stages'),
        (0x200F3F38,'MCM configuration builder'),
        (0x200F406C,'Request 18 chooses MCM control 11'),
        (0x200F7C34,'type 28 wrapper'),
        (0x200F7D38,'MCM packer'),
        (0x200F8038,'MCM packer C004/sector selection'),
        (0x200F80D8,'MCM packer matrix selection'),
        (0x20101ECC,'MCM matrix bank start'),
        (0x20101F20,'MCM row 4, identity matrix'),
        (0x20108794,'MCM live initialized mirror'),
        (0x201086E4,'type 26 initialized mirror'),
        (0x200F7820,'type 26 wrapper'),
        (0x200F8CE8,'P stage-pointer getter'),
        (0x204F0594,'P stage-pointer state'),
        (0x200F06AC,'Memory resize frontend'),
        (0x203E21B4,'Native backend wrapper'),
        (0x203E5A8C,'Native MMIO backend'),
        (0x2015F9D8,'Main JPEG wrapper call boundary'),
        (0x2016583C,'Main JPEG wrapper'),
        (0x203ED714,'JPEG input DMA descriptor wrapper'),
        (0x203F20D0,'JPEG DMA input format/geometry setter'),
        (0x203CA3A8,'type 38 writer'),
        (0x203D0E08,'F0234002..404c control writer'),
        (0x203CCCEC,'F023 control writer caller'),
    ],
    'jlaunch3': [
        (0x20255600,'ISP dispatcher'),
        (0x2010E5A4,'WDR/RLUT/LUT native request builder'),
        (0x20118468,'type 26 packer'),
        (0x20143004,'type 26 mirror'),
        (0x2012F504,'Type26 input A5'),
        (0x2012FFFC,'Type26 output B5'),
        (0x2013024E,'Type26 C/D bank'),
        (0x20130290,'RLUT six input rows'),
        (0x20130404,'RLUT six first output rows'),
        (0x20130590,'RLUT six second output rows'),
        (0x2013071C,'RLUT six third output rows'),
        (0x201195A4,'RLUT packer'),
        (0x20143118,'RLUT mirror'),
        (0x2014322C,'WDR mirror, 278 u32'),
        (0x2026782C,'WDR clock/gate function'),
        (0x2011825C,'EXIP packer'),
        (0x20142F90,'EXIP mirror'),
        (0x20118180,'AWBIP control setter'),
        (0x20142F7C,'AWBIP initialized mirror'),
        (0x2012D0C0,'MCM matrix row 1'),
        (0x2012D0DC,'MCM matrix row 2'),
        (0x2010D800,'Native grey/toning mapper'),
        (0x20115638,'Grey/TE sector row selector, row28 or row29'),
        (0x2011564C,'Native two-byte toning value selector/interpolator'),
        (0x2010E1A4,'Store native toning u16 into MCM cfg+2'),
        (0x201152A0,'Pack cfg+2 into MCM C004 mirror word'),
        (0x2012D0B4,'Non-T native B&W toning word, 0x8080'),
        (0x2012D0BA,'Non-T ordinary colour toning word, 0x0000'),
        (0x20142AB4,'C004 mirror word'),
        (0x2012C0F4,'C040 row 1'),
        (0x2012C5D4,'C080 row 1'),
        (0x2012C600,'C080 sector 11 in row 1'),
        (0x2012D1A0,'C120 ROM nodes row 1'),
        (0x2012D1F4,'C120 ROM gains row 1'),
        (0x20383E68,'C040/C080/C120 selector cache; BSS/state, no initial file bytes'),
        (0x20114FB8,'MCM packer'),
        (0x20142AB0,'MCM mirror'),
        (0x201080B8,'Spatial gain/type14 packer'),
        (0x201084B0,'Spatial gain Q10/mask conversion'),
        (0x201B2424,'Native spatial mask generator'),
        (0x20195340,'Native grain generator'),
        (0x201254A4,'GLUT/type34 uploader'),
    ],
    'nlaunch3': [
        (0x20191D5C,'Native scene19 dispatch to DR main'),
        (0x2019073C,'Native DR main entry'),
        (0x201A120C,'Common Q builder initializes WDR parameter state to zero'),
        (0x20191244,'Native DR main overrides WDR parameter state to one'),
        (0x201912B4,'Native DR main requests ISP kind50 with apply=1'),
        (0x201050C4,'Native request/apply wrapper'),
        (0x2010B9A8,'Native Q getter, 20399A20'),
        (0x201A07F4,'Scene-to-ISP-effect mapping'),
        (0x202304EC,'Scene jump table'),
        (0x201A0854,'Scene19 -> ISP effect15'),
        (0x201A0D38,'Write ISP effect to Q+4'),
        (0x2010E540,'Native WDR table generator wrapper call'),
        (0x2010E548,'Native WDR bypass clear'),
        (0x2011A258,'Native WDR generation wrapper'),
        (0x2011B738,'Native WDR generator'),
        (0x2011A280,'Native WDR data packer'),
        (0x2010BC38,'Native WDR packer caller'),
        (0x2010BDD0,'Native WDR upload caller'),
        (0x2011A22C,'type21 wrapper'),
        (0x2026BA00,'P10 ISP dispatcher'),
        (0x2026D188,'type21 hardware writer'),
        (0x20144C64,'P10 WDR mirror'),
    ],
    'l06firm3': [
        (0x20140F58,'A16 WDR initialized mirror'),
        (0x2010C6F4,'A16 builder starts WDR control at 1'),
        (0x2011875C,'A16 WDR control setter, no full table packer here'),
    ],
}

def main():
    body=m.Image('ilaunch3')
    matrix=list(struct.unpack('>14H',body.read(0x20101F20,28)))
    assert matrix==[1024,0,0,0,1024,0,0,0,1024,0,0,0,0,0]
    assert body.read(0x20100DCC+6,1)==b'\x00'
    b=body.read(0x201086E4,176)
    assert struct.unpack_from('>I',b)[0]==0
    # First node occupies the low halfword at +4; high halfword is padding.
    assert list(struct.unpack_from('>31H',b,6))==list(range(128,3969,128))
    outputs=[list(b[a:a+33]) for a in (0x44,0x68,0x8c)]
    assert all(v==list(range(0,256,8))+[255] for v in outputs)
    m.save(m.EVIDENCE/'body-colour-identities.json',dict(
        matrix_row4_vma='0x20101f20',matrix14_u16=matrix,
        mcm_mirror_vma='0x20108794',mcm_mirror_index6_maps_to=0,
        lut_mirror_vma='0x201086e4',lut_initial_control=0,
        lut_input31_offset=6,
        lut_input31=list(struct.unpack_from('>31H',b,6)),lut_outputs33=outputs,
        caveat='Initial uniform knots and outputs support identity LUT interpretation; hardware rounding and request18 active path still require a probe.'))
    j=m.Image('jlaunch3')
    params=m.parse_params('jlaunch8')
    toning={}
    for a in (0x1230,0x123A,0x1244,0x124E,0x1258):
        raw=bytes(params[k] for k in range(a,a+10))
        values=list(struct.unpack('>5H',raw))
        toning[hex(a)]=dict(packed_u16=[hex(v) for v in values],
            signed_magnitude_byte_pairs=[[(x&127)*(-1 if x&128 else 1)
                                         for x in v.to_bytes(2,'big')] for v in values])
    assert j.read(0x2012D0B4,2)==bytes.fromhex('8080')
    assert j.read(0x2012D0BA,2)==bytes.fromhex('0000')
    assert j.read(0x2012CFF4,96)==bytes(96)
    destinations={}
    for internal in range(12):
        delta=struct.unpack('>h',j.read(0x2012BE40+2*internal,2))[0]
        destinations[internal]=hex(0x20115678+delta)
    assert destinations[5]=='0x201159a0' and destinations[6]=='0x201159ac'
    m.save(m.EVIDENCE/'native-toning-c004.json',dict(
        image='jlaunch3',native_control_rows=toning,
        native_bw_tone_source='0x2012d0b4',native_bw_tone_word='0x8080',
        ordinary_colour_tone_source='0x2012d0ba',ordinary_colour_tone_word='0x0000',
        native_internal_type_targets=destinations,
        grey_or_te_sector_row=28,sector_row_vma='0x2012cff4',sector_row_all_zero=True,
        selector='0x2011564c',cfg_write='0x2010e1a4',packer='0x201152a0',
        mirror='0x20142ab4',hardware_payload_register='0xf034c004',
        software_byte_encoding='sign-magnitude observed in native interpolation; 0x80 represents negative zero',
        unknown=['Pixel equation','Channel order and effective scale','Whether additive or luminance-proportional',
                 'Hardware order relative to matrix/sector','Ordinary colour mode response and bypass']))
    with (m.EVIDENCE/'key-addresses.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['image','vma','file_offset_if_initialized','description'])
        for name,rows in ADDRESSES.items():
            im=m.Image(name)
            for va,label in rows:
                try: off=hex(im.offset(va))
                except AssertionError: off='RAM/BSS only'
                w.writerow([name,hex(va),off,label])
    print('Key addresses and body identity data OK')

if __name__=='__main__':main()
