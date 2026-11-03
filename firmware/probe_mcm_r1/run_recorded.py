"""Record this integration's commands with outputs scoped to the copied tree."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "local/integration"


def main():
    label, *argv = sys.argv[1:]
    assert label and "/" not in label and argv
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = HERE / "candidate/local/tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMPDIR=str(tmp), PYTHONDONTWRITEBYTECODE="1",
               PYTHONUNBUFFERED="1", GIT_OPTIONAL_LOCKS="0",
               CLANG_MODULE_CACHE_PATH=str(tmp / "modules"),
               ASAN_OPTIONS="detect_leaks=0:halt_on_error=1",
               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    start = time.monotonic()
    print("START", label, flush=True)
    with (OUT / (label + ".stdout")).open("w") as stdout, (OUT / (label + ".stderr")).open("w") as stderr:
        p = subprocess.run(argv, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, timeout=2400)
    record = dict(label=label, argv=argv, returncode=p.returncode,
                  seconds=round(time.monotonic() - start, 3))
    with (OUT / "executions.jsonl").open("a") as f:
        f.write(json.dumps(record) + "\n")
    print(json.dumps(record), flush=True)
    for suffix in ("stdout", "stderr"):
        value = (OUT / (label + "." + suffix)).read_text()
        print(value if len(value) < 5000 else value[-5000:], end="", flush=True)
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
