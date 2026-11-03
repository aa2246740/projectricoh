"""Required RV_CHECK_UI fault, first observed by a real cursor H08."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,save as original_save
exec(compile((HERE/"adversarial.py").read_text().split('selected=sys.argv')[0],str(HERE/"adversarial.py"),"exec"),globals())
def save(name,value):original_save("h08-retire-"+name,value)
run("ui_corruption_first_seen_by_H08",[OPEN,ONE,OK,REOPEN,ONE,
    ("negative: corrupt detached snapshot",corrupt_ui),SCROLL,MENU])
save("adversarial.json",reports)
last=reports[-1]
if "final" in last:
    assert last["final"]["root"]["state"]==6
    assert last["final"]["native_visits"]["H08_native"]>0
    assert last["final"]["mode"]!=1
    assert last["final"]["deep_sha256"]==last["steps"][2]["after"]["deep_sha256"]
    print("COUNTEREXAMPLE_CONFIRMED native mode replaced selected recipe, deep rows unchanged",flush=True)
