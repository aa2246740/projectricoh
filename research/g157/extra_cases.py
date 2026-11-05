"""Generate explicit BOOT fixtures and append cold-start diagnostic checks."""
from pathlib import Path
import json
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import records as R
C.setup();C.compute_gate('BOOT-fixtures')
folder=C.LOCAL/'boot-fixtures';folder.mkdir(exist_ok=True)
default=C.ROOT/'research/field_gate_r1/local/inputs-v3-auto/g156-test-A.bin'
seed=bytearray(default.read_bytes());assert len(seed)==4096
seed[0xfd4:0xffc]=bytes(40)
def seal(block):
    block[-4:]=(sum(struct.unpack('>2046H',block[:4092]))&0xffffffff).to_bytes(4,'big')
    return bytes(block)
(folder/'empty-S.bin').write_bytes(seal(seed))
tasks_path=C.LOCAL/'r1-work.json';tasks=json.loads(tasks_path.read_text());added=[]
raw=C.artifact('test','model')['dat'].read_bytes();area,_=C.D.effect_area(raw)
for u,unit in enumerate(C.UNITS):
    index=next(i for i in range(C.D.u16(raw,area+10)) if raw[area+32+32*i+18]>>u&1 and raw[area+32+32*i+20:area+64+32*i].split(b'\0')[0]==b'Acros')
    ext=C.D.u32(raw,204)+1408;first_user_slot=raw[ext+64+24*64]
    # The fixed user table offset comes from the validated format header.
    user_offset=C.D.u32(raw,ext+36);first_user_slot=raw[ext+user_offset]
    for name,code,expected in (('hcbw',3,C.D.expand(raw,u,3)),('acros',64+index,C.D.expand_effect(raw,index)),('user1',128,C.D.expand(raw,u,first_user_slot))):
        record=b'GXR2'+bytes((3,code,u,1))+struct.pack('>10h',100,0,0,0,0,0,0,0,0,0)+raw[20:28]
        record+=zlib.crc32(record).to_bytes(4,'big');block=bytearray(seed);block[0xfd4:0xffc]=record
        source=folder/(unit+'-'+name+'-S.bin');source.write_bytes(seal(block))
        target=folder/(unit+'-'+name+'-expected552.bin');target.write_bytes(expected)
        label=f'r2-model-test-{unit}-BOOT-{name}'
        args=['--dataset','model','--version','test','--unit',unit,'--backend','native','--label',label,'--action','menu','--settings',str(source),'--expected',str(target)]
        added.append(dict(id=label,script='run.py',args=args,needs=[],log=str(C.LOCAL/'logs'/(label+'.log'))))
hc=folder/'mount-hcbw-S.bin'
for task in tasks:
    if task['script']=='run.py' and '--challenge' in task['args']:
        task['args']+=['--settings',str(hc)]
        task.setdefault('needs',[]).append('boot-fixtures')
for challenge in ('boot-both','no-dispatch'):
    label='r2-model-test-mount-'+challenge+'-reference'
    args=['--dataset','model','--version','test','--unit','mount','--backend','reference','--label',label,'--action','menu','--challenge',challenge,'--settings',str(hc)]
    added.append(dict(id=label,script='run.py',args=args,needs=[],log=str(C.LOCAL/'logs'/(label+'.log'))))
known={t['id'] for t in tasks}
tasks.extend(t for t in added if t['id'] not in known)
tmp=tasks_path.with_suffix('.tmp');C.save(tmp,tasks);tmp.replace(tasks_path)
C.save(folder/'manifest.json',dict(seed_sha256=C.sha(default.read_bytes()),DAT_sha256=C.sha(raw),files=[dict(file=str(f.relative_to(C.ROOT)),sha256=C.sha(f.read_bytes())) for f in folder.iterdir() if f.is_file() and f.name!='manifest.json']))
print(json.dumps(dict(status='PASS',BOOT_cases=9,reference_diagnostics=2)))
