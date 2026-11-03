"""Confirm the counterexample with the frozen, unaccelerated reference class."""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import isolated as iso
import probe_solver as probe
from engine import reference

rt, np = iso.rt, iso.rt.np


def main():
    source = rt.PRIVATE / "solver_probes/neighbor-start-07-3-1"
    row = rt.read(source / "result.json")
    data = probe.arrays(source / "states.npz")
    p = reference.Problem(rt.camera_for_unit(0), data["x"], data["want"], data["sw"], row["config"])
    theta, status = p.solve(data["start"].copy(), 100)
    candidates = []
    for name, value in (("refit", theta), ("initial_integer", data["start"]), ("parent_integer", data["fallback"])):
        prediction = p.predict_state(p.state(value, True), data["x"])
        objective = probe.gate.objective(prediction, data["want"], data["sw"])
        candidates.append((objective, name, value, prediction))
    objective, origin, selected, prediction = min(candidates, key=lambda row: row[0])
    noise = probe.gate.objective_noise(prediction, data["want"], data["sw"], objective)[1]
    result = dict(original_reference_objective=objective, original_reference_selected=origin,
                  accelerated_exact_objective=row["objectives"]["exact"],
                  guarded_normal_objective=row["objectives"]["guarded_normal"],
                  guarded_objective_increase=row["objectives"]["guarded_normal"]-objective,
                  training_noise=noise, reference_status=status,
                  original_and_accelerated_exact_predictions_equal=bool(np.array_equal(prediction, data["exact_prediction"])),
                  original_and_accelerated_exact_theta_max_difference=float(abs(selected-data["exact_theta"]).max()),
                  reference_class_source_sha256=iso.sha(Path(reference.__file__)))
    iso.write("counterexample_original_reference.json", result)
    np.savez_compressed(rt.PRIVATE / "counterexample_original_reference.npz", theta=selected, prediction=prediction)
    assert result["guarded_objective_increase"] > noise
    assert result["original_and_accelerated_exact_predictions_equal"]
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
