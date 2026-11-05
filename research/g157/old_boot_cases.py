"""Declare a checksum-valid S with an old g156 binding for fresh MAIN refusal."""
from pathlib import Path
import json
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import records as R
C.setup();C.compute_gate('old-g156-cold-fixtures')
old=R.frozen(Path('firmware/package_v310_g156_test/GXRCE.DAT'))
record=b'GXR2'+bytes((3,3,2,1))+struct.pack('>10h',100,0,0,0,0,0,0,0,0,0)+old[20:28]
record+=zlib.crc32(record).to_bytes(4,'big')
folder=C.LOCAL/'boot-fixtures';block=bytearray((folder/'empty-S.bin').read_bytes());block[0xfd4:0xffc]=record
block[-4:]=(sum(struct.unpack('>2046H',block[:4092]))&0xffffffff).to_bytes(4,'big')
file=folder/'old-g156-S.bin';file.write_bytes(block)
queue=C.LOCAL/'r1-work.json';tasks=json.loads(queue.read_text());known={t['id'] for t in tasks}
for profile in ('test','release'):
    label='r2-model-'+profile+'-mount-old-g156'
    if label in known:continue
    args=['--dataset','model','--version',profile,'--unit','mount','--backend','native','--label',label,'--action','menu','--settings',str(file)]
    tasks.append(dict(id=label,script='run.py',args=args,log=str(C.LOCAL/'logs'/(label+'.log'))))
tmp=queue.with_suffix('.tmp');C.save(tmp,tasks);tmp.replace(queue)
print(json.dumps(dict(status='PASS',old_DAT_sha256=C.sha(old),record=record.hex())))
