"""Compare per-step and batch cold runs (compare.py outputs) point by point."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "local"
rows = {}
for profile in ("no-card", "card"):
    step = json.loads((OUT / ("eq-step-" + profile + ".json")).read_text())
    batch = json.loads((OUT / ("eq-batch-" + profile + ".json")).read_text())
    points = {}
    for key in step["points"]:
        a, b = step["points"][key], batch["points"][key]
        points[key] = {"state_parts_equal": {k: a["state"][k] == b["state"][k] for k in a["state"]},
                       "observations_equal": a["observations"] == b["observations"],
                       "all": a["state"]["all"]}
    adj = {k: step["adj"][k] == batch["adj"][k]
           for k in ("state", "observations", "flow_hash", "flow_rows", "flow_counts",
                     "open_calls_hash", "panel_events_hash", "segments")}
    rows[profile] = {"points": points, "adj_equal": adj, "adj_all": batch["adj"]["state"]["all"],
                     "medium_equal": step["medium_sha256"] == batch["medium_sha256"],
                     "passed": all(all(p["state_parts_equal"].values()) and p["observations_equal"]
                                   for p in points.values()) and all(adj.values())
                               and step["medium_sha256"] == batch["medium_sha256"]}
(OUT / "equivalence.json").write_text(json.dumps(rows, indent=2) + "\n")
print(json.dumps({p: {"passed": r["passed"], "points": list(r["points"])} for p, r in rows.items()}))
