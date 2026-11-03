"""Reproducible state, observation, and timing checks for emulator-speed-r1."""
import argparse
from bisect import bisect_right
import copy
import cProfile
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools/gxr_emulator"
OUT = Path(__file__).resolve().parent / "local"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope_guard import enable
enable()
import speed_snapshot as snap
from input_run import Flow


def emit(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def selected(profile, mode="fast", label="run"):
    return snap.load(snap.LOCAL / (profile + ".snap.z"), mode=mode,
                     medium=OUT / (profile + "-" + label + ".img"), allow_idle_task=True)


def observation(machine):
    return snap.value_hash(snap.observer_data(machine))


def equivalence(args):
    reference = json.loads((OUT / (args.profile + "-continuous.json")).read_text())
    machine, metadata = selected(args.profile, args.mode, "equivalence-" + args.mode)
    result = {"profile": args.profile, "mode": args.mode, "points": {},
              "snapshot_sha256": metadata["sha256"], "identity": metadata["identity"]}
    try:
        if reference["identity"] != metadata["identity"] or reference["snapshot_sha256"] != metadata["sha256"]:
            raise ValueError("continuous reference identity differs")
        for distance in (1000000, 10000000):
            began = time.monotonic()
            count = metadata["steps"] + distance - machine.cpu.steps
            remaining = count
            while remaining:
                chunk = min(remaining, 1000000)
                snap.run_steps(machine, chunk)
                remaining -= chunk
                print(json.dumps({"equivalence_steps": machine.cpu.steps,
                                  "profile": args.profile, "mode": args.mode}), flush=True)
            state, observed = snap.state_hash(machine), observation(machine)
            expected = reference["points"][str(distance)]
            row = {"state": state, "observations": observed,
                   "state_equal": state == expected["state"],
                   "observations_equal": observed == expected["observations"],
                   "executed": count, "seconds": time.monotonic() - began}
            result["points"][str(distance)] = row
            result["passed"] = all(x["state_equal"] and x["observations_equal"] for x in result["points"].values())
            emit(OUT / (args.profile + "-equivalence-" + args.mode + ".json"), result)
            print(json.dumps({"distance": distance, "profile": args.profile,
                              "mode": args.mode, "state_equal": row["state_equal"],
                              "observations_equal": row["observations_equal"]}), flush=True)
    finally:
        machine.close()
    return result["passed"]


def benchmark(args):
    results = {"profile": args.profile, "steps_per_run": args.steps,
               "machine": subprocess.check_output(["uptime"], text=True).strip(), "runs": []}
    for repeat in range(5):
        for mode in ("debug", "fast") if repeat % 2 == 0 else ("fast", "debug"):
            began = time.monotonic()
            machine, metadata = selected(args.profile, mode, "timing")
            loaded = time.monotonic()
            try:
                snap.run_steps(machine, args.steps)
                finished = time.monotonic()
                state = snap.state_hash(machine)
                results["runs"].append({"repeat": repeat, "mode": mode, "steps": args.steps,
                                        "load_seconds": loaded - began,
                                        "run_seconds": finished - loaded,
                                        "total_seconds": finished - began,
                                        "instructions_per_second": args.steps / (finished - loaded),
                                        "state": state, "observations": observation(machine)})
                print(json.dumps({"repeat": repeat, "mode": mode, "seconds": finished - loaded}), flush=True)
            finally:
                machine.close()
            emit(OUT / (args.profile + "-benchmark.json"), results)
    hashes = {(r["state"]["all"], r["observations"]) for r in results["runs"]}
    results["equal_states_and_observations"] = len(hashes) == 1
    for mode in ("fast", "debug"):
        values = [r["instructions_per_second"] for r in results["runs"] if r["mode"] == mode]
        results[mode] = {"median": statistics.median(values), "min": min(values), "max": max(values)}
    results["ratio"] = results["fast"]["median"] / results["debug"]["median"]
    emit(OUT / (args.profile + "-benchmark.json"), results)
    return results["equal_states_and_observations"]


def inputs(args):
    began = time.monotonic()
    if args.origin == "cold":
        metadata = json.loads((snap.LOCAL / (args.profile + ".snap.json")).read_text())
        card = OUT / "card-seed.img" if args.profile == "card" else None
        if snap.identity(card) != metadata["identity"]:
            raise ValueError("cold input identity differs")
        machine = snap.cold(card, args.mode, OUT / (args.profile + "-keys-cold.img"))
        remaining = metadata["steps"]
        while remaining:
            count = min(remaining, 1000000)
            snap.run_steps(machine, count)
            remaining -= count
            print(json.dumps({"cold_steps": machine.cpu.steps, "profile": args.profile}), flush=True)
        if snap.state_hash(machine) != metadata["state_hash"]:
            machine.close()
            raise ValueError("cold run did not reach the exact saved state")
    else:
        machine, metadata = selected(args.profile, args.mode, "inputs-" + args.origin + "-" + args.mode)
    ready = time.monotonic()
    flow = Flow(machine)
    name = args.sequence
    keys = ["ADJ"] if name == "adj" else ["ADJ", "OK", "DISP", "UP", "DOWN", "LEFT", "RIGHT", "HALF", "FULL"]
    start = machine.cpu.steps
    result = {"profile": args.profile, "mode": args.mode, "origin": args.origin,
              "sequence": name, "snapshot_sha256": metadata["sha256"], "segments": [],
              "start_step": start, "setup_seconds": ready - began}
    try:
        stopped = False
        for key in keys:
            for down, count in ((True, 120000 if name == "adj" else 300000),
                                (False, 3000000 if name == "adj" else 600000)):
                machine.panel.set_key(key, down)
                stop = machine.cpu.run(count)
                result["segments"].append({"key": key, "down": down, "requested": count,
                                           "stop": stop.to_dict(), "end_step": machine.cpu.steps})
                if stop.reason != "max_steps":
                    stopped = True
                    break
            if stopped:
                break
        execution_finished = time.monotonic()
        result.update({"run_seconds": execution_finished - ready,
                       "total_seconds": time.monotonic() - began,
                       "state": snap.state_hash(machine), "observations": observation(machine),
                       "ui_state": int.from_bytes(machine.cpu.read(0x205D9C00, 4), "big"),
                       "ui_table": int.from_bytes(machine.cpu.read(0x2037F800, 4), "big"),
                       "unit_field": int.from_bytes(machine.cpu.read(0x2037F2F4, 4), "big"),
                       "flow": flow.rows, "flow_hash": snap.value_hash(flow.rows),
                       "flow_counts": dict(flow.counts),
                       "open_calls": flow.open_calls(), "panel_events": machine.panel.events,
                       "completed_all_segments": len(result["segments"]) == 2 * len(keys)
                            and all(r["stop"]["reason"] == "max_steps" for r in result["segments"]),
                       "trace_records": len(machine.cpu.trace),
                       "coverage_sites": len(machine.cpu.coverage)})
        result["verification_seconds"] = time.monotonic() - execution_finished
        result["total_seconds"] = time.monotonic() - began
        target = OUT / (args.profile + "-" + name + "-" + args.origin + "-" + args.mode + ".json")
        emit(target, result)
        print(json.dumps({"result": str(target.relative_to(ROOT)), "segments": len(result["segments"]),
                          "complete": result["completed_all_segments"]}), flush=True)
    finally:
        machine.close()
    return True


def identity_checks(args):
    path = snap.LOCAL / (args.profile + ".snap.z")
    metadata = json.loads(path.with_suffix(".json").read_text())
    target = OUT / (args.profile + "-identity-copy.snap.z")
    target.write_bytes(path.read_bytes())
    checks = {}
    def reject(label, value, **kw):
        emit(target.with_suffix(".json"), value)
        try:
            machine, _ = snap.load(target, **kw)
        except ValueError as error:
            checks[label] = {"rejected": True, "rebuild_command": "/usr/bin/python3 -I -B" in str(error)}
        else:
            machine.close()
            checks[label] = {"rejected": False}
    reject("candidate_default", metadata)
    for key in metadata["identity"]["files"]:
        changed = copy.deepcopy(metadata)
        changed["identity"]["files"][key] = "0" * 64
        reject("file:" + key, changed, allow_idle_task=True)
    for key in metadata["identity"]["configuration"]:
        changed = copy.deepcopy(metadata)
        changed["identity"]["configuration"][key] = "different"
        reject("configuration:" + key, changed, allow_idle_task=True)
    changed = copy.deepcopy(metadata)
    changed["sha256"] = "0" * 64
    reject("compressed_state_sha", changed, allow_idle_task=True)
    reject("requested_configuration", metadata, allow_idle_task=True, configuration={})
    result = {"checks": checks, "passed": all(x["rejected"] and x.get("rebuild_command") for x in checks.values())}
    emit(OUT / (args.profile + "-identity-checks.json"), result)
    print(json.dumps({"checks": len(checks), "passed": result["passed"]}))
    return result["passed"]


def profile_run(args):
    import backend
    import storage_run
    class TimedBackend(backend.Backend):
        def __init__(self, **kw):
            self.metrics = {"bus_ram_seconds": 0.0, "bus_mmio_seconds": 0.0,
                            "bus_ram_calls": 0, "bus_mmio_calls": 0,
                            "outer_api_seconds": 0.0, "api": {}}
            self.depth = 0
            self.ram_starts, self.ram_ends = [], []
            super().__init__(**kw)
            for name in ("gxr_step", "gxr_flush", "gxr_reg_get", "gxr_reg_set", "gxr_interrupt"):
                original = getattr(self.lib, name)
                def measured(*values, original=original, name=name):
                    started = time.perf_counter()
                    outer = self.depth == 0
                    self.depth += 1
                    try:
                        return original(*values)
                    finally:
                        self.depth -= 1
                        elapsed = time.perf_counter() - started
                        row = self.metrics["api"].setdefault(name, {"calls": 0, "seconds": 0.0})
                        row["calls"] += 1
                        row["seconds"] += elapsed
                        if outer:
                            self.metrics["outer_api_seconds"] += elapsed
                setattr(self.lib, name, measured)
        def _bus(self, opaque, pc, addr, size, pointer, writing):
            began = time.perf_counter()
            index = bisect_right(self.ram_starts, addr) - 1
            is_ram = index >= 0 and addr + size <= self.ram_ends[index]
            category = "bus_ram" if is_ram else "bus_mmio"
            try:
                return super()._bus(opaque, pc, addr, size, pointer, writing)
            finally:
                self.metrics[category + "_seconds"] += time.perf_counter() - began
                self.metrics[category + "_calls"] += 1
    original = storage_run.Backend
    storage_run.Backend = TimedBackend
    machine, metadata = selected(args.profile, args.mode, "profile")
    storage_run.Backend = original
    machine.cpu.metrics = {"bus_ram_seconds": 0.0, "bus_mmio_seconds": 0.0,
                           "bus_ram_calls": 0, "bus_mmio_calls": 0,
                           "outer_api_seconds": 0.0, "api": {}}
    machine.cpu.ram_starts = [base for base, data, _ in machine.cpu.regions]
    machine.cpu.ram_ends = [base + len(data) for base, data, _ in machine.cpu.regions]
    profiler = cProfile.Profile()
    try:
        began = time.perf_counter()
        snap.run_steps(machine, args.steps)
        elapsed = time.perf_counter() - began
        metrics = copy.deepcopy(machine.cpu.metrics)
        bus = metrics["bus_ram_seconds"] + metrics["bus_mmio_seconds"]
        metrics.update({"elapsed_seconds": elapsed, "steps": args.steps,
                        "python_loop_and_device_seconds": elapsed - metrics["outer_api_seconds"],
                        "native_api_without_callbacks_seconds": metrics["outer_api_seconds"] - bus,
                        "state": snap.state_hash(machine), "instrumented": True})
        # Keep call attribution separate from the timer-based distribution.
        profiler.enable()
        trace_started = time.perf_counter()
        snap.run_steps(machine, args.steps)
        profiler.disable()
        metrics["cprofile_additional_seconds"] = time.perf_counter() - trace_started
        profiler.dump_stats(str(OUT / (args.profile + "-" + args.mode + ".pstats")))
        emit(OUT / (args.profile + "-profile-" + args.mode + ".json"), metrics)
        print(json.dumps({"steps": args.steps, "seconds": elapsed}), flush=True)
    finally:
        machine.close()
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("equivalence", "benchmark", "inputs", "identity", "profile"))
    parser.add_argument("--profile", choices=("card", "no-card"), default="no-card")
    parser.add_argument("--mode", choices=("fast", "debug"), default="fast")
    parser.add_argument("--origin", choices=("cold", "snapshot"), default="snapshot")
    parser.add_argument("--sequence", choices=("adj", "keys"), default="adj")
    parser.add_argument("--steps", type=int, default=200000)
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    command = {"equivalence": equivalence, "benchmark": benchmark, "inputs": inputs,
               "identity": identity_checks, "profile": profile_run}[args.command]
    raise SystemExit(0 if command(args) else 1)


if __name__ == "__main__":
    main()
