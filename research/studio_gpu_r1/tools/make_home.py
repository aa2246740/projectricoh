"""把本机已有的 g127 夹具 DAT 和标定文件提取到一个临时应用数据目录（理光字节只写到那里，不进仓库）。

用法：studio/.venv/bin/python research/studio_gpu_r1/tools/make_home.py <目标目录>
只读调用 studio/src/gxr_studio；不改 studio/ 下任何文件。
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "studio/src"))
sys.path.insert(0, str(REPO / "studio/tests"))

import e0_support as t  # noqa: E402
from gxr_studio.camdata import calib, store  # noqa: E402


def main(dest: str) -> None:
    home = Path(dest)
    home.mkdir(parents=True, exist_ok=True)
    raw = t.fixture_dat(127)
    if raw is None:
        raise SystemExit("g127 夹具 DAT 不在本机")
    store.import_from_dat(raw, home)
    calib.import_calibration(home, calib.dev_sources(REPO))
    print("ok", home)


if __name__ == "__main__":
    main(sys.argv[1])
