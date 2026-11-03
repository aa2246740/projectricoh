"""Run repository checks without changing tracked files or using default temp paths."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
STUDIO = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio')
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r4")


def manifest() -> dict[str, str]:
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=STUDIO
    ).decode().split("\0")
    return {name: hashlib.sha256((STUDIO / name).read_bytes()).hexdigest()
            for name in sorted(set(names)) if name and (STUDIO / name).is_file()}


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE="1",
               PYTEST_ADDOPTS=f"--basetemp={SCRATCH / 'pytest'} --junitxml={HERE / 'checks.junit.xml'} -o cache_dir={SCRATCH / 'pytest-cache'}",
               COVERAGE_FILE=str(SCRATCH / ".coverage"), UV_NO_SYNC="1", UV_CACHE_DIR=str(SCRATCH / "uv"),
               RUFF_CACHE_DIR=str(SCRATCH / "ruff"), MYPY_CACHE_DIR=str(SCRATCH / "mypy"))
    before = manifest()
    (HERE / "source_manifest.json").write_text(json.dumps(before, indent=2) + "\n")
    makefile = SCRATCH / "Makefile.acceptance"
    source_makefile = (STUDIO / "Makefile").read_text()
    assert "uv run --frozen lint-imports\n" in source_makefile
    assert "uv run --frozen pylint --disable" in source_makefile
    makefile.write_text(source_makefile.replace("uv run --frozen lint-imports\n", f"uv run --frozen lint-imports --cache-dir={SCRATCH / 'imports'}\n").replace("uv run --frozen pylint --disable", "uv run --frozen pylint --persistent=n --disable"))
    env.update(XDG_CACHE_HOME=str(SCRATCH / "cache"))
    start = time.monotonic()
    with (HERE / "make-check.log").open("w") as out:
        proc = subprocess.run(["make", "-f", str(makefile), "check"], cwd=STUDIO, env=env, stdout=out,
                              stderr=subprocess.STDOUT, timeout=1800, check=False)
    result = {"command": "make check", "exit_code": proc.returncode,
              "seconds": round(time.monotonic() - start, 2), "source_unchanged": before == manifest()}
    if (SCRATCH / ".coverage").exists():
        with (HERE / "coverage-report.log").open("w") as out:
            subprocess.run([str(STUDIO / ".venv/bin/python"), "-B", "-m", "coverage", "report"],
                           cwd=STUDIO, env=env, stdout=out, stderr=subprocess.STDOUT, check=False)
    (HERE / "checks.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)
    print((HERE / "make-check.log").read_text()[-5000:], flush=True)


if __name__ == "__main__":
    main()
