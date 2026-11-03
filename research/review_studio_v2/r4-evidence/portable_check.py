"""Run pytest on a source-only v2 snapshot with no adjacent private fixtures.

This is a macOS source-isolation check, not a remote Linux CI execution.
Dependencies are reused without changing the active virtual environment.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from run_checks import manifest

HERE = Path(__file__).resolve().parent
STUDIO = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio')
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r4")


def main():
    snapshot = SCRATCH / "source-only/studio"
    snapshot.mkdir(parents=True, exist_ok=True)
    for name in manifest():
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(STUDIO / name, target)
    env = os.environ.copy()
    env.update(TMPDIR=str(SCRATCH), PYTHONPATH=str(snapshot / "src"), PYTHONDONTWRITEBYTECODE="1",
               COVERAGE_FILE=str(SCRATCH / "portable.coverage"))
    env.pop("PYTEST_ADDOPTS", None)
    python = str(STUDIO / ".venv/bin/python")
    module = subprocess.check_output([python, "-B", "-c", "import gxr_studio;print(gxr_studio.__file__)"], cwd=snapshot, env=env, text=True).strip()
    assert module.startswith(str(snapshot / "src")), module
    command = [python, "-B", "-m", "pytest", "-q", "--durations=10", "--reruns", "1", "--cov=gxr_studio",
               "-o", f"cache_dir={SCRATCH / 'portable-cache'}", "--cov-report=term-missing", "--cov-fail-under=85", f"--basetemp={SCRATCH / 'portable-pytest'}",
               f"--junitxml={HERE / 'portable.junit.xml'}"]
    start = time.monotonic()
    with (HERE / "portable.log").open("w") as out:
        result = subprocess.run(command, cwd=snapshot, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=1800)
    summary = {"module": module, "exit_code": result.returncode, "seconds": round(time.monotonic() - start, 2),
               "private_siblings_present": any((snapshot.parent / name).exists() for name in ("firmware", "captures", "research"))}
    (HERE / "portable.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)
    print((HERE / "portable.log").read_text()[-2500:], flush=True)


if __name__ == "__main__":
    main()
