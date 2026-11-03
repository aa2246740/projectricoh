"""Independently compare renamed data with gen 117 at every row and identity."""
from pathlib import Path
import json,struct,sys,zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,save,sha,load
prior=load(ROOT/'research/review_g118/artifacts.py','quality_row_expander')
u32=lambda b,o:int.from_bytes(b[o:o+4],'big')
NAMES=['01 GRPos','02 GRNeg','03 HC BW','04 Std','05 F-CC','06 F-CN','07 L-Chr','08 L-Viv']
ROWS=((20,62),(82,33),(115,96),(216,56),(284,62),(346,33),(379,66),(456,62),(518,33))
def compare(baseline,old,new):
 a,b,c=map(prior.expand,(baseline,old,new));assert a==b
 output=[];changed=[]
 for index,(x,y) in enumerate(zip(a,c)):
  for key in ('map','pin','metadata'):assert x[key]==y[key],(index,key)
  records=[]
  for slot in range(16):
   before=x['records'][slot*64:(slot+1)*64];after=y['records'][slot*64:(slot+1)*64]
   assert zlib.crc32(after[:60])==u32(after,60)
   if slot<8:
    assert after[4:4+after[2]].decode('ascii')==NAMES[slot]
    assert before[:2]==after[:2] and before[3:4]==after[3:4] and before[36:60]==after[36:60]
   else:assert before==after
   e0,e1=x['entries'][slot],y['entries'][slot]
   assert e0[:4]==e1[:4] and e0[8:]==e1[8:],(index,slot,'entry colour bytes')
   if slot<8:
    identity=after[2:3]+after[4:36]+after[3:4]+after[36:51]
    assert zlib.crc32(identity)==u32(e1,4)
   rows=[]
   for off,n in ROWS:
    assert e0[off:off+n]==e1[off:off+n]
    rows.append(dict(offset=off,bytes=n,sha256=sha(e1[off:off+n])))
   records.append(dict(slot=slot+1,record_changed=before!=after,entry_changed=e0!=e1,rows=rows,control_sha256=sha(e1[445:447])))
   if before!=after:changed.append([index,slot+1])
  output.append(dict(unit=('jlaunch','qlaunch','l08firm')[index],records=records,map_sha256=sha(y['map']),pin_sha256=sha(y['pin'])))
 assert len(changed)==18
 # Only record name/length/CRC, bank CRC and descriptor identity/CRC may differ
 # from the tested implementation candidate. Header and content CRCs rebind.
 assert len(old)==len(new)
 allowed=set(range(20,28));directory=u32(new,156)
 for index in range(3):
  d=directory+64*index;bank=u32(new,d+16);table=u32(new,d+20)
  allowed.update(range(bank+24,bank+32));allowed.update(range(table+12,table+16))
  for slot in range(16):
   record=bank+32+slot*64
   allowed.add(record+2);allowed.update(range(record+4,record+36));allowed.update(range(record+60,record+64))
  for j in range(new[d+30]):allowed.update(range(table+16+j*20+4,table+16+j*20+8))
 delta=[i for i,(x,y) in enumerate(zip(old,new)) if x!=y]
 assert all(i in allowed for i in delta),[hex(i) for i in delta if i not in allowed][:20]
 result=dict(status='PASS',baseline=sha(baseline),implementation_candidate=sha(old),named_candidate=sha(new),maps=3,pins=3,metadata=48,expanded=48,primary_rows=216,expanded_rows=432,names_changed=18,changed_record_slots=changed,changed_bytes=len(delta),units=output,
  scope='All nine row bodies, their CRC fields, T/control, maps, metadata and pins remain byte-identical to gen 117. Entry changes are limited to identity CRC; record changes are limited to names, length and record CRC.')
 save('data-name-equality.json',result)
 return result
if __name__=='__main__':
 compare((ROOT/'firmware/package_v36_g117/SD_ROOT/GXRCE.DAT').read_bytes(),(OUT/'implementation-candidate/GXRCE.DAT').read_bytes(),(ROOT/'firmware/engine_v42_ux/candidate/local/full-r13/GXRCE.DAT').read_bytes())
 print('PASS renamed records, identities and 216 primary colour rows against gen 117',flush=True)
