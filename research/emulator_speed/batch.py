"""A serial work lane. Run at most two lanes, with no timer-based waiting."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "local"
sys.path.insert(0, str(HERE))
from run_existing import neutral


def jobs(lane):
    profile = "no-card" if lane == "a" else "card"
    checks = "research/emulator_speed/run_checks.py"
    cumulative = "research/emulator_speed/cumulative.py"
    rows = []
    if lane == "a":
        rows.append(["research/emulator_speed/run_existing.py", "suite"])
    rows += [[checks, "identity", "--profile", profile]]
    rows += [[checks, "equivalence", "--profile", profile, "--mode", mode] for mode in ("fast", "debug")]
    rows += [[cumulative, "boot", "--profile", profile]]
    rows += [[checks, "benchmark", "--profile", profile]]
    if lane == "a":
        rows += [[checks, "profile", "--profile", profile, "--mode", mode] for mode in ("fast", "debug")]
    rows += [[checks, "inputs", "--profile", profile, "--sequence", sequence, "--mode", mode]
             for sequence in ("adj", "keys") for mode in ("fast", "debug")]
    rows += [[checks, "inputs", "--profile", profile, "--sequence", "keys", "--origin", "cold"]]
    rows += [[checks, "inputs", "--profile", profile, "--sequence", "adj", "--origin", "cold", "--mode", "debug"]]
    if lane == "a":
        rows += [[cumulative, "files", "--case", case] for case in ("full", "read-error", "write-error", "no-card")]
        rows += [["research/emulator_speed/startup_keys.py", origin] for origin in ("snapshot", "cold")]
    else:
        rows += [[cumulative, "files", "--case", "files"], [cumulative, "restart"],
                 [cumulative, "files", "--case", "readback"], [cumulative, "model"]]
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lane", choices=("a", "b"))
    parser.add_argument("--start", type=int, default=0)
    args = parser.parse_args()
    records = []
    for index, arguments in enumerate(jobs(args.lane)):
        if index < args.start:
            continue
        users = subprocess.run(["lsof", "-t", str(ROOT / "tools/gxr_emulator/build/libgxr_m32r.dylib")],
                               capture_output=True, text=True)
        active = sorted(set(users.stdout.split()))
        if len(active) >= 2:
            raise RuntimeError("two model processes are already present; no new run started")
        started = time.monotonic()
        command = ["/usr/bin/python3", "-I", "-B", *arguments]
        print(json.dumps({"lane": args.lane, "stage": index, "command": arguments,
                          "other_model_processes": active}), flush=True)
        log = OUT / ("lane-" + args.lane + "-" + str(index) + ".log")
        with log.open("w") as stream:
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                line = neutral(line)
                stream.write(line)
                stream.flush()
                print(line, end="", flush=True)
            code = process.wait()
        records.append({"stage": index, "command": arguments, "returncode": code,
                        "seconds": time.monotonic() - started,
                        "other_model_processes_at_start": active})
        (OUT / ("lane-" + args.lane + "-results-" + str(args.start) + ".json")).write_text(
            json.dumps(records, indent=2) + "\n")
        if code:
            raise SystemExit(code)


if __name__ == "__main__":
    main()
