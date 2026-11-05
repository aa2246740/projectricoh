"""Declare Vivid in logical S before native initialization, retaining saved intent."""
from pathlib import Path
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();C.compute_gate('persistent-Vivid-input')
queue=C.LOCAL/'r1-work.json';tasks=json.loads(queue.read_text());known={t['id'] for t in tasks}
for old,new in (('r6-model-test-mount-boot-vivid-native','r7-model-test-mount-persistent-vivid'),('r6-model-test-mount-remembered-acros-vivid','r7-model-test-mount-remembered-persistent-vivid')):
    prior=next(t for t in tasks if t['id']==old);args=list(prior['args'])
    source=Path(args[args.index('--settings')+1]);block=bytearray(source.read_bytes());record=bytes(block[0xfd4:0xffc]);block[0x36e]=2
    block[-4:]=(sum(struct.unpack('>2046H',block[:4092]))&0xffffffff).to_bytes(4,'big')
    target=C.LOCAL/'boot-fixtures'/(new+'-S.bin');target.write_bytes(block);assert bytes(block[0xfd4:0xffc])==record
    args[args.index('--settings')+1]=str(target);args[args.index('--label')+1]=new;args[args.index('--challenge')+1]='none';args+=['--require-vivid']
    if new not in known:tasks.insert(2,dict(id=new,script='run.py',args=args,log=str(C.LOCAL/'logs'/(new+'.log'))))
tmp=queue.with_suffix('.tmp');C.save(tmp,tasks);tmp.replace(queue)
print(json.dumps(dict(status='PASS',fixtures=2,record_preserved=True,source='declared logical S before MAIN')))
