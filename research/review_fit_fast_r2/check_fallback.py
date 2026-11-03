"""Force each numerical rejection and check a fresh exact restart from x0."""
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import isolated as iso
import probe_solver as probe
import guarded
from engine import Problem

rt, np = iso.rt, iso.rt.np


def main():
    folder = rt.PRIVATE / "solver_probes/start-07-3"
    row = rt.read(folder / "result.json")
    data = probe.arrays(folder / "states.npz")
    c = rt.camera_for_unit(0)
    config = row["config"]
    rt.os.environ.pop("FIT_FAST_RCOND_FLOOR", None)
    rt.os.environ["FIT_FAST_GUARD_FACTOR"] = "normal"
    rt.os.environ["FIT_FAST_SOLVER"] = "exact"
    p = Problem(c, data["x"], data["want"], data["sw"], config)
    expected, reference_status = p.solve(data["start"], 100)
    rows = []
    original_eigh = guarded.la.eigh
    original_exact = guarded.least_squares
    for kind, trigger in (("rcond", 1), ("rcond", 3), ("backward", 1)):
        calls, fallbacks = [0], []
        def eig(*args, **kwargs):
            values, vectors = original_eigh(*args, **kwargs)
            calls[0] += 1
            if calls[0] == trigger:
                if kind == "rcond":
                    values[0] = -abs(values[-1])
                else:
                    vectors[0, 0] += .001
            return values, vectors
        def exact(fun, start, **kwargs):
            fallbacks.append(start.copy())
            return original_exact(fun, start, **kwargs)
        rt.os.environ["FIT_FAST_SOLVER"] = "guarded_normal"
        p = Problem(c, data["x"], data["want"], data["sw"], config)
        with patch.object(guarded.la, "eigh", eig), patch.object(guarded, "least_squares", exact):
            actual, status = p.solve(data["start"].copy(), 100)
        assert len(fallbacks) == 1
        assert np.array_equal(fallbacks[0], data["start"])
        assert np.array_equal(actual, expected)
        item = dict(kind=kind, rejected_factor=trigger, actual_factor_calls=calls[0],
                    original_start_used=True, exact_endpoint_equal=True,
                    exact_cost=reference_status["cost"], restarted_cost=status["cost"])
        rows.append(item)
        print(json.dumps(item), flush=True)
    def failed_eigh(*args, **kwargs):
        raise guarded.la.LinAlgError("Review-injected LAPACK convergence failure")
    p = Problem(c, data["x"], data["want"], data["sw"], config)
    try:
        with patch.object(guarded.la, "eigh", failed_eigh):
            p.solve(data["start"].copy(), 100)
    except guarded.la.LinAlgError as exc:
        convergence_failure = dict(fallback=False, fails_loudly=True, error=str(exc))
    else:
        raise AssertionError("Injected LAPACK failure unexpectedly succeeded")
    result = dict(passed=True, rejection_cases=rows, lapack_failure=convergence_failure,
                  source_sha256=iso.sha(Path(guarded.__file__)))
    iso.write("fallback_checks.json", result)
    print(json.dumps(dict(passed=True, condition_cases=len(rows), lapack_failure=convergence_failure)), flush=True)


if __name__ == "__main__":
    main()
