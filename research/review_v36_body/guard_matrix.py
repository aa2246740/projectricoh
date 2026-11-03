"""Real native H06/H08 under labelled root faults; preserve CPU balance evidence."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import HERE, save as original_save
exec(compile((HERE / "adversarial.py").read_text().split('selected=sys.argv')[0], str(HERE / "adversarial.py"), "exec"), globals())
def save(name, value):
    original_save("guard-matrix-" + name, value)
POINTS[0x202be250] = "H06_native"
POINTS[0x202be6a8] = "H06_safe_exit"
POINTS[0x202bcf58] = "H08_safe_exit"

h, p, w = boot()
rec = dict(name="labelled_root_guard_faults", steps=[], branches=[])
reports.append(rec)
for label, fn in (OPEN, ONE, OK, REOPEN):
    step(rec, label, h, p, w, lambda fn=fn: fn(h, p, w))
golden = snapshot(h, p)["deep_sha256"]
assert fr.u8(h, 0x2022f5ac) == 8
old_flags = fr.u32(h, R + 212)
old_restore = fr.u32(h, R + 156)

def probe(label, hook):
    before = snapshot(h, p)
    regs = [h.b.get_reg("r" + str(i)) for i in range(8, 14)]
    psw = h.b.core.psw
    sp = h.b.get_reg("r15")
    mark = w.mark()
    wi = len(h.writes)
    done = fr.native(h, 0x202be220) if hook == 6 else fr.move_key(h, 0x20)
    after = snapshot(h, p)
    row = dict(label=label, hook=hook, result=done, before=before, after=after,
               sp_before=sp, sp_after=h.b.get_reg("r15"), saved_before=regs,
               saved_after=[h.b.get_reg("r" + str(i)) for i in range(8, 14)],
               psw_before=psw, psw_after=h.b.core.psw, hooks=w.since(mark),
               settings_writes=[x for x in h.writes[wi:] if h.settings <= int(x["address"], 16) < h.settings + 4096])
    rec["branches"].append(row)
    save("adversarial.json", reports)
    assert done["ok"] and row["sp_before"] == row["sp_after"]
    assert row["saved_before"] == row["saved_after"]
    assert after["mode"] == 1 and after["deep_sha256"] == golden
    assert after["native_visits"]["H06_native"] == 0 and after["native_visits"]["H08_native"] == 0
    assert not row["settings_writes"]
    assert any(x["hook"] == hook for x in row["hooks"])
    print("PASS", label, hook, "mode=1 no native continuation, SP and r8..r13 balanced", flush=True)

# RF_BUSY is an explicit root fault, distinct from scheduler-controlled inflight.
h.put(R + 212, old_flags | 8)
for hook in (6, 8): probe("RF_BUSY root flag injection", hook)
h.put(R + 212, old_flags)
h.put(R + 156, 0)
for hook in (6, 8): probe("!owned root restore marker injection", hook)
h.put(R + 156, old_restore)

# Genuine rv_retire cannot restore rows if its resident restore record is corrupt.
# This is two labelled corruption inputs, not a naturally occurring UI sequence.
h.put(R + 156, 0)
corrupt_ui(h, p, w)
probe("rv_check retire with missing restore marker", 8)
assert fr.u8(h, R + 5) == 6 and fr.u8(h, 0x2022f5ac) == 8
for hook in (6, 8): probe("disabled with eight rows after failed restoration", hook)
rec["final"] = snapshot(h, p)
save("adversarial.json", reports)
print("PASS all seven real-native branch probes", flush=True)
