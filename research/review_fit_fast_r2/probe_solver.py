"""Paired real-model solves on declared, deterministic out-of-corpus starts.

All fits are independent and serial within this process. -I -B, nice 15.
This script never copies a previous full-field final solution as an answer.
"""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import isolated as iso
from isolated import rt
from engine import Problem, reference

np = rt.np
gate = iso.gate_module()


def arrays(path):
    with np.load(path, allow_pickle=False) as values:
        return dict(values)


def one(case, config, c, x, want, sw, start, fallback, nfev):
    statuses, states, objectives, costs, solutions = {}, {}, {}, {}, {}
    begin = {"case": case, "config": config, "nfev": nfev,
             "x_sha256": rt.hashlib.sha256(x.tobytes()).hexdigest(),
             "want_sha256": rt.hashlib.sha256(want.tobytes()).hexdigest(),
             "start_sha256": rt.hashlib.sha256(start.tobytes()).hexdigest()}
    for mode in ("exact", "guarded_normal"):
        rt.os.environ["FIT_FAST_SOLVER"] = mode
        p = Problem(c, x, want, sw, config)
        theta, status = p.solve(start.copy(), nfev)
        seed_options = [("refit", theta), ("initial_integer", start)]
        if fallback is not None:
            seed_options.append(("parent_integer", fallback))
        candidates = []
        for origin, value in seed_options:
            pred = p.predict_state(p.state(value, True), x)
            candidates.append((gate.objective(pred, want, sw), origin, value, pred))
        objective, origin, value, pred = min(candidates, key=lambda row: row[0])
        statuses[mode] = dict(status, selected_origin=origin)
        states[mode] = pred
        objectives[mode] = objective
        costs[mode] = status["cost"]
        solutions[mode] = value
    _, tolerance, noise = gate.objective_noise(states["exact"], want, sw, objectives["exact"])
    stats = sorted((rt.LOCAL / "condition_statistics").glob("*/*.json"), key=lambda q: q.stat().st_mtime_ns)
    trace = rt.read(stats[-1]) if stats else None
    row = dict(begin, objectives=objectives, continuous_cost=costs, objective_noise=tolerance,
               objective_delta=objectives["guarded_normal"]-objectives["exact"],
               prediction_equal=bool(np.array_equal(states["exact"], states["guarded_normal"])),
               statuses=statuses, condition=trace,
               theta_max_difference=float(np.max(abs(solutions["exact"]-solutions["guarded_normal"]))))
    row["training_regression"] = row["objective_delta"] > tolerance
    folder = rt.PRIVATE / "solver_probes" / case
    folder.mkdir(parents=True, exist_ok=True)
    rt.dump(folder / "result.json", row)
    np.savez_compressed(folder / "states.npz", x=x, want=want, sw=sw, start=start,
                        exact_theta=solutions["exact"], guard_theta=solutions["guarded_normal"],
                        exact_prediction=states["exact"], guard_prediction=states["guarded_normal"],
                        **({"fallback": fallback} if fallback is not None else {}))
    print(json.dumps({key: row[key] for key in ("case", "objective_delta", "objective_noise", "prediction_equal", "training_regression")}, ensure_ascii=False), flush=True)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=("starts", "redo"), default="starts")
    ap.add_argument("--limit", type=int, default=48)
    ap.add_argument("--nfev", type=int, default=100)
    args = ap.parse_args()
    rows = []
    rt.os.environ.pop("FIT_FAST_RCOND_FLOOR", None)
    rt.os.environ["FIT_FAST_GUARD_FACTOR"] = "normal"
    rng = np.random.default_rng(2026110301)
    configs = [cfg for cfg in reference.variants() if cfg["level"] == 2]
    if args.kind == "starts":
        for index in (0, 1, 6, 7, 20, 29, 35, 36, 37, 38, 43, 44, 45, 46, 50):
            meta = rt.read(rt.SOURCE_LOCAL / f"target_{index:02d}.json")
            data = arrays(rt.SOURCE_LOCAL / f"target_{index:02d}.npz")
            train = arrays(rt.SOURCE_LOCAL / meta.get("group_files", {}).get("train", "samples_train.npz"))
            c = rt.camera_for_unit(meta.get("camera_ui", 0))
            x, want, sw = train["x"], data["train_target"], train["sw"]
            for k, original in enumerate(configs):
                config = dict(original, key=original["key"] + "_fullfields", full_fields=True)
                p = Problem(c, x, want, sw, config)
                daily = rt.read(rt.SOURCE_LOCAL / "fits" / f"{index:02d}" / (original["key"] + ".json"))
                start = np.asarray(daily["theta"]).copy()
                # Perturb curve ordinates and the ordinary core; stay inside the declared box.
                start[p.qstart:p.qend] += rng.normal(0, (0.02, 0.2, 2., 8.)[k], p.qend-p.qstart)
                start[:2] += rng.normal(0, .005, 2)
                start = np.clip(start, np.array(p.lower)+1e-8, np.array(p.upper)-1e-8)
                parent_doc = rt.read(rt.SOURCE_LOCAL / "fits" / f"{index:02d}" / "L1.json")
                parent = Problem(c, x, want, sw, dict(key="L1", level=1))
                fallback = p.promote_integer(parent, np.asarray(parent_doc["theta"]))
                rows.append(one(f"start-{index:02d}-{k}", config, c, x, want, sw, start, fallback, args.nfev))
                if len(rows) >= args.limit:
                    break
            if len(rows) >= args.limit:
                break
    else:
        # These targets have new per-unit input domains and 839 training points.
        for ui, unit in enumerate(("a12-50", "a12-28", "mount-a12")):
            for index in (0, 3, 4, 5, 12, 20, 31, 34):
                base = rt.ROOT / "research/recipe_redo_r1/local/targets" / unit
                data = arrays(base / f"{index:02d}_train.npz")
                meta = rt.read(base / f"{index:02d}.json")
                c = rt.camera_for_unit(ui)
                # Use the published row matrix as recipe-redo does; unit colour
                # calibration remains the frozen fit-fast model in this probe.
                import copy
                c = copy.copy(c)
                c.row = rt.mm.MatrixRow.from_bytes(bytes.fromhex(meta["template_hex"])[216:244])
                original = configs[(index+ui) % len(configs)]
                config = dict(original, key=original["key"]+"_redo_probe_fullfields", full_fields=True)
                p = Problem(c, data["x"], data["want"], data["sw"], config)
                start = p.theta0.copy()
                rows.append(one(f"redo-{ui}-{index:02d}", config, c, data["x"], data["want"], data["sw"], start, None, args.nfev))
                if len(rows) >= args.limit:
                    break
            if len(rows) >= args.limit:
                break
    iso.write(f"solver_{args.kind}_summary.json", dict(cases=len(rows),
        regressions=sum(row["training_regression"] for row in rows),
        prediction_differences=sum(not row["prediction_equal"] for row in rows),
        no_restart=sum(not row["condition"]["svd_restart"] for row in rows), rows=rows))


if __name__ == "__main__":
    main()
