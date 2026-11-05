"""Use a completed native sweep's actual Acros S record for fresh reference MAIN."""
from pathlib import Path
import argparse
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
p=argparse.ArgumentParser();p.add_argument('--dataset',choices=('control','model'),required=True);p.add_argument('--profile',choices=('test','release'),required=True);p.add_argument('--unit',choices=C.UNITS,required=True);p.add_argument('--source-run',required=True);a=p.parse_args()
C.setup();C.compute_gate('reference-Acros-input');C.DATASET=a.dataset
source=C.LOCAL/'runs'/a.source_run;result=json.loads((source/'result.json').read_text());raw=C.artifact(a.profile,a.dataset)['dat'].read_bytes()
assert result['status']=='OBSERVED' and result['actual_backend']=='native' and result['dat_sha256']==C.sha(raw)
sample=next(r for r in result['samples'] if r['name']=='Acros');assert sample['full_40_equal'] and sample['unit_readback']['complete_552_equal']
block=(source/('look-'+str(sample['ordinal'])+'-S.bin')).read_bytes();assert len(block)==4096
assert block[0xfd4:0xffc]==bytes.fromhex(sample['state']['record']) and block[0xfd4+5]==64+sample['index']
assert block[0x36e]==1 and block[0x6dd:0x6df]==b'\x09\x09' and not block[8]
fixed=block[:4092]+(sum(struct.unpack('>2046H',block[:4092]))&0xffffffff).to_bytes(4,'big')
folder=C.LOCAL/'reference-fixtures';folder.mkdir(exist_ok=True);stem=a.dataset+'-'+a.profile+'-'+a.unit
(folder/(stem+'-S.bin')).write_bytes(fixed)
(folder/(stem+'-expected552.bin')).write_bytes(C.D.expand_effect(raw,sample['index']))
C.save(folder/(stem+'.json'),dict(status='PASS',DAT_sha256=C.sha(raw),source_run=a.source_run,source_S_sha256=C.sha(block),reference_S_sha256=C.sha(fixed),changed_offsets=[i for i,(x,y) in enumerate(zip(block,fixed)) if x!=y],record_preserved=True,index=sample['index'],source_full_552_equal=True,boundary='Logical S only, checksum-only twin. New MAIN, no CPU/device checkpoint or shutdown claim.'))
print(json.dumps(dict(status='PASS',dataset=a.dataset,profile=a.profile,unit=a.unit)))
