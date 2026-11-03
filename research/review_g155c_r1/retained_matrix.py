"""Audit actual final-SHA first-menu snapshots, including cached ten controls."""
import json
import argparse
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--name',default='retained-matrix')
args=parser.parse_args()

# Reuse the frozen complete-row checker, independently bind its inputs and
# inspect the cache that supplies the first visible controls.
sys.path.insert(0,str(C.PRIOR))
C.snapshot(C.PRIOR/'local/p1final-mount-cold1-boot_run.pkl.z')
import reference
reference.HERE=C.HERE
reference.TMP=C.TMP/'matrix-reference'
import accept
engine=C.ROOT/'firmware/engine_v67_g155c'
elf=engine/'candidate/local/boot-on/engine.elf'
offsets=C.RT.layout(engine)
syms=C.RT.symbols(elf)
rows=[]
for name in ('p1final-mount','p1final-user','p1final-look','p1final-50','p1final-28'):
    source=C.PRIOR/'local'/(name+'-menu1-first-menu.pkl.z')
    saved=C.snapshot(source)
    base,binding=C.bind(saved,mutable=[(syms['t_seen'],4)])
    result,target=accept.check(source,engine,elf)
    S=C.word(saved,0x200c0dac)
    record=C.mem(saved,S+0xfd4,40)
    levels=record[8:28]
    code=record[5]
    if 1<=code<=8:
        cached=C.mem(saved,base+syms['n']+offsets['n.values']+20*(code-1),20)
    elif code>=0x80:
        cached=C.mem(saved,base+syms['n']+offsets['n.ui.saved']+20*(code-0x80),20)
    else:
        cached=C.mem(saved,base+syms['n']+offsets['n.ui.levels'],20)
    assert cached==levels and C.mem(saved,base+syms['n']+offsets['n.ui.levels'],20)==levels
    assert C.word(saved,0x200547ec)==2
    rows.append(dict(case=name,binding=binding,complete_colour_check=result,
                     cached_levels=list(struct.unpack('>10h',cached)),all_ten_cached_controls_equal_record=True,
                     evidence_type='retained final-SHA artifact audit, not a new UI/cold run'))
C.save(args.name,dict(status='PASS',rows=rows,checker=C.file_info(C.PRIOR/'accept.py'),
                             boundary='Uses declared settings-read replay snapshots. Owner NAND persistence is a separate known fact.'))
