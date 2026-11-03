#!/usr/bin/env python3
"""Recreate byte-checked excerpts and a local address-to-line index."""
import hashlib
import json
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from trace import instructions, FW, sections, offset

WINDOWS=[
 ('metadata-reader-prologue',0x201738f4,0x20173924),
 ('metadata-reader-fields',0x201741ac,0x20174374),
 ('metadata-reader-return',0x20174548,0x20174588),
 ('metadata-tag-caller',0x20171cf8,0x20171d34),
 ('metadata-writer-prologue',0x2019ba40,0x2019ba58),
 ('normalized-builder-entry',0x201999c8,0x20199a88),
 ('context-getter',0x2019b47c,0x2019b488),
 ('parser-builder-call',0x20198460,0x20198490),
 ('normalized-builder-fields',0x20199ccc,0x20199e00),
 ('normalized-flag-source',0x20199bf4,0x20199c28),
 ('normalized-preset-override',0x20199f54,0x20199fe0),
 ('normalize-enum',0x20199760,0x201997ac),
 ('special-flag',0x201994d8,0x201994e8),
 ('contrast-selector',0x2010e80c,0x2010e9a8),
 ('contrast-builder-entry',0x2010e544,0x2010e5b4),
 ('contrast-pack-selector',0x2010eb1c,0x2010eb84),
 ('isp-dispatch-and-pack',0x2010bea4,0x2010c248),
 ('isp-apply-selected',0x2010c248,0x2010c3f4),
 ('isp-apply-caller',0x20105480,0x201054f4),
 ('isp-q-getter',0x2010be98,0x2010bea4),
 ('isp-pointers-init',0x2011a768,0x2011a8c8),
 ('lut-index-and-apply',0x2011838c,0x20118468),
 ('lut-packer',0x20118468,0x20118788),
 ('hardware-apply-dispatch',0x20255600,0x20255740),
 ('hardware-prefix-writer',0x202569a0,0x202569c8),
 ('hardware-lut-writer',0x20257430,0x20257490),
 ('hardware-color-writer',0x20257550,0x2025764c),
 ('hardware-sharpness-writer',0x20257690,0x20257914),
 ('glut-rejected-candidate',0x2010ec08,0x2010ec98),
 ('vividness-builder',0x2010d9fc,0x2010e544),
 ('color-buffer-getter',0x20113894,0x201138bc),
 ('color-hardware-apply',0x20113954,0x2011396c),
 ('color-mapper',0x2011396c,0x20113fb4),
 ('color-table-loaders',0x201141c0,0x20114288),
 ('sharpness-builder',0x20110e0c,0x20111ca0),
 ('shared-hardware-getter',0x20115b30,0x20115b58),
 ('shared-hardware-apply',0x20115e68,0x20115e80),
 ('shared-hardware-packer-example',0x20115e80,0x20116008),
]

def main():
    data=(FW/'jlaunch3').read_bytes();secs=sections(data)
    cached=list(instructions())
    for label,start,end in WINDOWS:
        out=[f'# jlaunch3 VMA {start:#x}..{end:#x}; file {offset(start,secs):#x}..{offset(end-1,secs)+1:#x}',
             '# Each original line and all emitted machine bytes are checked against the firmware.']
        for va,b,op,p,no,line in cached:
            if start<=va<end:
                off=offset(va,secs);assert data[off:off+len(b)]==b
                out.append(f'{p}:{no} | {line}')
        (HERE/(label+'.disasm.txt')).write_text('\n'.join(out)+'\n')
        print(label,len(out)-2)
    source={va:(b,op,p,no) for va,b,op,p,no,line in cached}
    index={};checked=0
    for label,start,end in WINDOWS:
        path=HERE/(label+'.disasm.txt')
        for no,line in enumerate(path.read_text().splitlines(),1):
            m=re.search(r'\|\s*([0-9a-f]+):',line)
            if not m:continue
            va=int(m[1],16);b,op,p,original_no=source[va];off=offset(va,secs)
            assert data[off:off+len(b)]==b
            index.setdefault(hex(va),[]).append({'excerpt':path.name,'line':no,
                       'original':p,'original_line':original_no,'file_offset':hex(off),'instruction':op})
            checked+=1
    (HERE/'evidence_index.json').write_text(json.dumps(index,indent=2)+'\n')
    inputs={n:hashlib.sha256((FW/n).read_bytes()).hexdigest() for n in ['jlaunch3','jlaunch4']}
    expected=json.loads((HERE/'inventory.json').read_text())
    assert all(inputs[n]==expected[n]['sha256'] for n in inputs)
    result={'checked_excerpt_lines':checked,'input_sha256_unchanged':inputs,
            'windows':len(WINDOWS),'executed_firmware':False,'camera_connected':False}
    (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
