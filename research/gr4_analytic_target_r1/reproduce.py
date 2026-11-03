"""Run the offline research in the foreground, preserving each command's logs."""
from pathlib import Path
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from mount_guard import guard
LOCAL = HERE / "local"
STEPS = [("sources", ["freeze_sources.py"]), ("integer_gamma", ["simulator.py"]),
    ("data", ["data.py"]), ("natural_modes", ["data.py", "--modes"]),
    ("validate", ["validate.py"]), ("diagnose", ["diagnose.py"]),
    ("verify", ["verify.py", "--leakage-probe"]), ("report", ["report.py"]),
    ("seal", ["verify.py", "--seal"])]


def main():
    guard()
    LOCAL.mkdir(exist_ok=True)
    for name, args in STEPS:
        command = [sys.executable, "-I", "-B", str(HERE / args[0]), *args[1:]]
        print("foreground:", name, flush=True)
        with (LOCAL / (name + ".stdout.txt")).open("w") as stdout, (LOCAL / (name + ".stderr.txt")).open("w") as stderr:
            run = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        if run.returncode:
            raise SystemExit(f"{name} failed with {run.returncode}; inspect local/{name}.stderr.txt")
    print(HERE / "REPORT.md")


if __name__ == "__main__":
    main()
