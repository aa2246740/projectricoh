"""Skipped BOOT retains non-default Look/user values for explicit OK apply."""
from pathlib import Path
import json
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import math_reference as M
C.setup();C.compute_gate('remembered-manual-fixtures')
folder=C.LOCAL/'boot-fixtures';seed=bytearray((folder/'empty-S.bin').read_bytes())
raw=C.artifact('test','model')['dat'].read_bytes();area,_=C.D.effect_area(raw);u=2
visible=[i for i in range(C.D.u16(raw,area+10)) if raw[area+32+32*i+18]>>u&1]
index=next(i for i in visible if raw[area+32+32*i+20:area+64+32*i].split(b'\0')[0]==b'Acros')
slot,_=M.user_record(raw,1);levels=[100,1]+[0]*8;reference=M.Reference()
queue=C.LOCAL/'r1-work.json';tasks=json.loads(queue.read_text());known={t['id'] for t in tasks}
for name,code,row,base,challenge in (
    ('acros-vivid',64+index,8+visible.index(index),C.D.expand_effect(raw,index),'boot-vivid'),
    ('acros-wb',64+index,8+visible.index(index),C.D.expand_effect(raw,index),'boot-wb'),
    ('user2-wb',129,8+len(visible)+1,C.D.expand(raw,u,slot),'boot-wb'),
):
    expected=reference.compute(raw,u,base,levels)
    target=folder/(name+'-explicit-expected552.bin');target.write_bytes(expected)
    record=b'GXR2'+bytes((3,code,u,1))+struct.pack('>10h',*levels)+raw[20:28];record+=zlib.crc32(record).to_bytes(4,'big')
    block=bytearray(seed);block[0xfd4:0xffc]=record
    block[-4:]=(sum(struct.unpack('>2046H',block[:4092]))&0xffffffff).to_bytes(4,'big')
    source=folder/(name+'-S.bin');source.write_bytes(block)
    label='r2-model-test-mount-remembered-'+name
    if label not in known:
        args=['--dataset','model','--version','test','--unit','mount','--backend','native','--label',label,'--action','session','--session-row',str(row),'--close-key','OK','--challenge',challenge,'--settings',str(source),'--expect-final',str(target)]
        tasks.append(dict(id=label,script='run.py',args=args,log=str(C.LOCAL/'logs'/(label+'.log'))))
tmp=queue.with_suffix('.tmp');C.save(tmp,tasks);tmp.replace(queue)
print(json.dumps(dict(status='PASS',cases=3,nondefault_levels=levels)))
