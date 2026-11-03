"""Forwarded accesses by device and address, batch mode, no card, steps 10M..12M (counts only)."""
from collections import Counter
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()
import compare

tools, snap, _ = compare.load_impl("batch")
import backend

counts, active = Counter(), [False]
original = backend.Backend._bus


def bus(cpu, opaque, pc, addr, n, ptr, writing):
    if active[0] and cpu._batching:
        owner = next((type(getattr(rd or wr, "__self__", None)).__name__
                      for lo, hi, rd, wr in cpu.mmio if lo <= addr < hi), "write-trace-or-unmapped")
        counts[(owner, "w" if writing else "r", "%#010x" % addr)] += 1
    return original(cpu, opaque, pc, addr, n, ptr, writing)


backend.Backend._bus = bus
machine = compare.cold(snap, "batch", "no-card", None)
try:
    compare.run_to(snap, machine, 10000000, "hist_steps")
    active[0] = True
    compare.run_to(snap, machine, 12000000, "hist_steps")
    state = snap.state_hash(machine)["all"]
finally:
    machine.close()
by_owner = Counter()
for (owner, _, _), value in counts.items():
    by_owner[owner] += value
result = {"window": [10000000, 12000000], "state": state, "by_device": dict(by_owner.most_common()),
          "top_addresses": [{"device": o, "access": a, "address": x, "count": c}
                            for (o, a, x), c in counts.most_common(25)]}
(HERE / "local/mmio-hist.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result["by_device"]))
for row in result["top_addresses"][:12]:
    print(row)
