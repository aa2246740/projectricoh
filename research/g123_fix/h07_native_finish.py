"""Observe the frozen native H07 close after the RAM-only recipe return."""
from pathlib import Path
import json,sys,traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_cases as nc
from common import OUT,save,sha
unit=sys.argv[1];nc.n.configure(unit,'h07-native-finish');ux,m,fr=nc.ux,nc.m,nc.fr
h,p,w=m.boot(unit)
if len(sys.argv)>2:
 h.run_slice(0x2030e8cc,0x2030e8e4)
 h.parent()
m.published(h,p,w);context=nc.stamp(h,p)

def run(r):
 calls=[]
 for address,name in ((0x20052be8,'resident_close'),(0x201c092c,'native_layer'),(0x201d83b0,'layer_transfer'),(0x201d79f4,'layer_show'),(0x201d7b28,'layer_hide'),(0x2005ff88,'ui_service'),(0x2005fdfc,'ui_service_body'),(0x20060300,'ui_state_update')):
  def record(b,name=name):
   calls.append(dict(function=name,pc=hex(b.pc),args=list(b.core.r[4:8]),flags=h.u(0x205a280e,1),kind=h.u(0x205a280f,1),overlay=h.u(0x2037f3bc)))
   return False
  h.b.breakpoints.setdefault(address,[]).insert(0,record)
 # Run the actual layer transfer. Its two wrappers and their calls are no
 # longer represented by the broad graphics submission model.
 h.b.breakpoints[0x201d83b0]=[h.b.breakpoints[0x201d83b0][0]]
 before=ux.snap(h,p);result=fr.press(h,0x23)
 r.update(unit=unit,result=result,before=before,after=ux.snap(h,p),calls=calls,RPC=len(p.rpc.log),
  file_mutations=m.no_writes(p),native_layer_transfer_model_removed=True,dat_sha256=sha(m.DAT.read_bytes()))
 assert result.get('ok'),result
 r['has_ui_service']=any(c['function']=='ui_service' for c in calls)
 print('H07 native close',unit,'UI service',r['has_ui_service'],'calls',calls,flush=True)

nc.case('h07-native-finish-'+unit+('-native-base' if len(sys.argv)>2 else ''),run,context)
