"""Continue one pending native test call and record its real ABI return."""
import argparse
import copy
from collections import deque
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
sys.path.insert(0, str(ROOT / "tools/gxr_emulator"))
from backend import REGS
from fat_image import inspect
from file_calls import Calls, SEM_COUNT, SENTINEL
from storage_run import Machine, save, sources


def signed(value):
    return value if value < 0x80000000 else value - 0x100000000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--resume", type=Path, required=True)
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--budget", type=int, default=40000000)
    parser.add_argument("--close-budget", type=int, default=20000000)
    args = parser.parse_args()
    if not args.name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("use a simple continuation name")
    target = OUT / (args.name + ".json")
    if target.exists():
        raise ValueError("use a fresh continuation name")
    previous = json.loads(args.case.read_text())
    result = copy.deepcopy(previous)
    result["continuation_of"] = str(args.case)
    result["continuation_sources"] = sources()
    result["continuation_runner_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["prior_error"] = result.pop("error", None)
    result["status"] = "incomplete"
    machine = Machine(args.card, args.resume)
    machine.sd.journal = OUT / (args.name + "-sd.jsonl")
    cpu = machine.cpu
    calls = Calls(machine)
    pending = result["calls"][-1]
    if pending["name"] not in ("write-new-file", "close-written-file"):
        raise ValueError("case does not end in a supported pending file call")
    machine.events = deque(result.get("events", []), maxlen=4096)
    for address, label in ((0x200AF4EC, "file-error-code"),
                           (0x200A3D0C, "file-core-dma-stop")):
        machine.watch(address, label)
    for address in (0x200595F0, 0x20059930):
        def returned(c, address=address):
            machine.events.append({"kind": "file-core-write-host-return", "step": c.steps,
                                   "task": machine.task(), "pc": address, "r0": c.get_reg("r0")})
        machine.observer.breakpoint(address, returned)
    def reached(c):
        return machine.task() == 8 and bool(c.get_reg("psw") & 0x80)
    cpu.add_breakpoint(SENTINEL, reached)
    start = cpu.steps
    before_coverage = dict(cpu.coverage)
    try:
        left = args.budget
        while left:
            count = min(left, 1000000)
            stop = cpu.run(count)
            left -= count
            print(json.dumps({"steps": cpu.steps, "reason": stop.reason}), flush=True)
            if stop.reason != "max_steps":
                break
        result["continuation_segment"] = {"start_step": start, "end_step": cpu.steps, "stop": stop.to_dict()}
        if stop.reason != "breakpoint" or cpu.get_reg("pc") != SENTINEL or machine.task() != 8:
            raise RuntimeError("pending native call has not reached its real return point")
        value = signed(cpu.get_reg("r0"))
        pending["first_stop"] = pending["stop"]
        pending.update({"end_step": cpu.steps, "stop": stop.to_dict(), "result": value,
                        "return_task": machine.task(),
                        "semaphore47_after": int.from_bytes(cpu.read(SEM_COUNT, 2), "big"),
                        "state_after": calls.state(), "continued": True})
        coverage = pending.setdefault("native_file_path", {})
        for pc, count in cpu.coverage.items():
            delta = count - before_coverage.get(pc, 0)
            if 0x200A3E00 <= pc < 0x200BC000 and delta > 0:
                key = f"{pc:08x}"
                coverage[key] = coverage.get(key, 0) + delta
        print(json.dumps({"native_return": pending["name"], "value": value,
                          "task": machine.task(), "step": cpu.steps}), flush=True)
        cpu.breakpoints.pop(SENTINEL, None)
        if pending["name"] == "write-new-file":
            result["written"] = value
            fd = pending["args"][0]
            result["write_close"] = calls.call(0x200A437C, [fd], "close-written-file", task=8,
                                                budget=args.close_budget)
        else:
            result["write_close"] = value
        result["medium"] = inspect(machine.sd.medium.path)
        failed = result["written"] <= 0 or result["write_close"] < 0
        result["status"] = "passed" if failed and machine.sd.counts["io-error"] > 0 else "incomplete"
    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        result["calls"].extend(calls.rows)
        result.update({"steps": cpu.steps, "events": list(machine.events),
                       "sd_events": list(machine.sd.events), "sd_counts": dict(machine.sd.counts),
                       "registers": {name: cpu.get_reg(name) for name in REGS},
                       "observations": machine.observer.summary(),
                       "last_mmio": list(cpu.mmio_trace), "last_instructions": list(cpu.trace)})
        save(cpu, OUT / (args.name + "-stop.pkl"), result["continuation_sources"])
        target.write_text(json.dumps(result, indent=2) + "\n")
        machine.close()
    print(json.dumps({"status": result["status"], "output": str(target)}))
    raise SystemExit(0 if result["status"] == "passed" else 2)


if __name__ == "__main__":
    main()
