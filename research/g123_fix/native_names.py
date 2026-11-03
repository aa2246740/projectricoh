"""Observe real list glyph submissions for every short name and its width."""
from pathlib import Path
import json,struct,sys,traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_cases as nc
from common import ROOT,OUT,save,sha,file_sha
unit=sys.argv[1];nc.n.configure(unit,'short-names')
ux,m,fr=nc.ux,nc.m,nc.fr
budget=json.loads((ROOT/'research/three_module_audit_r1/local/name_widths.json').read_text())
names=['01 GRPos','02 GRNeg','03 HC BW','04 Std','05 F-CC','06 F-CN','07 L-Chr','08 L-Viv']
known={}
for row in budget['rows']:
 if row['name'] not in names:continue
 for language in row['languages']:
  encoded=b''.join(struct.pack('>H',x) for x in language['glyphs'])+b'\0'
  known[encoded]=dict(name=row['name'],width=language['width_with_edge_max'],language=language['setting'],glyphs=language['glyphs'])
h,p,w=m.boot(unit);ascii_calls=[];draws=[];seen=set();other=[]
def ascii_record(b):
 source,length,destination,language=b.core.r[4:8]
 text=b.read(source,length).decode('ascii')
 ascii_calls.append(dict(text=text,bytes=length,source=hex(source),destination=hex(destination),language=language))
 return False
def draw_record(b):
 style=b.core.r[5];x=h.u(style,2);y=h.u(style+2,2);kind=h.u(style+4,1);text=h.u(style+8)
 if kind==8 and text:
  raw=bytearray()
  for at in range(0,96,2):
   if h.u(text+at,1)==0:raw+=b'\0';break
   raw+=b.read(text+at,2)
  identity=known.get(bytes(raw))
  if identity:
   right=640 if h.u(0x205d444c) else 320
   row=dict(identity,x=x,y=y,right=right,edge=x+identity['width'],kind=kind,encoded=bytes(raw).hex(),style=b.read(style,12).hex(),writer=hex(b.core.r[14]))
   row['next_column']=219;row['conservative_width_limit']=101
   assert x==38 and identity['width']<=101 and x+identity['width']<=min(219,right) and 0<=y and y+38<=480,row
   draws.append(row);seen.add(identity['name'])
  elif len(other)<8:other.append(dict(x=x,y=y,kind=kind,encoded=bytes(raw).hex(),style=b.read(style,12).hex()))
 return False
h.b.add_breakpoint(0x201d73e0,ascii_record)
h.b.breakpoints[0x201d7170].insert(0,draw_record)
r=dict(unit=unit,dat=sha(m.DAT.read_bytes()),body=nc.v.BODY_SHA)
try:
 m.published(h,p,w)
 assert seen==set(names),(sorted(seen),other)
 assert set(x['text'] for x in ascii_calls)>=set(names)
 r.update(status='PASS',names=names,ascii_calls=ascii_calls,draws=draws,all_eight_drawn=True,native_ui_hand_seeded=False,getter_fixed_return_stub_removed=True,file_mutations=m.no_writes(p),
  evidence_scope='The exact native constructor, converters and row renderer reach each glyph submission with matching encoded text and real x/y. Font metric advances come from the audited official resource. Pixel rasterization, display hardware and RTOS remain modeled.')
 print('PASS native short names',unit,'all eight drawn; largest edge',max(x['edge'] for x in draws),'right',min(x['right'] for x in draws),flush=True)
except BaseException:
 r.update(status='FAIL',error=traceback.format_exc(),ascii_calls=ascii_calls,draws=draws,other=other);raise
finally:save('local/native/names-'+unit+'.json',r)
