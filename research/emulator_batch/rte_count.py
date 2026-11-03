"""Where RTE bank completions happen in batch mode: inside gxr_run or in Python steps.

Cold MAIN, no card, 0..10,000,000 steps; counts only, no behavior change.
"""
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

counts = {"python_rte": 0, "python_rte_bank_switch": 0}
original = backend.Backend._step_once


def counted(cpu, start):
    pc = cpu.get_reg("pc")
    rte = cpu._location(pc, 2) is not None and cpu.read(pc, 2) == b"\x10\xd6"
    sm = cpu.get_reg("psw") & 0x80
    stop = original(cpu, start)
    if rte and cpu.get_reg("pc") != pc:
        counts["python_rte"] += 1
        counts["python_rte_bank_switch"] += (cpu.get_reg("psw") & 0x80) != sm
    return stop


backend.Backend._step_once = counted
machine = compare.cold(snap, "batch", "no-card", None)
try:
    compare.run_to(snap, machine, 10000000, "rte_steps")
    result = {**counts, "c_rte_bank_switch": machine.cpu.batch_stats["rte-in-c"],
              "state": snap.state_hash(machine)["all"], "steps": machine.cpu.steps}
finally:
    machine.close()
(HERE / "local/rte-count.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
