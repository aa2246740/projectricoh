"""Run the requested existing checks by path, with isolated result files."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
PYTHON = ["/usr/bin/python3", "-I", "-B"]


def main():
    name = sys.argv[1]
    target = OUT / (name + ".json")
    if target.exists():
        raise ValueError("regression name already exists")
    checks = [
        ("board_checks", ["tools/gxr_emulator/board_checks.py", "--output", str(OUT / (name + "-board.json"))]),
        ("m2_checks", ["tools/gxr_emulator/m2_checks.py", "--checkpoints"]),
        ("rpc_check", ["tools/gxr_emulator/rpc_check.py"]),
        ("conformance", ["tools/gxr_emulator/conformance.py", "--backend", "gnu"])]
    rows = []
    for check, args in checks:
        started = time.monotonic()
        command = PYTHON + args
        with (OUT / (name + "-" + check + ".stdout")).open("wb") as stdout, \
             (OUT / (name + "-" + check + ".stderr")).open("wb") as stderr:
            process = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        row = {"check": check, "command": command, "returncode": process.returncode,
               "elapsed_sec": round(time.monotonic() - started, 3)}
        rows.append(row)
        print(json.dumps(row), flush=True)
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((ROOT / "tools/gxr_emulator").glob("*.py"))}
    target.write_text(json.dumps({"checks": rows, "sources": hashes}, indent=2) + "\n")
    return int(any(row["returncode"] != 0 for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
