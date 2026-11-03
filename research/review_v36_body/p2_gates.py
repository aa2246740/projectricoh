"""Separately exercise both cold readiness gates, including MOUNT identity."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,ROOT,save as original_save
exec(compile((HERE/"adversarial.py").read_text().split('selected=sys.argv')[0],str(HERE/"adversarial.py"),"exec"),globals())
def save(name,value):original_save("p2-"+name,value)
pe.UNITS["mount"]=(ROOT/"artifacts/firmware/gxr-1.51/l08firm3","0a4dff6d3be9b9a9b56dfcbd98a2df59efcb31f7d4eaca6b0c3fbdb1641fde44",2)
for unit,ready,link in (("50mm",0,1),("50mm",1,0),("28mm",0,1),("mount",0,1),("mount",0,0)):
    h,p,w,rec=run(f'{unit}_ready{ready}_link{link}',[OPEN,MENU,REOPEN],unit=unit,ready=ready,link=link)
    rec["files_opened"]=p.files.log
    assert not p.files.log and not p.rpc.log
    assert rec["final"]["root"]["state"]==0 and rec["final"]["root"]["flags"]==2
    assert rec["final"]["ui"]["rows"]==7
save("adversarial.json",reports)
print("PASS both gates keep native, no attempted latch, no file IO/RPC",flush=True)
