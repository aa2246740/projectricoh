#!/usr/bin/env python3
"""Search full factory banks across seven images; no same-offset assumptions."""
import importlib.util
import struct
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('cross',HERE/'cross_units.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
m=c.m
BANKS={
 'tone_A22':(0x2012F40C,22*62), 'tone_B22':(0x2012FF78,22*33),
 'tone_CD':(0x2013024E,66), 'RLUT_input6':(0x20130290,6*62),
 'RLUT_output0_6':(0x20130404,6*66), 'RLUT_output1_6':(0x20130590,6*66),
 'RLUT_output2_6':(0x2013071C,6*66), 'C040_26':(0x2012C0F4,26*48),
 'C080_29':(0x2012C5D4,29*96), 'matrix8':(0x2012D0C0,8*28),
 'tail_nodes6':(0x2012D1A0,6*14), 'tail_gains6':(0x2012D1F4,6*9),
 'toning6_C004':(0x2012D0B4,12),
 'WDR_initial278':(0x2014322C,278*4),
}

def main():
    j=m.Image('jlaunch3');result={}
    for key,(va,size) in BANKS.items():
        raw=j.read(va,size)
        locations={}
        for stem in m.NAMES:
            im=m.Image(stem+'3')
            found=c.hits(im.data,raw)
            locations[im.name]=dict(matches=len(found),locations=[dict(file_offset=hex(o),vma=hex(c.vma(im,o))) for o in found[:20]],
                                   truncated=len(found)>20)
        result[key]=dict(jlaunch_vma=hex(va),size=size,sha256=m.sha(raw),images=locations,
                         limitation='Exact full-bank byte search only; a miss is not an absent capability.')
        print(key,{n:r['matches'] for n,r in locations.items()})
    # All non-A12 bank controls are extracted, without assuming any table axes.
    m.save(m.EVIDENCE/'bank-exact-matches.json',result)
    # Shapes of initialized WDR payload by the independently verified driver groups.
    import json
    layout=json.loads((m.ROOT/'research/isp_pipeline/register_layouts.json').read_text())[21]
    words=list(struct.unpack('>278I',j.read(0x2014322C,1112)))
    cursor=0;groups=[]
    for group in layout['write_groups']:
        n=group['count'];v=words[cursor:cursor+n]
        groups.append(dict(group=group,mirror_offset=hex(cursor*4),words=[hex(x) for x in v],
                           halfwords=[y for x in v for y in (x>>16,x&65535)]))
        cursor+=n
    assert cursor==278
    m.save(m.EVIDENCE/'wdr-initial-groups.json',dict(vma='0x2014322C',groups=groups))

if __name__=='__main__':main()
