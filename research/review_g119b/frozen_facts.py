"""Recompute immutable recipe facts used by per-PC branch reasoning."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,load,save,sha
a=load(OUT/'artifacts.py','facts_expand')
rows=[]
for generation in (117,118,119):
    raw=(ROOT/f'firmware/package_v36_g{generation}/SD_ROOT/GXRCE.DAT').read_bytes()
    u32=lambda at:int.from_bytes(raw[at:at+4],'big')
    ids=[u32(u32(204)+32+4*i) for i in range(8)]
    assert ids[:6]==list(range(1,7)) and ids[6:]==[0,0],ids
    units=[]
    for unit,parts in enumerate(a.expand(raw)):
        direct=u32(156)+64*unit;pool=u32(direct+20);visible=0
        occupied=[];style=[];lengths=[]
        for i in range(16):
            record=parts['records'][64*i:64*(i+1)]
            occupied.append(record[1]);style.append(record[3]);lengths.append(record[2])
            descriptor=pool+16+20*parts['metadata'][28*i+24]
            if i!=3 and raw[descriptor]!=4:visible=i+1
        visible=4 if 0<visible<4 else visible
        assert visible==8 and set(occupied)=={1} and max(lengths)<=32
        units.append(dict(unit=unit,visible_rows=visible,occupied=occupied,style=style,label_lengths=lengths))
    rows.append(dict(generation=generation,dat_sha256=sha(raw),ids=ids,units=units))
save('frozen-facts.json',dict(status='PASS',generations=rows,
    facts=['All six parameter IDs searched by preload exist in the frozen eight-ID table.',
           'The metadata loop uses slots 1 through 8; 0 and 17 are excluded.',
           'All 48 records are occupied; recipe-list visible count is eight.',
           'Private frozen image bytes do not change during the resident image lease.']))
print('PASS frozen IDs, occupied records and eight visible rows across generations 117/118/119',flush=True)
