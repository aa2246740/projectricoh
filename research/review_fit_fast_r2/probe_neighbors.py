"""Reproduce the discovered case, then search its nearby declared starts."""
import argparse
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="start-07-3")
    ap.add_argument("--index", type=int, default=7)
    ap.add_argument("--limit", type=int, default=64)
    ap.add_argument("--replay-only", action="store_true")
    ap.add_argument("--label", default="replay")
    args = ap.parse_args()
    folder = rt.PRIVATE / "solver_probes" / args.case
    old = rt.read(folder / "result.json")
    data = probe.arrays(folder / "states.npz")
    meta = rt.read(rt.SOURCE_LOCAL / f"target_{args.index:02d}.json")
    c = rt.camera_for_unit(meta.get("camera_ui", 0))
    rt.os.environ.pop("FIT_FAST_RCOND_FLOOR", None)
    rt.os.environ["FIT_FAST_GUARD_FACTOR"] = "normal"
    rng = np.random.default_rng(2026110302)
    rows = []
    count = 2 if args.replay_only else args.limit
    for number in range(count):
        start = data["start"].copy()
        if not args.replay_only and number:
            p = Problem(c, data["x"], data["want"], data["sw"], old["config"])
            scale = (.0001, .001, .01, .1, 1., 4.)[number % 6]
            start[p.qstart:p.qend] += rng.normal(0, scale, p.qend-p.qstart)
            start[:2] += rng.normal(0, .0001*scale, 2)
            start = np.clip(start, np.array(p.lower)+1e-8, np.array(p.upper)-1e-8)
        name = ((args.label+"-") if args.replay_only else "neighbor-") + args.case + "-" + str(number)
        row = probe.one(name, old["config"], c, data["x"], data["want"], data["sw"], start,
                        data.get("fallback"), old["nfev"])
        rows.append(row)
        if row["training_regression"]:
            break
    iso.write(((args.label+"s_") if args.replay_only else "neighbors_")+args.case+".json",
              dict(cases=len(rows), regressions=sum(r["training_regression"] for r in rows),
                   prediction_differences=sum(not r["prediction_equal"] for r in rows), rows=rows))


if __name__ == "__main__":
    main()
