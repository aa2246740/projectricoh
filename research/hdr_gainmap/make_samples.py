"""批量做样张：captures/street-g137-20261031 里 15 对 JPG+DNG → captures/hdr-gainmap-proto/。

    studio/.venv/bin/python -I research/hdr_gainmap/make_samples.py [--max-stops 2.5] [编号 …]

每张输出：R805xxxx_HDR.JPG（成品）、R805xxxx_gainmap.png（增益图本身，白 = 提亮最多，便于肉眼检查）。
汇总写 captures/hdr-gainmap-proto/stats.json。只读输入。
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # python -I 不把脚本目录放进 sys.path

import gxr_hdr  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = HERE.parents[1]
SRC = ROOT / "captures" / "street-g137-20261031"
OUT = ROOT / "captures" / "hdr-gainmap-proto"
NUMBERS = [1530, 1531, 1532, 1533, 1534, 1535, 1536, 1537, 1562, 1577, 1627, 1644, 1653, 1680, 1685]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("numbers", nargs="*", type=int, default=NUMBERS)
    ap.add_argument("--max-stops", type=float, default=gxr_hdr.Params.max_stops)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    p = gxr_hdr.Params(max_stops=a.max_stops)
    stats_path = a.out / "stats.json"
    all_stats = json.loads(stats_path.read_text()) if stats_path.exists() else {}
    for n in a.numbers:
        name = f"R805{n}"
        out = a.out / f"{name}_HDR.JPG"
        s = gxr_hdr.make_hdr(SRC / "jpg" / f"{name}.JPG", SRC / "dng" / f"{name}.DNG", out, p)
        s["params"] = p.__dict__
        d = out.read_bytes()
        gm = d[s["primary_size"] :]
        Image.open(io.BytesIO(gm)).save(a.out / f"{name}_gainmap.png")
        all_stats[name] = s
        print(f"{name}: 最大增益 {s['gain_max_stops']:.2f} 档，>0.1 档面积 {s['frac_gain_gt_0p1_stop'] * 100:.1f}%，"
              f">1 档 {s['frac_gain_gt_1_stop'] * 100:.1f}%，RAW 过曝 {s['raw_clipped_frac'] * 100:.1f}%，"
              f"对齐 {s['alignment']}", flush=True)
    stats_path.write_text(json.dumps(all_stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
