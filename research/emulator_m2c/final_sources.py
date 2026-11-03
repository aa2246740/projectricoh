"""Bind current file checks to the original restart chain and native results."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
PAIRS = (
    ("files-acceptance-r2", "files-delivery-r1"),
    ("full-acceptance-r1", "full-delivery-r2"),
    ("read-error-acceptance-r1", "read-error-delivery-r1"),
    ("no-card-acceptance-r1", "no-card-delivery-r1"),
)


def read(name):
    return json.loads((OUT / (name + ".json")).read_text())


def calls(case):
    fields = ("name", "address", "args", "task", "psw", "start_step", "end_step",
              "result", "return_task", "semaphore47_before", "semaphore47_after",
              "native_file_path")
    return [{key: row.get(key) for key in fields} for row in case["calls"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().parent != OUT:
        raise ValueError("use a fresh M2c local result")
    current = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in (ROOT / "tools/gxr_emulator").glob("*.py")}
    pairs = []
    for prior_name, final_name in PAIRS:
        prior, final = read(prior_name), read(final_name)
        checks = {
            "passed": prior["status"] == final["status"] == "passed",
            "current_sources": final["sources"] == current,
            "same_native_calls": calls(prior) == calls(final),
            "same_native_events": prior["events"] == final["events"],
            "same_file_result": all(prior.get(key) == final.get(key) for key in
                                    ("read", "read_close", "written", "write_close",
                                     "create_result", "open_result", "medium")),
        }
        pairs.append({"prior": prior_name, "final": final_name, "checks": checks})
    additional = {}
    for name in ("write-error-acceptance-r3", "readback-acceptance-r2"):
        case = read(name)
        additional[name] = case["status"] == "passed" and case["sources"] == current
    reboot = read("reboot-read-acceptance-r1-restart")
    same_bytes = read("files-delivery-r1")["medium"]["image_sha256"] == reboot["before"]["image_sha256"]
    passed = all(all(row["checks"].values()) for row in pairs) and all(additional.values()) and same_bytes
    result = {"status": "passed" if passed else "incomplete", "pairs": pairs,
              "current_additional_cases": additional, "same_restart_input_bytes": same_bytes,
              "source_hashes": current,
              "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key not in ("source_hashes", "checker_sha256")}))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
