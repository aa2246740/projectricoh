"""First published ADJ list: UI fault arrives on scroll, before first OK."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,save as original_save
exec(compile((HERE/"adversarial.py").read_text().split('selected=sys.argv')[0],str(HERE/"adversarial.py"),"exec"),globals())
def save(name,value):original_save("h08-first-"+name,value)
run("first_publish_ui_fault_H08",[OPEN,ONE,("negative: corrupt snapshot",corrupt_ui),SCROLL,OK,MENU])
save("adversarial.json",reports)
last=reports[-1]
print("FIRST_FAULT_RESULT",last.get("final"),flush=True)

assert last["final"]["mode"]==1 and last["final"]["native_visits"]["H08_native"]==0
assert last["final"]["root"]["state"]==6
