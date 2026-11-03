"""Locate the observed Ricoh ShotInfo bytes in the original DNG/JPEG carriers."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import boundary as b
import artifacts as a
from images import load

def main():
    ac=load('offset_capture',b.ROOT/'research/color_calibration/analyze_capture.py')
    session=load('offset_session',b.ROOT/'research/chart_session_20261024/session_runtime.py')
    session.patch_tiff(ac.Tiff);out=[]
    for number in range(1476,1482):
        stem=f'R805{number:04d}';folder=(a.OLD_CARD if number<1478 else a.CARD)/'root/DCIM/100RICOH'
        for suffix in ('DNG','JPG'):
            path=b.add(folder/(stem+'.'+suffix));raw=path.read_bytes()
            base=0 if suffix=='DNG' else raw.index(b'Exif\0\0')+6
            t=ac.Tiff(raw[base:]);info=ac.shot_info(t)
            record_offset=info['maker_shot_record_offset_in_tiff'];start=base+record_offset
            record=raw[start:start+224]
            assert record.hex(' ')==info['maker_shot_record_hex']
            out.append(dict(file=str(path.relative_to(b.ROOT)),tiff_file_offset=hex(base),
                ShotInfo_file_offset=hex(start),ShotInfo_bytes=224,
                selector_file_offset=hex(start+0x28),selector=record[0x28],
                tone_fields_file_offset=hex(start+0x31),tone_raw=list(record[0x31:0x34]),
                colour_fields_file_offset=hex(start+0x78),colour_raw=list(record[0x78:0x82]),
                ISO=info['iso'],date_time=info['date_time']))
    b.dump('maker_note_offsets.json',out)
    print('PASS located 224-byte Ricoh ShotInfo in 12 carriers; selector+0x28, tone+0x31, colour+0x78')

if __name__=='__main__':main()
