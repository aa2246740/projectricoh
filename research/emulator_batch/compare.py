"""Cold MAIN runs for per-step/batch equivalence, with exit statistics.

  --impl step   unmodified tools/gxr_emulator (original library), per-step loop
  --impl batch  tools/gxr_emulator_batch with set_batch(True)
  --impl copy-step  tools/gxr_emulator_batch with batch off (its per-step loop)

Both use fast recording. The hash is research/emulator_speed's state_hash
(CPU, every mapped byte, every device field, panel keys) plus the observer
value hash; the ADJ window also hashes the Flow call trace. Outputs go to
research/emulator_batch/local only.
"""
import argparse
import importlib
import json
from pathlib import Path
import shutil
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "local"
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()

CANDIDATE = {"no-card": 33004041, "card": 42572307}
SEED = ROOT / "research/emulator_speed/local/card-seed.img"


def load_impl(impl, shadow=None):
    tools = ROOT / ("tools/gxr_emulator" if impl == "step" else "tools/gxr_emulator_batch")
    sys.path.insert(0, str(tools))
    if shadow:
        # Scratch mutant modules (e.g. one edited devices.py) shadow the tool's.
        sys.path.insert(0, str(Path(shadow).resolve()))
    sdcard = importlib.import_module("sdcard")
    if impl != "step":
        # The batch copy has no default output or medium directory.
        importlib.import_module("outputs").declare_media(OUT)
    if impl == "step":
        # The original BlockImage only admits its own study directories. Keep
        # its checks and add this study's local directory, in memory only.
        original = sdcard.BlockImage.__init__
        def admitted(self, path):
            path = Path(path).resolve()
            if path.is_relative_to(OUT):
                self.path, self.size = path, path.stat().st_size
                if not self.size or self.size % sdcard.SECTOR:
                    raise ValueError("SD image size must be a positive sector multiple")
                self.sectors = self.size // sdcard.SECTOR
                self.read_errors, self.write_errors = set(), set()
                return
            original(self, path)
        sdcard.BlockImage.__init__ = admitted
    snap = importlib.import_module("speed_snapshot")
    flow = importlib.import_module("input_run").Flow
    return tools, snap, flow


def cold(snap, impl, profile, medium):
    """speed_snapshot.cold() without its writes into the tool's local/."""
    if profile == "card":
        shutil.copyfile(SEED, medium)
    machine = snap.Machine(medium if profile == "card" else None)
    machine.cpu.set_mode("fast")
    if impl == "batch":
        machine.cpu.set_batch(True)
    snap.attach_panel(machine)
    serial = machine.devices["serial"]
    mask, level = serial.input_bytes.get(0, (0, 0))
    serial.input_bytes[0] = (mask | 2, level & ~2)
    snap.set_dial(machine.cpu, machine.devices, 2)
    return machine


def stats(cpu):
    return dict(getattr(cpu, "batch_stats", {}))


def delta(after, before):
    return {k: after.get(k, 0) - before.get(k, 0) for k in after if after.get(k, 0) != before.get(k, 0)}


def run_to(snap, machine, target, log):
    while machine.cpu.steps < target:
        count = min(1000000, target - machine.cpu.steps)
        stop = machine.cpu.run(count)
        if stop.reason != "max_steps" or stop.steps != count:
            raise RuntimeError("stopped before requested work: " + json.dumps(stop.to_dict()))
        if machine.cpu.steps % 5000000 == 0 or machine.cpu.steps == target:
            print(json.dumps({log: machine.cpu.steps}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--impl", choices=("step", "batch", "copy-step"), required=True)
    parser.add_argument("--profile", choices=tuple(CANDIDATE), required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--points", default="1000000,10000000,candidate")
    parser.add_argument("--adj", action="store_true", help="ADJ down 120000, up 3000000 after the candidate")
    parser.add_argument("--shadow", help="scratch directory of mutant module copies (batch only)")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    target = OUT / (args.name + ".json")
    if target.exists():
        raise ValueError("choose a fresh name")
    tools, snap, Flow = load_impl(args.impl, args.shadow)
    points = [CANDIDATE[args.profile] if p == "candidate" else int(p) for p in args.points.split(",")]
    medium = OUT / (args.name + ".img")
    began = time.monotonic()
    machine = cold(snap, args.impl, args.profile, medium)
    result = {"impl": args.impl, "profile": args.profile, "tools": str(tools.relative_to(ROOT)),
              "shadow": {p.name: snap.sha(p) for p in sorted(Path(args.shadow).glob("*.py"))}
              if args.shadow else None,
              "library_sha256": snap.sha(tools / "build/libgxr_m32r.dylib"),
              "points": {}, "segments": []}
    def emit():
        result["total_seconds"] = time.monotonic() - began
        target.write_text(json.dumps(result, indent=2) + "\n")
    try:
        result["setup_seconds"] = time.monotonic() - began
        for point in points:
            s0, t0, b0 = machine.cpu.steps, time.monotonic(), stats(machine.cpu)
            run_to(snap, machine, point, "boot_steps")
            seconds = time.monotonic() - t0
            result["segments"].append({"segment": "boot", "from": s0, "to": point, "seconds": seconds,
                                       "steps_per_second": (point - s0) / seconds if seconds else None,
                                       "exits": delta(stats(machine.cpu), b0)})
            result["points"][str(point)] = {"state": snap.state_hash(machine),
                                            "observations": snap.value_hash(snap.observer_data(machine))}
            emit()
        if args.adj:
            if machine.cpu.steps != CANDIDATE[args.profile]:
                raise ValueError("ADJ window starts at the candidate point")
            flow = Flow(machine)
            adj = []
            for down, count in ((True, 120000), (False, 3000000)):
                machine.panel.set_key("ADJ", down)
                s0, t0, b0 = machine.cpu.steps, time.monotonic(), stats(machine.cpu)
                stop = machine.cpu.run(count)
                seconds = time.monotonic() - t0
                adj.append({"key": "ADJ", "down": down, "requested": count, "stop": stop.to_dict(),
                            "end_step": machine.cpu.steps})
                result["segments"].append({"segment": "adj-" + ("down" if down else "up"), "from": s0,
                                           "to": machine.cpu.steps, "seconds": seconds,
                                           "steps_per_second": (machine.cpu.steps - s0) / seconds,
                                           "exits": delta(stats(machine.cpu), b0)})
                if stop.reason != "max_steps":
                    break
            result["adj"] = {"segments": adj, "state": snap.state_hash(machine),
                             "observations": snap.value_hash(snap.observer_data(machine)),
                             "flow_hash": snap.value_hash(flow.rows), "flow_rows": len(flow.rows),
                             "flow_counts": dict(flow.counts),
                             "open_calls_hash": snap.value_hash(flow.open_calls()),
                             "panel_events_hash": snap.value_hash(machine.panel.events)}
        result["final_stats"] = stats(machine.cpu)
        result["medium_sha256"] = snap.sha(medium) if args.profile == "card" else None
        result["status"] = "complete"
    except Exception as error:
        result["status"] = "error"
        result["error"] = {"type": type(error).__name__, "message": str(error)[:600],
                           "steps": machine.cpu.steps}
        raise
    finally:
        emit()
        machine.close()
        print(json.dumps({"result": str(target.relative_to(ROOT)), "status": result.get("status"),
                          "seconds": round(result["total_seconds"], 1)}), flush=True)


if __name__ == "__main__":
    main()
