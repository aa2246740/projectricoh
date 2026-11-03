"""Audit every recorded camera-file counter; unit W is a separate domain."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,save,file_sha
files=[];observations=0;counts={'create':0,'write':0,'rename':0,'delete':0,'write_open':0};failed=[]
def walk(x,source):
 global observations
 if isinstance(x,dict):
  for key,value in x.items():
   if key=='file_mutations' and isinstance(value,dict):
    assert set(value)<=set(counts),(source,key)
    for op,count in value.items():
     assert isinstance(count,int) and count>=0
     observations+=1;counts[op]+=count
     if count:failed.append(dict(file=source,operation=op,count=count))
   else:walk(value,source)
 elif isinstance(x,list):
  for value in x:walk(value,source)
for p in sorted((OUT/'native').rglob('*.json')):
 walk(json.loads(p.read_text()),str(p.relative_to(OUT)))
 files.append(dict(path=str(p.relative_to(OUT)),sha256=file_sha(p)))
gates=json.loads((OUT/'machine-gates.json').read_text());assert not any(gates['zero_file_mutations'].values())
assert gates['artifacts']['dat']==json.loads((OUT/'identity.json').read_text())['120']['dat']
assert not failed and not any(counts.values()),failed
save('zero-file-write-audit.json',dict(status='PASS',native_files=len(files),counter_observations=observations,totals=counts,files=files,machine_gate='machine-gates.json',static_calls='final-file-calls.json',scope='Camera/IROM/card file APIs in the recorded model sessions; not host build artifact writes and not the unit RPC W commands.'))
print('PASS zero camera-file changes:',len(files),'native records;',observations,'counter observations',flush=True)
