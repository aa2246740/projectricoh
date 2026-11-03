"""Both native keys, wrapping, post-OK arrows, and an H08 up-key fault."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,save as original_save
exec(compile((HERE/"adversarial.py").read_text().split('selected=sys.argv')[0],str(HERE/"adversarial.py"),"exec"),globals())
def save(name,value):original_save("scroll-both-"+name,value)
h,p,w=boot();rec=dict(name="both_keys_same_boot",steps=[]);reports.append(rec)
step(rec,"open",h,p,w,lambda:publish(h,p,w))
for key in (0x20,0x1f):
    for i in range(10):
        step(rec,f'key {key:#x} #{i+1}',h,p,w,lambda key=key:fr.move_key(h,key))
step(rec,"01",h,p,w,lambda:moves_to(h,1))
step(rec,"OK",h,p,w,lambda:fr.press(h,0x23))
for key in (0x20,0x1f):step(rec,f'closed key {key:#x}',h,p,w,lambda key=key:fr.move_key(h,key))
assert pe.settings_byte(h)[1]==1
step(rec,"MENU",h,p,w,lambda:fr.press(h,0x29))
rec["positive_final"]=snapshot(h,p)
step(rec,"reopen",h,p,w,lambda:reopen(h,p,w))
step(rec,"negative: corrupt snapshot",h,p,w,lambda:corrupt_ui(h,p,w))
step(rec,"fault seen by key 0x1f",h,p,w,lambda:fr.move_key(h,0x1f))
rec["final"]=snapshot(h,p)
save("adversarial.json",reports)
assert rec["positive_final"]["native_visits"]["H08_native"]==0
assert rec["final"]["mode"]==5 and rec["final"]["root"]["state"]==6
print("PASS both keys and wraps; COUNTEREXAMPLE on up key too",flush=True)
