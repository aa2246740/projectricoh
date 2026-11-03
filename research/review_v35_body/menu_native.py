"""Native state-9 MENU callbacks, with read-only table-derived navigation."""
import struct
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,save as original_save
exec(compile((HERE/"adversarial.py").read_text().split('selected=sys.argv')[0],str(HERE/"adversarial.py"),"exec"),globals())
def save(name,value):original_save("menu-native-"+name,value)
def context(h):
    return dict(state=fr.u32(h,0x205d9c00),item=fr.u32(h,0x205d9bf8),
                main_bytes=h.b.read(0x2022f390,80).hex(),main_row=fr.u8(h,0x205d9e08))
rec=dict(name="vi_native_MENU",unit="50mm",steps=[]);reports.append(rec)
h,p,w=boot()
for label,fn in (OPEN,ONE,OK,MENU):step(rec,label,h,p,w,lambda fn=fn:fn(h,p,w))
result=step(rec,"native ADJ MENU state transition",h,p,w,lambda:fr.native(h,0x202bd724,(0x29,)))
rec["steps"][-1]["menu"]=context(h)
def event(key):
    state=fr.u32(h,0x205d9c00);table=fr.u32(h,0x2037f658+4*state)
    for i in range(128):
        k,pre,post=struct.unpack(">3I",h.b.read(table+12*i,12))
        if k==key:break
        if not k:return dict(ok=False,reason="event absent",state=state,key=key)
    else:return dict(ok=False,reason="event table limit")
    out=[]
    for entry in (pre,post):
        done=fr.native(h,entry,(key,),steps=2000000)
        out.append(dict(entry=hex(entry),result=done,menu=context(h)))
        if not done["ok"]:return dict(ok=False,state=state,key=key,callbacks=out)
    return dict(ok=True,state=state,key=key,callbacks=out)
result=step(rec,"native MENU state entry",h,p,w,lambda:event(1))
rec["steps"][-1]["menu"]=context(h)
if result["ok"]:
    for i in range(40):
        if fr.u32(h,0x205d9bf8)==8:break
        result=step(rec,f'native MENU cursor down {i+1}',h,p,w,lambda:event(0x20))
        rec["steps"][-1]["menu"]=context(h)
        if not result["ok"]:break
    if result["ok"] and fr.u32(h,0x205d9bf8)==8:
        result=step(rec,"native MENU open Image",h,p,w,lambda:event(0x23))
        rec["steps"][-1]["menu"]=context(h)
if not result["ok"]:rec["blocked"]=result
rec["final"]=snapshot(h,p)
save("adversarial.json",reports)
