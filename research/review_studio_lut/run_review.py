"""Run each check once in the foreground, with bounded time and a fixed write scope."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
STUDIO = ROOT / "studio"
TMP = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-lut")

def snapshot():
    names = subprocess.check_output(["git", "--no-optional-locks", "-C", str(STUDIO), "ls-files", "-co", "--exclude-standard", "-z"]).decode().split("\0")
    return {name: hashlib.sha256((STUDIO/name).read_bytes()).hexdigest() for name in sorted(set(names)) if name and (STUDIO/name).is_file()}

def run(label, command):
    for name in ("bin", "ruff", "mypy", "cache", "uv", "clang", "swift", "pylint"):
        (TMP/name).mkdir(parents=True, exist_ok=True)
    env = {k:v for k,v in os.environ.items() if not k.startswith(("GXR_STUDIO_", "SENTRY_", "PYTEST_", "COVERAGE_"))}
    env.update(TMPDIR=str(TMP), TMP=str(TMP), TEMP=str(TMP), PYTHONDONTWRITEBYTECODE="1",
        UV_OFFLINE="1", UV_NO_SYNC="1", UV_CACHE_DIR=str(TMP/"uv"), UV_PYTHON_DOWNLOADS="never",
        GIT_OPTIONAL_LOCKS="0", RUFF_CACHE_DIR=str(TMP/"ruff"), MYPY_CACHE_DIR=str(TMP/"mypy"),
        XDG_CACHE_HOME=str(TMP/"cache"), CLANG_MODULE_CACHE_PATH=str(TMP/"clang"),
        SWIFT_MODULECACHE_PATH=str(TMP/"swift"), PYLINTHOME=str(TMP/"pylint"),
        COVERAGE_FILE=str(OUT/(label+".coverage")),
        PYTEST_ADDOPTS="--basetemp="+str(TMP/("pytest-"+label))+" --force-reruns 0",
        PYTEST_PLUGINS="review_receipt", PYTHONPATH=str(OUT), REVIEW_LABEL=label,
        REVIEW_TMP=str(TMP), PATH=str(TMP/"bin")+":"+os.environ["PATH"],
        OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1")
    argv = ["/usr/bin/sandbox-exec", "-f", str(OUT/"offline.sb"), "/usr/bin/nice", "-n", "10", *command]
    receipt = {"argv":argv, "cwd":str(STUDIO), "utc_start":datetime.now(timezone.utc).isoformat(),
        "timeout_seconds":3600, "TMPDIR":str(TMP), "force_reruns":0,
        "cache_override":"lint-imports receives only --cache-dir under the allowed temporary directory",
        "source_before":snapshot()}
    with (OUT/(label+".started.json")).open("x") as f:
        json.dump(receipt,f,indent=2)
    started=time.monotonic()
    with (OUT/(label+".log")).open("xb") as f:
        child=subprocess.Popen(argv,cwd=STUDIO,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
        timer=threading.Timer(3600, lambda: os.killpg(child.pid,signal.SIGTERM))
        timer.start()
        try:
            for line in child.stdout:
                f.write(line); f.flush()
                sys.stdout.buffer.write(line); sys.stdout.buffer.flush()
            code=child.wait(timeout=30)
        finally:
            timer.cancel()
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGTERM)
                child.wait(timeout=30)
    receipt.update(exit_code=code,seconds=round(time.monotonic()-started,3),
        utc_end=datetime.now(timezone.utc).isoformat(),source_unchanged=snapshot()==receipt["source_before"])
    with (OUT/(label+".result.json")).open("x") as f:
        json.dump(receipt,f,indent=2);f.write("\n")
    print(json.dumps({k:v for k,v in receipt.items() if k!="source_before"}),flush=True)
    return code

if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1],sys.argv[2:]))
