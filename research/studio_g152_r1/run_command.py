"""有时限的前台检查；日志和退出回执只写本报告目录。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or not args.name.replace("-", "").replace("_", "").isalnum():
        parser.error("请指定检查名称和命令")
    started = time.time()
    log_path = HERE / f"{args.name}.log"
    timed_out = False
    with log_path.open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            result = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            result = 124
    receipt = {
        "name": args.name, "command": command, "cwd": str(Path.cwd()),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "seconds": round(time.time() - started, 3), "exit_code": result, "timeout": timed_out,
        "nice": os.getpriority(os.PRIO_PROCESS, 0),
        "log": log_path.name, "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
    }
    (HERE / f"{args.name}.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    print(log_path.read_text(errors="replace")[-6000:], flush=True)
    raise SystemExit(result)


if __name__ == "__main__":
    main()
