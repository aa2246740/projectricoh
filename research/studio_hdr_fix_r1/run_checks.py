"""Run offline checks in the foreground and preserve each run once."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
STUDIO = ROOT / "studio"
TMP = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-hdr-fix")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def environment(label):
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("GXR_STUDIO_", "SENTRY_")):
            del env[key]
    TMP.mkdir(parents=True, exist_ok=True)
    for name in ("home", "ruff", "mypy", "cache", "clang", "swift"):
        (TMP / name).mkdir(exist_ok=True)
    env.update(
        TMPDIR=str(TMP), TMP=str(TMP), TEMP=str(TMP), HOME=str(TMP / "home"),
        PYTHONDONTWRITEBYTECODE="1", UV_OFFLINE="1", UV_NO_SYNC="1",
        UV_CACHE_DIR="/Users/wu/.cache/uv", RUFF_CACHE_DIR=str(TMP / "ruff"),
        MYPY_CACHE_DIR=str(TMP / "mypy"), XDG_CACHE_HOME=str(TMP / "cache"),
        CLANG_MODULE_CACHE_PATH=str(TMP / "clang"), SWIFT_MODULECACHE_PATH=str(TMP / "swift"),
        COVERAGE_FILE=str(OUT / (label + ".coverage")), GIT_OPTIONAL_LOCKS="0",
        PYTEST_ADDOPTS=f"--basetemp={TMP / ('pytest-' + label)} --force-reruns 0",
        PYTEST_PLUGINS="hdr_fix_receipt", PYTHONPATH=str(OUT), HDR_FIX_RUN_LABEL=label,
    )
    return env


def freeze():
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=STUDIO
    ).decode().split("\0")
    files = {str(Path("studio") / n): digest(STUDIO / n) for n in names if n and (STUDIO / n).is_file()}
    for rel in ("research/review_studio_hdr", "research/studio_hdr_r1", "research/hdr_gainmap", "captures/a12-50", "captures/street-g137-20261031"):
        for path in sorted((ROOT / rel).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                files[str(path.relative_to(ROOT))] = digest(path)
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "files": files}
    receipt["head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=STUDIO).decode().strip()
    (OUT / "initial_inputs.json").write_text(json.dumps(receipt, indent=2) + "\n")
    diff = subprocess.check_output(["git", "diff", "--binary"], cwd=STUDIO)
    (OUT / "initial_worktree.diff").write_bytes(diff)
    print(json.dumps({"files": len(files), "head": receipt["head"]}))


def source_snapshot():
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=STUDIO,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    ).decode().split("\0")
    return {name: digest(STUDIO / name) for name in names if name and (STUDIO / name).is_file()}


def run(label, command):
    marker = OUT / (label + ".started.json")
    env = environment(label)
    argv = ["/usr/bin/sandbox-exec", "-f", str(OUT / "offline.sb"), "/usr/bin/nice", "-n", "10", *command]
    receipt = {"utc_start": datetime.now(timezone.utc).isoformat(), "argv": argv,
               "cwd": str(STUDIO), "reruns": 0, "timeout_seconds": 7200,
               "TMPDIR": env["TMPDIR"], "PYTEST_ADDOPTS": env["PYTEST_ADDOPTS"]}
    if label == "make_check":
        receipt["source_sha256"] = source_snapshot()
    with marker.open("x") as stream:
        json.dump(receipt, stream, indent=2)
    start = time.monotonic()
    with (OUT / (label + ".log")).open("xb") as log:
        child = subprocess.Popen(argv, cwd=STUDIO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        receipt["child_pid"] = child.pid
        try:
            assert child.stdout is not None
            import threading
            def stop():
                os.killpg(child.pid, signal.SIGTERM)
            timer = threading.Timer(7200, stop)
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
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=30)
    receipt.update(exit_code=code, seconds=round(time.monotonic() - start, 3), utc_end=datetime.now(timezone.utc).isoformat())
    if label == "make_check":
        receipt["source_unchanged"] = source_snapshot() == receipt["source_sha256"]
        if not receipt["source_unchanged"]:
            receipt["exit_code"] = code = 1
    (OUT / (label + ".result.json")).write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)
    return code


if __name__ == "__main__":
    if sys.argv[1] == "freeze":
        freeze()
    else:
        raise SystemExit(run(sys.argv[1], sys.argv[2:]))
