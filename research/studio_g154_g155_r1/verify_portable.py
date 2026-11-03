"""在没有 firmware 目录的隔离副本中检查本机夹具的正常跳过。"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1] / "studio"
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g154-g155-r1")
TARGET = SCRATCH / "portable/studio"


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for folder in ("src", "tests"):
        shutil.copytree(STUDIO / folder, TARGET / folder, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(STUDIO / "pyproject.toml", TARGET / "pyproject.toml")
    assert not (TARGET.parent / "firmware").exists()
    env = {**os.environ, "PYTHONPATH": str(TARGET / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    verify = "from pathlib import Path; from gxr_studio.camdata import datcodec; "
    verify += f"assert Path(datcodec.__file__).is_relative_to(Path({str(TARGET)!r}))"
    subprocess.run([sys.executable, "-B", "-c", verify], cwd=TARGET, env=env, check=True, timeout=30)
    command = [sys.executable, "-B", "-m", "pytest", "-q", "tests/test_g152.py", "tests/test_g154_g155.py"]
    subprocess.run(command, cwd=TARGET, env=env, check=True, timeout=120)


if __name__ == "__main__":
    main()
