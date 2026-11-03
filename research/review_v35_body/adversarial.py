"""Real image/native menu sequences. No direct writes to native UI or S.

Only hardware input is injected by Product and by the native readiness setter.
The UI-corruption negative writes the detached snapshot, explicitly labelled.
"""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import HERE, ROOT, module, save
v = module(ROOT / "firmware/image_v35/harness_scenarios/run_v35.py", "v35_bound")
v.bind()
fr, pe = v.fr, v.pe
class RealGetterHarness(v.V35Harness):
    def install_native_boundaries(self):
        super().install_native_boundaries()
        # This official getter reads and validates the actual S selector.
        # A constant-1 stub masks later native setters during refresh.
        self.b.breakpoints.pop(0x20271fec, None)
v.harness_mod.Harness = RealGetterHarness
R = pe.ROOT_ADDR
POINTS = {0x202871dc: "H07_native", 0x202bb96c: "H08_native", 0x20268768: "mode_setter", 0x202c2d84: "H07_return", 0x202c31cc: "dispatcher_exit"}

def snapshot(h, p):
    root = fr.root_fields(h)
    raw = b"".join(a.to_bytes(4, "big") + x.to_bytes(2, "big") for a, x in sorted(p.rpc.overlay.items()))
    return dict(mode=pe.settings_byte(h)[1], root=root, diag_early=hex(fr.u32(h, R + 232)),
                ui=h.state(), item=fr.u32(h, 0x205d9bf8), t=p.rpc.t,
                deep_cells=len(p.rpc.overlay), deep_sha256=hashlib.sha256(raw).hexdigest(),
                native_visits={name:h.b.visits[addr] for addr,name in POINTS.items()},
                rpc_writes=sum(x["cmd"] == 22 for x in p.rpc.log))

def boot(unit="50mm", ready=1, link=1):
    h, p, w = fr.boot(unit, ready=ready, link=link)
    # Run the official interrupt-safe setter instead of seeding the BSS word.
    h.b.breakpoints.pop(0x2009359c, None)
    setter = fr.native(h, 0x200935b4, (ready,))
    if not setter["ok"]:
        raise RuntimeError(setter)
    return h,p,w

def step(rec, label, h,p,w, fn):
    mark = w.mark()
    before = snapshot(h,p)
    out = fn()
    after = snapshot(h,p)
    rec["steps"].append(dict(action=label, result=out, before=before, after=after, hooks=w.since(mark)))
    save("adversarial-progress.json", reports)
    print(rec["name"], label, "result", out.get("ok", True) if isinstance(out,dict) else out,
          "mode", after["mode"], "state", after["root"]["state"], "flags", after["root"]["flags"],
          "diag", after["diag_early"], "native", after["native_visits"], flush=True)
    return out

def publish(h,p,w):
    opened,_,error=fr.publish(h,p,w)
    return dict(**opened, review_error=error)

def moves_to(h, target):
    out=[]
    for _ in range(9):
        if fr.u8(h,0x2022f726)==target:
            return dict(ok=all(s["ok"] for s in out), moves=out)
        s=fr.move_key(h,0x20)
        out.append(s)
        if not s["ok"]:break
    return dict(ok=False,moves=out,target=target)

reports=[]
def run(name, actions, unit="50mm", ready=1, link=1):
    rec=dict(name=name,unit=unit,steps=[])
    reports.append(rec)
    h,p,w=boot(unit,ready,link)
    rec["initial"]=snapshot(h,p)
    try:
        for label, fn in actions:
            step(rec,label,h,p,w,lambda fn=fn:fn(h,p,w))
        rec["final"]=snapshot(h,p)
        rec["settings_writes"]=[x for x in h.writes if x["address"]==hex(h.settings+0x36e)]
        rec["stub_hits"]=h.stub_hits
    except Exception as e:
        rec["error"]=str(e)
    save("adversarial.json",reports)
    return h,p,w,rec

OPEN=("ADJ Image open",publish)
ONE=("scroll to 01",lambda h,p,w:moves_to(h,1))
TWO=("scroll to 02",lambda h,p,w:moves_to(h,2))
OK=("OK",lambda h,p,w:fr.press(h,0x23))
MENU=("MENU close",lambda h,p,w:fr.press(h,0x29))
SCROLL=("scroll down",lambda h,p,w:fr.move_key(h,0x20))
FN2=("Fn2",lambda h,p,w:fr.native(h,0x202be220))
def reopen(h,p,w):
    h.parent()
    return publish(h,p,w)
REOPEN=("ADJ parent and reopen",reopen)

def corrupt_ui(h,p,w):
    address=fr.u32(h,R+136)+1960
    h.put(address,fr.u32(h,address)^1)
    return dict(ok=True,negative="corrupt snapshot magic",address=hex(address))

def nested(h,p,w):
    pc=p.symbol_pc("ig_event")
    injected=[False]
    def enter(b):
        if injected[0]:return False
        injected[0]=True
        context=dict(r=list(b.core.r),pc=b.pc,psw=b.core.psw,cr=dict(b.core.cr),acc=b.core.acc)
        before=snapshot(h,p)
        # Single interpreter, nested task stack. Restore the interrupted CPU
        # registers only. Preserve all nested memory effects and trace events.
        b.running=False
        b.set_reg("r15",0x206efff0)
        done=fr.native(h,0x202871d8,(0,))
        b.core.r[:]=context["r"];b.pc=context["pc"]
        b.core.psw=context["psw"];b.core.cr=context["cr"];b.core.acc=context["acc"]
        b.running=True
        rec["nested"]=dict(result=done,before=before,after=snapshot(h,p))
        return False
    h.b.add_breakpoint(pc,enter)
    result=fr.press(h,0x23)
    result["injected"]=injected[0]
    return result

selected=sys.argv[1] if len(sys.argv)>1 else "all"
cases={
 "i":[OPEN,ONE,OK,MENU],
 "ii":[OPEN,ONE,OK,SCROLL,TWO,OK,MENU],
 "iii":[OPEN,ONE,OK,SCROLL,MENU],
 "iv":[OPEN,ONE,OK,FN2,OK,MENU],
 "v":[OPEN,ONE,OK,MENU,REOPEN,TWO,OK,MENU],
 "viii":[OPEN,ONE,OK,REOPEN,("negative: damage UI snapshot",corrupt_ui),OK,SCROLL,OK,MENU,REOPEN,TWO,OK,MENU],
}
for name,actions in cases.items():
    if selected in ("all",name):run(name,actions)
if selected in ("all","vii"):
    # The closure uses this record to retain the actual nested call.
    rec=dict(name="vii",unit="50mm",steps=[]);reports.append(rec)
    h,p,w=boot();rec["initial"]=snapshot(h,p)
    for label,fn in (OPEN,ONE,("OK with actual nested H07",nested),MENU):
        step(rec,label,h,p,w,lambda fn=fn:fn(h,p,w))
    rec["final"]=snapshot(h,p)
    save("adversarial.json",reports)
if selected in ("all","p2"):
    def ready_now(h,p,w):
        p.ready=1
        return fr.native(h,0x200935b4,(1,))
    run("28mm_retry",[OPEN,("hardware ready setter",ready_now),("wait-free snapshot before reopening",lambda h,p,w:dict(ok=True)),MENU,REOPEN],unit="28mm",ready=0)
    run("never_ready",[OPEN,MENU,REOPEN,MENU,REOPEN],ready=0,link=0)
save("adversarial.json",reports)
