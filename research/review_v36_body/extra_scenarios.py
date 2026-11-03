"""Additional native panel and retired-native-list runs. Review sources only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,ROOT,save as original_save
definitions=(HERE/"adversarial.py").read_text().split('selected=sys.argv')[0]
exec(compile(definitions,str(HERE/"adversarial.py"),"exec"),globals())
def save(name,value):original_save("extra-"+name,value)

def remove_getter(h,p,w):
    h.b.breakpoints.pop(0x20271fec,None)
    return dict(ok=True,real_getter=True)

run("panel_native",[OPEN,ONE,FN2,SCROLL,SCROLL,SCROLL,SCROLL,SCROLL,SCROLL,OK,MENU])
run("retired_native_move",[OPEN,ONE,OK,REOPEN,("negative: corrupt snapshot",corrupt_ui),OK,
    ("enable real native getter",remove_getter),REOPEN,SCROLL,SCROLL,OK,MENU])

def actual_nested_move(h,p,w):
    pc=p.symbol_pc("ig_apply");injected=[False]
    def enter(b):
        if injected[0]:return False
        injected[0]=True
        context=dict(r=list(b.core.r),pc=b.pc,psw=b.core.psw,cr=dict(b.core.cr),acc=b.core.acc)
        before=snapshot(h,p)
        b.running=False;b.set_reg("r15",0x206efff0)
        done=fr.move_key(h,0x1f)
        after=snapshot(h,p)
        b.core.r[:]=context["r"];b.pc=context["pc"];b.core.psw=context["psw"];b.core.cr=context["cr"];b.core.acc=context["acc"];b.running=True
        reports[-1]["nested_H08"]=dict(result=done,before=before,after=after,
            limitation="Controlled reentrant input at ig_apply; this does not prove the camera can schedule this input here.")
        return False
    h.b.add_breakpoint(pc,enter)
    result=fr.move_key(h,0x20);result["injected"]=injected[0]
    return result
run("nested_h08_negative",[OPEN,ONE,OK,REOPEN,("negative: nested cursor input while inflight",actual_nested_move),MENU])
save("adversarial.json",reports)
