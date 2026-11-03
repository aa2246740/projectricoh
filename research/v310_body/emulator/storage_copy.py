"""Offline M2c board runs with SD evidence and bounded native observations."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import pickle
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "tools/gxr_emulator_standby"
# Caller sets OUT (no default); see outputs.py.
OUT = None
sys.path.insert(0, str(HERE))
from backend import Backend, REGS, StepHook
from board import install as install_board
from devices import install as install_devices
from image import Image
from m2 import library_accepted, restore as restore_m2
from observe import Observer, CURRENT_TASK
from peripherals import install as install_peripherals
from sdcard import install as install_sd
import outputs


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(HERE.glob("*.py"))}


def save(cpu, path, source_hashes=None):
    path.write_bytes(pickle.dumps(cpu.snapshot(), protocol=4))
    path.with_suffix(".json").write_text(json.dumps({
        "sha256": sha(path), "steps": cpu.steps, "pc": cpu.get_reg("pc"),
        "image_sha256": cpu.image.sha256,
        "library_sha256": sha(HERE / "build/libgxr_m32r.dylib"),
        "source_hashes": source_hashes if source_hashes is not None else sources()}, indent=2) + "\n")


class Machine:
    def __init__(self, card=None, resume=None):
        self.cpu = Backend(trace_limit=2048)
        self.image = Image("official")
        self.image.load(self.cpu)
        self.devices = install_devices(self.cpu, monitor_hle=True)
        self.devices.update(install_peripherals(self.cpu))
        self.devices.update(install_board(self.cpu, self.devices))
        old = ROOT / "research/emulator_m2b/local"
        if resume and Path(resume).resolve().is_relative_to(old):
            restore_m2(self.cpu, Path(resume))
        else:
            fixture_path = old / "nand-reflector.pages.json"
            fixture = json.loads(fixture_path.read_text())
            if fixture["image_sha256"] != self.image.sha256:
                raise ValueError("NAND fixture image identity differs")
            for page, data in fixture["pages"].items():
                self.devices["nand"].pages[int(page)] = bytes.fromhex(data)
            receive_field = "pay" + "load"
            setattr(self.devices["dma"], receive_field, (old / "unit-info-synthetic.bin").read_bytes())
            self.devices["startup"].hsp_info_notifications = True
            self.devices["startup"].hsp_hello = True
            self.devices["startup"].hsp_rpc_errors = True
            self.devices["startup"].hsp_rpc8 = True
            self.devices["board"].configure_inputs()
        self.sd = install_sd(self.cpu, card)
        self.devices["sd"] = self.sd
        if resume and not Path(resume).resolve().is_relative_to(old):
            path = Path(resume).resolve()
            if not path.is_relative_to(outputs.require(OUT)):
                raise ValueError("checkpoint is outside the caller's output directory")
            meta = json.loads(path.with_suffix(".json").read_text())
            if sha(path) != meta["sha256"] or self.image.sha256 != meta["image_sha256"]:
                raise ValueError("checkpoint identity differs")
            if not library_accepted(meta["library_sha256"]):
                raise ValueError("checkpoint core identity differs")
            self.cpu.restore(pickle.loads(path.read_bytes()))
        self.observer = Observer(self.cpu)
        self.events = deque(maxlen=4096)
        self.pending_returns = {}
        for address, label in [(0x2010DDF8, "storage-init-return"),
                               (0x2010E1D8, "medium-0-return"),
                               (0x2010E23C, "medium-1-return"),
                               (0x200A40B4, "file-open"), (0x200A41AC, "file-create"),
                               (0x200A437C, "file-close"), (0x200A479C, "file-data-a"),
                               (0x200A48C8, "file-data-b"),
                               (0x0500D4E4, "file-lock-wait"),
                               (0x0500D4FC, "file-lock-signal"),
                               (0x2011461C, "medium-mount"),
                               (0x20057740, "sd-initialize")]:
            self.watch(address, label)
        original_hook = self.cpu.step_hook

        def tick(cpu):
            self.devices["startup"].advance(self.devices["irq"])
            self.devices["dma"].advance(self.devices["irq"], self.devices["startup"])
            self.devices["board"].advance()
            self.sd.advance(self.devices["irq"])
            original_hook(cpu)
        def plan(cpu):
            return (min(self.devices["startup"].batch_plan(), self.devices["dma"].batch_plan(),
                        self.devices["board"].batch_plan(), self.sd.batch_plan()),
                    False, frozenset())
        def skip(cpu, n):
            self.devices["startup"].batch_skip(n)
            self.devices["dma"].batch_skip(n)
            self.devices["board"].batch_skip(n)
            self.sd.batch_skip(n)
        def advanced():
            d = self.devices
            return (d["startup"], d["dma"], d["board"], d["sio2"], d["i2c"], self.sd)
        self.cpu.step_hook = StepHook(tick, plan, skip, original_hook, devices=advanced)

    def task(self):
        return int.from_bytes(self.cpu.read(CURRENT_TASK, 2), "big")

    def watch(self, address, label):
        def hit(cpu):
            row = {"kind": label, "step": cpu.steps, "pc": address,
                   "task": self.task(), "psw": cpu.get_reg("psw"),
                   "args": [cpu.get_reg(f"r{n}") for n in range(4, 8)],
                   "r0": cpu.get_reg("r0"), "lr": cpu.get_reg("lr")}
            self.events.append(row)
            if label in ("medium-mount", "sd-initialize", "file-open", "file-create", "file-close") or label.startswith("file-core"):
                ret = cpu.get_reg("lr")
                task = row["task"]
                key = (ret, task)
                self.pending_returns.setdefault(key, []).append(label)
                if not getattr(self, "return_hooks", None):
                    self.return_hooks = set()
                if ret not in self.return_hooks:
                    self.return_hooks.add(ret)
                    def returned(machine):
                        key = (ret, self.task())
                        names = self.pending_returns.get(key, [])
                        if names:
                            name = names.pop()
                            self.events.append({"kind": name + "-return", "step": machine.steps,
                                                "task": self.task(), "pc": ret,
                                                "r0": machine.get_reg("r0")})
                    self.observer.breakpoint(ret, returned)
        self.observer.breakpoint(address, hit)

    def close(self):
        self.cpu.close()


def run(args):
    out = outputs.declare_media(outputs.require(OUT))
    out.mkdir(exist_ok=True)
    target = out / (args.name + ".json")
    if target.exists() or not args.name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("use a new simple evidence name")
    started = time.monotonic()
    machine = Machine(args.card, args.resume)
    machine.sd.journal = out / (args.name + "-sd.jsonl")
    cpu = machine.cpu
    start_step = cpu.steps
    source_hashes = sources()
    if args.card_event:
        machine.sd.card_event()
    if args.stop_at:
        for address in args.stop_at:
            original = cpu.breakpoints.get(address)
            def stop_here(c, original=original):
                if original:
                    original(c)
                return args.task is None or machine.task() == args.task
            cpu.add_breakpoint(address, stop_here)
    result = {"start_step": start_step, "resume": str(args.resume) if args.resume else None,
              "image_sha256": machine.image.sha256, "sources": source_hashes,
              "library_sha256": sha(HERE / "build/libgxr_m32r.dylib"),
              "arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}}
    try:
        remaining = args.budget
        while remaining:
            count = min(remaining, 1000000)
            stop = cpu.run(count)
            remaining -= count
            print(json.dumps({"steps": cpu.steps, "pc": cpu.get_reg("pc"),
                              "reason": stop.reason}), flush=True)
            if stop.reason != "max_steps":
                break
        result.update({"steps": cpu.steps, "stop": stop.to_dict(),
                       "observations": machine.observer.summary(),
                       "registers": {k: cpu.get_reg(k) for k in REGS},
                       "events": list(machine.events), "sd_events": list(machine.sd.events),
                       "sd_counts": dict(machine.sd.counts),
                       "last_mmio": list(cpu.mmio_trace), "last_instructions": list(cpu.trace),
                       "irq_delivered": machine.devices["irq"].delivered,
                       "timer_expirations": machine.devices["timer"].expirations,
                       "elapsed_sec": round(time.monotonic() - started, 3)})
        if machine.sd.medium:
            result["medium_sha256"] = machine.sd.medium.sha256()
        save(cpu, out / (args.name + "-stop.pkl"), source_hashes)
        target.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"output": str(target), "steps": cpu.steps,
                          "stop": result["stop"]}), flush=True)
    finally:
        machine.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--budget", type=int, default=50000000)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--card", type=Path)
    parser.add_argument("--card-event", action="store_true")
    parser.add_argument("--stop-at", type=lambda v: int(v, 0), action="append", default=[])
    parser.add_argument("--task", type=int)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
