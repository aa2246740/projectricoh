"""Alternating cold-start throughput: per-step vs batch, MAIN to 5,000,000 steps, no card.

Each run is a separate compare.py process (one model process at a time).
"""
import json
from pathlib import Path
import statistics
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "local"
STEPS = 5000000


def main():
    runs = []
    for repeat in range(3):
        for impl in ("step", "batch") if repeat % 2 == 0 else ("batch", "step"):
            name = "bench-%s-%d" % (impl, repeat)
            subprocess.run([str(HERE / "limit.sh"), "1200", str(OUT / (name + ".log")),
                            "/usr/bin/python3", "-I", "-B", str(HERE / "compare.py"), "--impl", impl,
                            "--profile", "no-card", "--name", name, "--points", str(STEPS)],
                           cwd=ROOT, check=True)
            data = json.loads((OUT / (name + ".json")).read_text())
            segment = data["segments"][0]
            runs.append({"impl": impl, "repeat": repeat, "run_seconds": segment["seconds"],
                         "steps_per_second": segment["steps_per_second"],
                         "setup_seconds": data["setup_seconds"],
                         "state": data["points"][str(STEPS)]["state"]["all"],
                         "load": subprocess.check_output(["uptime"], text=True).strip()})
            print(json.dumps(runs[-1]), flush=True)
    result = {"steps": STEPS, "profile": "no-card", "origin": "MAIN", "runs": runs,
              "same_state": len({r["state"] for r in runs}) == 1}
    for impl in ("step", "batch"):
        values = [r["steps_per_second"] for r in runs if r["impl"] == impl]
        result[impl] = {"median": statistics.median(values), "min": min(values), "max": max(values)}
    result["ratio"] = result["batch"]["median"] / result["step"]["median"]
    (OUT / "bench.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("step", "batch", "ratio", "same_state")}))


if __name__ == "__main__":
    main()
