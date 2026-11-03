"""Real save/readback, a modelled cold power cycle, then H08 retire.

Only the device file dictionary and the actual prior 4096-byte settings input
survive reboot. Native UI state and root are rebuilt by image instructions.
The unit RPC overlay is reset to genuine ROM at reboot, as a device boundary.
"""
import hashlib
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,save as original_save
exec(compile((HERE/"adversarial.py").read_text().split('selected=sys.argv')[0],str(HERE/"adversarial.py"),"exec"),globals())
from file_edge import Files
def save(name,value):original_save("power-"+name,value)

rec=dict(name="boot1_save01",unit="50mm",steps=[]);reports.append(rec)
h,p,w=boot();files=Files(h,p)
for label,fn in (OPEN,ONE,OK,MENU):step(rec,label,h,p,w,lambda fn=fn:fn(h,p,w))
rec["final"]=snapshot(h,p);rec["file_io"]=files.log
rec["files"]={name:dict(bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest()) for name,blob in files.contents.items()}
golden=rec["final"]["deep_sha256"]
settings=h.b.read(h.settings,4096)
assert any(name.startswith("/IROM/L50") for name in files.contents),rec["files"]
for name,blob in files.contents.items():
    if name.startswith("/IROM/L50"):(HERE/(Path(name).name+".device-model")).write_bytes(blob)

rec=dict(name="boot2_remember01_h08_fault",unit="50mm",steps=[]);reports.append(rec)
h=RealGetterHarness()
h.b.write(h.settings,settings)  # Actual prior native S, modelled nonvolatile input.
h.quiet_trace=True
h.prepare_menu();h.leave_other_list()
p=pe.Product(h,"50mm",2,1,1)
h.b.breakpoints.pop(0x2009359c,None)
assert fr.native(h,0x200935b4,(1,))["ok"]
w=fr.Watch(h);files2=Files(h,p,files.contents)
rec["cold_before_H01"]=snapshot(h,p)
rec["persisted_settings_sha256"]=hashlib.sha256(settings).hexdigest()
step(rec,"first H01 with real saved GXLS",h,p,w,lambda:publish(h,p,w))
rec["remember_reapplied_full01"]=snapshot(h,p)["deep_sha256"]==golden
for label,fn in (ONE,("negative: corrupt snapshot after remembered 01",corrupt_ui),SCROLL,MENU):
    step(rec,label,h,p,w,lambda fn=fn:fn(h,p,w))
rec["final"]=snapshot(h,p);rec["file_io"]=files2.log
save("adversarial.json",reports)
if rec["remember_reapplied_full01"] and rec["final"]["mode"]!=1 and rec["final"]["deep_sha256"]==golden:
    print("COUNTEREXAMPLE_CONFIRMED remembered 01 deep rows kept, native mode replaced Standard",flush=True)
else:print("NO_COUNTEREXAMPLE",rec["remember_reapplied_full01"],rec["final"]["mode"],flush=True)
