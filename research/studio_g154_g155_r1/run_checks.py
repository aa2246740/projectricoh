"""在隔离目录运行检查，保存原日志、退出码与时间回执。"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUDIO = ROOT / "studio"
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g154-g155-r1")


def main():
    name, *command = sys.argv[1:]
    if not command or not name.replace("-", "").isalnum():
        raise ValueError("需要检查名称和命令")
    volume = "/Volumes/Workspace"
    info = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", volume]))
    if (info.get("MountPoint") != volume or info.get("FilesystemType") != "apfs"
            or info.get("VolumeUUID") != "14BE04EB-AF49-497E-B36A-B078B2F7C5E8" or not info.get("WritableVolume")):
        raise RuntimeError("Workspace 卷身份、文件系统或可写状态不合格")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "TMPDIR": str(SCRATCH), "PYTHONDONTWRITEBYTECODE": "1", "GIT_OPTIONAL_LOCKS": "0",
           "UV_OFFLINE": "1", "UV_NO_SYNC": "1", "RUFF_CACHE_DIR": str(SCRATCH / "ruff"),
           "MYPY_CACHE_DIR": str(SCRATCH / "mypy"), "COVERAGE_FILE": str(SCRATCH / "coverage-data"),
           "GXR_STUDIO_HOME": str(SCRATCH / "check-home"), "GXR_STUDIO_LIBRARY": str(SCRATCH / "check-library"),
           "GXR_STUDIO_EXPORT": str(SCRATCH / "check-export"), "GXR_STUDIO_VOLUMES": str(SCRATCH / "check-volumes"),
           "PYTEST_ADDOPTS": f"--force-reruns 0 --basetemp={SCRATCH / ('pytest-' + name)} --junitxml={HERE / (name + '.xml')}"}
    env["PYTEST_ADDOPTS"] += f" --cov-report=json:{HERE / (name + '-coverage.json')}"
    wrapper = SCRATCH / "check-shell.sh"
    wrapper.write_text('#!/bin/sh\nif [ "$1" = "-c" ] && [ "$2" = "uv run --frozen lint-imports" ]; then\n'
                       f'exec uv run --frozen lint-imports --cache-dir "{SCRATCH / "import-linter"}"\nfi\nexec /bin/sh "$@"\n')
    wrapper.chmod(0o700)
    if command == ["make", "check"]:
        command.append(f"SHELL={wrapper}")
    command = ["nice", "-n", "10", *command]
    start = dt.datetime.now(dt.timezone.utc).isoformat()
    tick = time.monotonic()
    log_path = HERE / f"{name}.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(command, cwd=STUDIO, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            result = process.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            result = 124
    receipt = {"command": command, "cwd": str(STUDIO), "start_utc": start, "end_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "seconds": round(time.monotonic() - tick, 3), "exit_code": result, "timeout_seconds": 1800,
               "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(), "temporary_directory": str(SCRATCH), "reruns": 0}
    (HERE / f"{name}.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False))
    print("\n".join(log_path.read_text(errors="replace").splitlines()[-30:]))
    raise SystemExit(result)


if __name__ == "__main__":
    main()
