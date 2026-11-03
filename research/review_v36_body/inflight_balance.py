"""Observe callee-saved native registers before restoring the interrupted CPU."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import HERE, save as original_save
exec(compile((HERE / "reachability.py").read_text().split('which=sys.argv')[0], str(HERE / "reachability.py"), "exec"), globals())
def save(name, value): original_save("inflight-balance-" + name, value)
native = fr.native
records = []
def checked_native(h, addr, args=(), steps=8000000):
    check = addr in (0x202be220, 0x202c2880) and fr.u8(h, R + 6) == 1
    if check:
        before = dict(sp=h.b.get_reg("r15"), saved=[h.b.get_reg("r" + str(i)) for i in range(8, 14)])
    out = native(h, addr, args, steps)
    if check:
        after = dict(sp=h.b.get_reg("r15"), saved=[h.b.get_reg("r" + str(i)) for i in range(8, 14)])
        records.append(dict(entry=hex(addr), before=before, after=after, result=out,
            inflight=fr.u8(h, R + 6), native06=h.b.visits[0x202be250], native08=h.b.visits[0x202bb96c]))
        original_save("inflight-register-balance.json", records)
        assert out["ok"] and before == after
    return out
fr.native = checked_native
run("inflight_H06_H08_register_balance", [OPEN, ONE, OK, REOPEN,
    ("real ig_apply nested H06", lambda h,p,w: nested_hook(h,p,w,6,"ig_apply")),
    ("real ig_apply nested H08", lambda h,p,w: nested_hook(h,p,w,8,"ig_apply")), MENU])
save("adversarial.json", reports)
assert len(records) == 2 and all(r["inflight"] == 1 and r["native06"] == r["native08"] == 0 for r in records)
assert "error" not in reports[-1] and reports[-1]["final"]["mode"] == 1
print("PASS actual inflight H06/H08 return with balanced SP and r8..r13 before CPU restore", flush=True)
