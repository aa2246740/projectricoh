"""Save 02 with real instructions; cold boot preserves only actual S/files."""
import hashlib
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,save as original_save
exec(compile((HERE/"adversarial.py").read_text().split('selected=sys.argv')[0],str(HERE/"adversarial.py"),"exec"),globals())
from file_edge import Files
def save(name,value):original_save("power02-"+name,value)
rec=dict(name="boot1_save02",unit="50mm",steps=[]);reports.append(rec)
h,p,w=boot();files=Files(h,p)
for label,fn in (OPEN,TWO,OK,MENU):step(rec,label,h,p,w,lambda fn=fn:fn(h,p,w))
rec["final"]=snapshot(h,p);rec["file_io"]=files.log
settings=h.b.read(h.settings,4096);golden=rec["final"]["deep_sha256"]
rec["preference_slots"]={name:blob[16] for name,blob in files.contents.items() if name.startswith("/IROM/L50")}
assert 2 in rec["preference_slots"].values()
rec=dict(name="boot2_last02",unit="50mm",steps=[]);reports.append(rec)
h=RealGetterHarness();h.b.write(h.settings,settings);h.quiet_trace=True;h.prepare_menu();h.leave_other_list()
p=pe.Product(h,"50mm",2,1,1);h.b.breakpoints.pop(0x2009359c,None)
assert fr.native(h,0x200935b4,(1,))["ok"]
w=fr.Watch(h);files2=Files(h,p,files.contents)
rec["cold_before_H01"]=snapshot(h,p)
step(rec,"first H01 with saved02",h,p,w,lambda:publish(h,p,w))
for label,fn in (OK,MENU):step(rec,label,h,p,w,lambda fn=fn:fn(h,p,w))
rec["final"]=snapshot(h,p);rec["file_io"]=files2.log
rec["same_full02_after_OK"]=rec["final"]["deep_sha256"]==golden
save("adversarial.json",reports)
assert rec["steps"][0]["after"]["ui"]["cursor"]==2
assert rec["cold_before_H01"]["deep_cells"]==0 and rec["cold_before_H01"]["mode"]==1
assert rec["steps"][0]["after"]["deep_cells"]==0
assert rec["same_full02_after_OK"]
print("PASS remembered cursor02; pure04 before OK; full02 after OK",flush=True)
