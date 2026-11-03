"""在指定本地边界内前台运行检查，并保留退出码与用时。"""

import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import time

OUT = Path(__file__).resolve().parent
BASE = OUT.parent.parent
REPO = BASE / "studio"
TEMP = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-a1a-r3")


def environment(run_name="make-check"):
    env = dict(os.environ)
    for name in tuple(env):
        if name.startswith("GXR_STUDIO_"):
            env.pop(name)
    env.update(
        HOME=str(TEMP / "home"),
        TMPDIR=str(TEMP),
        TMP=str(TEMP),
        TEMP=str(TEMP),
        XDG_CACHE_HOME=str(TEMP / "cache"),
        UV_OFFLINE="1",
        UV_NO_SYNC="1",
        UV_CACHE_DIR=str(TEMP / "uv"),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUNBUFFERED="1",
        PYTHONPATH=str(OUT) + os.pathsep + str(REPO / "src"),
        MYPY_CACHE_DIR=str(TEMP / "mypy"),
        RUFF_CACHE_DIR=str(TEMP / "ruff"),
        COVERAGE_FILE=str(OUT / ".coverage"),
        IMPORT_LINTER_CACHE_DIR=str(TEMP / "imports"),
        GIT_OPTIONAL_LOCKS="0",
        PYTEST_ADDOPTS=f"--basetemp={TEMP / ('pytest-' + run_name)} -p review_results -rR --junitxml={OUT / (run_name + '.xml')}",
        PATH=str(TEMP / "bin") + os.pathsep + env["PATH"],
    )
    return env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--timeout", type=int, default=2700)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    started = time.monotonic()
    receipt = {
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "command": command,
        "timeout_seconds": args.timeout,
        "priority": 10,
        "cwd": str(REPO),
    }
    with (OUT / f"{args.name}.log").open("w") as log:
        log.write(json.dumps(receipt, ensure_ascii=False) + "\n")
        log.flush()
        try:
            result = subprocess.run(
                ["/usr/bin/nice", "-n", "10", "/usr/bin/sandbox-exec", "-f", str(OUT / "local.sb"), *command],
                cwd=REPO,
                env=dict(environment(args.name), REVIEW_RUN_NAME=args.name),
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=args.timeout,
                check=False,
            )
            receipt["exit_code"] = result.returncode
        except subprocess.TimeoutExpired:
            receipt["exit_code"] = 124
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        log.write("\n" + json.dumps(receipt, ensure_ascii=False) + "\n")
    (OUT / f"{args.name}-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
