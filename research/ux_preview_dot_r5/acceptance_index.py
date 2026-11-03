"""Bind successful native groups to their actual tested DAT, leaving stop gates open."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,save,file_sha
old=file_sha(OUT/'implementation-candidate/GXRCE.DAT')
new=json.loads((OUT/'identity.json').read_text())['120']['dat']
rows=[]
def add(name,dat,unit,kind):
 p=OUT/name;x=json.loads(p.read_text());assert x['status'].startswith('PASS'),(name,x['status'])
 actual=x.get('dat_sha256',x.get('dat'))
 if actual:assert actual==dat,(name,actual,dat)
 rows.append(dict(file=name,sha256=file_sha(p),unit=unit,kind=kind,tested_dat=dat,status=x['status']))
for unit in ('50mm','28mm','mount'):
 suite=json.loads((OUT/('remaining-suite-'+unit+'.json')).read_text())
 assert suite['status']=='PASS' and len(suite['commands'])==21 and all(x['returncode']==0 for x in suite['commands'])
 add('native/matrix-complete-'+unit+'.json',old,unit,'implementation matrix')
 for group in ('h07-all','fn2-all-points','fn2-retain','fn2-failures','fn2-step-counts','ah','exits','confirm-paths','latch-paths'):
  add('native/'+group+'-'+unit+'.json',old,unit,group)
 h=json.loads((OUT/'native'/('h07-all-'+unit+'.json')).read_text())
 assert len(h['cases'])==(32 if unit=='28mm' else 28)
 assert all(x['RPC']==x['W']==x['preview']==0 for x in h['cases'])
 f=json.loads((OUT/'native'/('fn2-all-points-'+unit+'.json')).read_text())
 assert len(f['points'])==43 and f['reference']['RPC']==42
 assert all(x['late_writes']==0 and len(x['complete'])==1 for x in f['points'])
 add('native/names-'+unit+'.json',new,unit,'named candidate glyph submissions')
 named=json.loads((OUT/'native'/('names-'+unit+'.json')).read_text());assert named['all_eight_drawn']
 add('native/persistent-'+unit+'.json',old,unit,'continued failure notice')
save('acceptance.json',dict(status='NOT_ACCEPTED',implementation_dat=old,named_dat=new,code_binding='name-code-binding.json',records=rows,
 open_gates=['Fixed H07 native close no-yield requirement','New confirmed value in every locked H07 state','Complete A/B/C per-PC and recursive closure'],
 limits=['The complete interaction matrix was executed on the implementation candidate. The final short-name candidate has identical engine/ELF/effective colour bytes and separate three-unit glyph-submission checks, not a second complete interaction matrix.', 'Fn2 exhaustive communication-point switching covers contrast +1 on slot 05. Other parameters have step-by-step live/row consistency and wire counts; their every-point switch matrices were not expanded after the stop.', 'All evidence is host/static/native instruction execution with named hardware and OS models. No camera, card, physical display or power-cycle acceptance.']))
print('PASS evidence index',len(rows),'records; overall candidate NOT_ACCEPTED',flush=True)
