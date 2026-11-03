"""Repeat the existing M2d nine-key window at the original startup stage."""
import argparse
import copy
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "local"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools/gxr_emulator"))
from scope_guard import enable
enable()
import speed_snapshot as snap
from input_run import CheckpointReader, Flow
from storage_run import Machine, sources
from run_existing import load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin", choices=("snapshot", "cold"))
    args = parser.parse_args()
    source = OUT / "stable-speed-r1-stop.pkl"
    metadata = json.loads(source.with_suffix(".json").read_text())
    if snap.sha(source) != metadata["sha256"] or metadata["source_hashes"] != sources():
        raise ValueError("startup checkpoint identity differs")
    if snap.sha(ROOT / "tools/gxr_emulator/build/libgxr_m32r.dylib") != metadata["library_sha256"]:
        raise ValueError("startup library identity differs")
    with source.open("rb") as stream:
        state = CheckpointReader(stream).load()
    machine = Machine()
    snap.attach_panel(machine)
    machine.cpu.set_mode("fast")
    started = time.monotonic()
    try:
        if args.origin == "cold":
            while machine.cpu.steps < state["steps"]:
                snap.run_steps(machine, min(1000000, state["steps"] - machine.cpu.steps))
                print(json.dumps({"startup_cold_steps": machine.cpu.steps}), flush=True)
        else:
            machine.cpu.restore(copy.deepcopy(state))
        initial_equal = snap.value_hash(machine.cpu.snapshot()) == snap.value_hash(state)
        if not initial_equal:
            raise ValueError("startup stage state differs")
        flow = Flow(machine)
        segments = []
        for key in ("ADJ", "OK", "DISP", "UP", "DOWN", "LEFT", "RIGHT", "HALF", "FULL"):
            for down, count in ((True, 300000), (False, 600000)):
                machine.panel.set_key(key, down)
                stop = snap.run_steps(machine, count)
                segments.append({"key": key, "down": down, "stop": stop.to_dict()})
        target = OUT / ("startup-keys-" + args.origin + ".json")
        result = {"origin": args.origin, "initial_equal": initial_equal,
                  "checkpoint_sha256": metadata["sha256"], "start_step": state["steps"],
                  "end_step": machine.cpu.steps, "state": snap.state_hash(machine),
                  "flow": flow.rows, "flow_hash": snap.value_hash(flow.rows),
                  "segments": segments, "seconds": time.monotonic() - started,
                  "driver_sha256": snap.sha(Path(__file__)),
                  "source": "original startup-stage M2d key window"}
        target.write_text(json.dumps(result, indent=2) + "\n")
        verifier = load(ROOT / "research/emulator_m2d/milestone.py")
        codes = {"ADJ": 23, "OK": 24, "DISP": 21, "UP": 15, "DOWN": 18,
                 "LEFT": 17, "RIGHT": 16, "HALF": 13, "FULL": 14}
        phases = {}
        for key, code in codes.items():
            values = verifier.producer(flow.rows, code)
            phases[key] = values if all(isinstance(x, int) for x in values) else [r["args"][3] for r in values]
        result.update({"phases": phases,
                       "phases_equal_expected": all(v == [1, 129, 0] for v in phases.values())})
        target.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"origin": args.origin, "phase_count": sum(map(len, phases.values())),
                          "expected": result["phases_equal_expected"]}), flush=True)
        return result["phases_equal_expected"]
    finally:
        machine.close()


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
