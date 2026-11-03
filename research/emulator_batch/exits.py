"""Returns to Python per 1,000,000 steps, by cause, from the batch cold runs."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "local"
# Each C batch ends for one reason; a following single Python step (slow-*)
# belongs to that same return. slow-deadline beyond exit-deadline are extra
# Python steps where a device needed this step before a batch could start.
COLUMNS = [
    ("deadline", lambda e: e.get("exit-deadline", 0)),
    ("deadline_extra_python_steps", lambda e: e.get("slow-deadline", 0) - e.get("exit-deadline", 0)),
    ("mmio", lambda e: e.get("forward-mmio", 0)),
    ("breakpoint", lambda e: e.get("exit-breakpoint", 0)),
    ("interrupt", lambda e: e.get("exit-irq", 0)),
    ("rte", lambda e: 0),
    ("other_write_trace_or_unmapped", lambda e: e.get("forward-other", 0)),
    ("other_fetch_outside_ram", lambda e: e.get("exit-slow-pc", 0)),
    ("other_budget", lambda e: e.get("exit-budget", 0)),
]


def add(rows):
    total = {}
    for row in rows:
        for key, value in row.items():
            total[key] = total.get(key, 0) + value
    return total


def main():
    result = {}
    for profile in ("no-card", "card"):
        run = json.loads((OUT / ("eq-batch-" + profile + ".json")).read_text())
        groups = {"boot": [s for s in run["segments"] if s["segment"] == "boot"],
                  "boot_first_1M": [s for s in run["segments"] if s["segment"] == "boot" and s["from"] == 0],
                  "adj": [s for s in run["segments"] if s["segment"].startswith("adj")]}
        for name, segments in groups.items():
            steps = sum(s["to"] - s["from"] for s in segments)
            exits = add([s["exits"] for s in segments])
            per = {column: value(exits) * 1000000 / steps for column, value in COLUMNS}
            per["total_returns"] = sum(v for k, v in per.items() if k != "deadline_extra_python_steps")
            per["mean_batch_length"] = exits.get("batch-steps", 0) / max(1, exits.get("batches", 0))
            per["python_steps_per_million"] = (steps - exits.get("batch-steps", 0)) * 1000000 / steps
            result[profile + ":" + name] = {"steps": steps, "raw": exits, "per_million": per,
                                            "seconds": sum(s["seconds"] for s in segments)}
    (OUT / "exits.json").write_text(json.dumps(result, indent=2) + "\n")
    for key, row in result.items():
        print(key, row["steps"], {k: round(v, 1) for k, v in row["per_million"].items()})


if __name__ == "__main__":
    main()
