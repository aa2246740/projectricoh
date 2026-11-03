"""原样复跑 PR #12 六包对照入口，把其输出定向到本轮 Scratch。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g154-g155-r1")


def main():
    path = ROOT / "research/studio_g152_r1/verify_data.py"
    spec = importlib.util.spec_from_file_location("pr12_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = ROOT
    module.SCRATCH = SCRATCH / "pr12"
    module.HERE = SCRATCH / "pr12/report"
    module.HERE.mkdir(parents=True, exist_ok=True)
    assert module.PACKAGES == [(g, t) for g in (150, 152, 153) for t in (False, True)]
    module.main()
    result_path = module.HERE / "byte_equality.json"
    result = json.loads(result_path.read_text())
    assert len(result["packages"]) == 6 and result["look_comparisons"] == 120 and result["user_comparisons"] == 18
    shutil.copy2(result_path, HERE / "pr12-equality.json")


if __name__ == "__main__":
    main()
