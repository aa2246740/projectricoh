"""Compare exact confirmation from a fast endpoint with original cold starts."""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import isolated as iso
import probe_solver as probe
from engine import Problem

rt, np = iso.rt, iso.rt.np


def main():
    folder = rt.PRIVATE / "solver_probes/neighbor-start-07-3-1"
    paired = rt.read(folder / "result.json")
    data = probe.arrays(folder / "states.npz")
    c = rt.camera_for_unit(0)
    rt.os.environ["FIT_FAST_SOLVER"] = "exact"
    rows = []
    for kind in ("fast_float_endpoint", "fast_integer_state"):
        p = Problem(c, data["x"], data["want"], data["sw"], paired["config"])
        start = data["guard_theta"].copy()
        if kind == "fast_integer_state":
            start = p.promote_integer(p, start)
        theta, status = p.solve(start, 100)
        candidates = []
        for name, value in (("refit", theta), ("initial_integer", start), ("preserved_fast", data["guard_theta"])):
            pred = p.predict_state(p.state(value, True), data["x"])
            candidates.append((probe.gate.objective(pred, data["want"], data["sw"]), name, value))
        objective, origin, value = min(candidates, key=lambda item: item[0])
        item = dict(kind=kind, objective=objective, selected=origin,
                    cold_exact_objective=paired["objectives"]["exact"],
                    delta_vs_cold_exact=objective-paired["objectives"]["exact"],
                    initial_fast_objective=paired["objectives"]["guarded_normal"],
                    status=status)
        rows.append(item)
        print(json.dumps(item), flush=True)
    iso.write("final_confirmation_probe.json", dict(rows=rows,
        interpretation="Both are genuine exact SVD solves, but neither substitutes for the original declared cold starts"))


if __name__ == "__main__":
    main()
