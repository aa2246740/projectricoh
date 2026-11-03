"""Compare batch cumulative outputs with the frozen per-step emulator_speed runs (read-only).

Same entry scripts, same inputs, same step budgets. Ignored fields: timing,
source/library identities, run names and host paths of private medium copies.
Checkpoint pickles are compared byte for byte where no host path is inside.
"""
import builtins
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import pickle

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEED = ROOT / "research/emulator_speed/local"
OUT = HERE / "local"
IGNORED = {"elapsed_sec", "sources", "library_sha256", "resume", "resume_sha256", "name",
           "medium_path", "seconds", "current_sources", "checker_sha256", "evidence_sha256",
           "path", "journal", "medium_record", "sd_journal", "started"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Reader(pickle.Unpickler):
    """Self-produced checkpoints only; the same classes input_run.CheckpointReader admits."""
    def find_class(self, module, name):
        if module == "collections" and name in ("Counter", "deque"):
            return {"Counter": Counter, "deque": deque}[name]
        if module == "builtins" and name in ("bytearray", "set", "frozenset"):
            return getattr(builtins, name)
        raise ValueError("checkpoint contains an undeclared class")


def state(path):
    with path.open("rb") as stream:
        value = Reader(stream).load()
    for kind, data in zip(value["device_types"], value["devices"]):
        if kind == "SdHost" and data.get("medium_record"):
            data["medium_record"]["path"] = "private-medium"
    return value


def strip(value):
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if k not in IGNORED}
    if isinstance(value, list):
        return [strip(v) for v in value]
    if isinstance(value, str) and ("emulator_speed" in value or "emulator_batch" in value):
        return "<private path>"
    return value


def diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        return [d for k in sorted(set(a) | set(b)) for d in diff(a.get(k), b.get(k), path + "/" + k)]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, path + "/" + str(i))]
    return [] if a == b else [path]


def main():
    pairs = ["cold", "stable", "cold-card", "reboot", "files", "full", "read-error", "write-error",
             "no-card", "readback"]
    rows = {}
    for name in pairs:
        a = json.loads((SPEED / (name + "-speed-r1.json")).read_text())
        b = json.loads((OUT / (name + "-batch-r1.json")).read_text())
        row = {"differing_fields": diff(strip(a), strip(b))[:40]}
        for suffix in ("-stop.pkl",):
            pa, pb = SPEED / (name + "-speed-r1" + suffix), OUT / (name + "-batch-r1" + suffix)
            if pa.exists() and pb.exists():
                row["checkpoint_bytes_equal"] = sha(pa) == sha(pb)
                row["checkpoint_state_equal_after_path"] = state(pa) == state(pb)
        for suffix in ("-medium.img",):
            pa, pb = SPEED / (name + "-speed-r1" + suffix), OUT / (name + "-batch-r1" + suffix)
            if pa.exists() and pb.exists():
                row["medium_bytes_equal"] = sha(pa) == sha(pb)
        rows[name] = row
    result = {"pairs": rows, "all_fields_equal": all(not r["differing_fields"] for r in rows.values())}
    (OUT / "crosscheck.json").write_text(json.dumps(result, indent=2) + "\n")
    for name, row in rows.items():
        print(name, row)


if __name__ == "__main__":
    main()
