"""显卡读回 vs Python 参考：逐像素 ΔE2000（studio engine.colour 的同一实现）。

用法：studio/.venv/bin/python compare.py <gpudata> <readback 目录> <输出 JSON> [--full]
  不带 --full：比较代理图分辨率的预览（name__set__WxH.rgba ↔ gpudata/name/ref/set.png）
  带 --full：比较全尺寸导出（name__set__full__WxH.rgba ↔ gpudata/name/ref_full/set.png）
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "studio/src"))
from gxr_studio.engine.colour import delta_e00, lab_from_codes  # noqa: E402


def de_stats(a: np.ndarray, b: np.ndarray) -> dict:
    if a.shape != b.shape:
        return {"error": f"shape {a.shape} vs {b.shape}"}
    a2, b2 = a.reshape(-1, 3), b.reshape(-1, 3)
    diff = np.abs(a2.astype(int) - b2.astype(int))
    de = np.empty(len(a2))
    for s in range(0, len(a2), 1 << 20):
        de[s : s + (1 << 20)] = delta_e00(lab_from_codes(a2[s : s + (1 << 20)]), lab_from_codes(b2[s : s + (1 << 20)]))
    return {
        "mean": round(float(de.mean()), 4),
        "p95": round(float(np.percentile(de, 95)), 4),
        "p99": round(float(np.percentile(de, 99)), 4),
        "max": round(float(de.max()), 3),
        "share_identical": round(float((diff.max(axis=1) == 0).mean()), 4),
        "share_within_1_code": round(float((diff.max(axis=1) <= 1).mean()), 4),
        "max_code_diff": int(diff.max()),
        "share_de_over_1": round(float((de > 1).mean()), 5),
    }


def main() -> None:
    data, rb, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    full = "--full" in sys.argv
    rows = []
    pat = re.compile(r"(?P<name>[^_]+)__(?P<set>s\d+_[a-z0-9_]+?)__(?P<tag>(?:full|rawgpu)__)?(?P<w>\d+)x(?P<h>\d+)\.rgba$")
    want = "full__" if full else ("rawgpu__" if "--rawgpu" in sys.argv else None)
    for f in sorted(rb.glob("*.rgba")):
        m = pat.match(f.name)
        if not m or m.group("tag") != want:
            continue
        w, h = int(m.group("w")), int(m.group("h"))
        gpu = np.frombuffer(f.read_bytes(), np.uint8).reshape(h, w, 4)[..., :3]
        refdir = data / m.group("name") / ("ref_full" if full else "ref")
        row = {"photo": m.group("name"), "set": m.group("set"), "w": w, "h": h, "tag": m.group("tag")}
        for tag, suffix in (("vs_python", ""), ("vs_python_f16_input", ".f16in"), ("vs_python_jpeg_base", ".jpegbase")):
            p = refdir / f"{m.group('set')}{suffix}.png"
            if p.is_file():
                row[tag] = de_stats(gpu, np.asarray(Image.open(p).convert("RGB")))
        if full:
            Image.fromarray(np.ascontiguousarray(gpu), "RGB").save(refdir / f"{m.group('set')}.gpu.png", compress_level=1)
        rows.append(row)
        v = row.get("vs_python", {})
        print(row["photo"], row["set"], "mean", v.get("mean"), "p95", v.get("p95"), "max", v.get("max"), "ident", v.get("share_identical"), "f16", row.get("vs_python_f16_input", {}).get("mean"))
    out.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
