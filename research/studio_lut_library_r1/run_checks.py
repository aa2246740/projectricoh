"""离线前台检查：保留命令、输出、源码哈希和退出状态。"""

import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
STUDIO = ROOT / "studio"
TMP = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-lut")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    files = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=STUDIO).decode().split("\0")
    return {name: digest(STUDIO / name) for name in files if name and (STUDIO / name).is_file()}


def run(label, command):
    for name in ("home", "ruff", "mypy", "cache", "clang", "swift"):
        (TMP / name).mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GXR_STUDIO_", "SENTRY_"))}
    env.update(
        TMPDIR=str(TMP), TMP=str(TMP), TEMP=str(TMP), HOME=str(TMP / "home"), PYTHONDONTWRITEBYTECODE="1",
        UV_OFFLINE="1", UV_NO_SYNC="1", UV_CACHE_DIR="/Users/wu/.cache/uv", GIT_OPTIONAL_LOCKS="0",
        RUFF_CACHE_DIR=str(TMP / "ruff"), MYPY_CACHE_DIR=str(TMP / "mypy"), XDG_CACHE_HOME=str(TMP / "cache"),
        CLANG_MODULE_CACHE_PATH=str(TMP / "clang"), SWIFT_MODULECACHE_PATH=str(TMP / "swift"),
        COVERAGE_FILE=str(OUT / f"{label}.coverage"), PYTEST_ADDOPTS=f"--basetemp={TMP / ('pytest-' + label)} --force-reruns 0",
        PYTEST_PLUGINS="lut_receipt", PYTHONPATH=str(OUT), LUT_CHECK_LABEL=label,
    )
    argv = ["/usr/bin/sandbox-exec", "-f", str(OUT / "offline.sb"), "/usr/bin/nice", "-n", "10", *command]
    record = {"argv": argv, "cwd": str(STUDIO), "utc_start": datetime.now(timezone.utc).isoformat(),
              "TMPDIR": str(TMP), "force_reruns": 0, "source_sha256": snapshot()}
    with (OUT / f"{label}.started.json").open("x") as stream:
        json.dump(record, stream, indent=2)
    started = time.monotonic()
    with (OUT / f"{label}.log").open("xb") as log:
        child = subprocess.Popen(argv, cwd=STUDIO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        timer = threading.Timer(7200, lambda: os.killpg(child.pid, signal.SIGTERM))
        timer.start()
        try:
            for line in child.stdout:
                log.write(line)
                log.flush()
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
            code = child.wait(timeout=30)
        finally:
            timer.cancel()
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=30)
    record["process_exit_code"] = code
    expects_tests = ("pytest" in command and "--collect-only" not in command) or (
        Path(command[0]).name == "make" and any(target in command[1:] for target in ("check", "test"))
    )
    if code == 0 and expects_tests:
        receipts = list(OUT.glob(f"{label}_pytest_*.json"))
        if len(receipts) != 1 or json.loads(receipts[0].read_text())["exit_code"] != 0:
            record["validation_error"] = "缺少正常结束的 pytest 收据"
            code = 1
    record.update(exit_code=code, seconds=round(time.monotonic() - started, 3), utc_end=datetime.now(timezone.utc).isoformat(),
                  source_unchanged=snapshot() == record["source_sha256"])
    (OUT / f"{label}.result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: v for k, v in record.items() if k != "source_sha256"}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1], sys.argv[2:]))
