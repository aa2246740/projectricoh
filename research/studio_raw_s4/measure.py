"""S4 numbers for REPORT.md. Usage: studio/.venv/bin/python -I research/studio_raw_s4/measure.py > research/studio_raw_s4/measure.json
Reads one capture DNG (read-only) and writes nothing but stdout."""
import json, resource, sys, time, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "studio/src"))
import numpy as np
from PIL import Image
from gxr_studio.crop import default_crop
from gxr_studio.export import ExportOptions, render_raw
from gxr_studio.raw import demosaic_full, half_res_codes, open_dng, render_full, render_half

SAMPLE = ROOT / "captures/a12-50/2026-10-19/stage2c-first-run/R8051144.DNG"
out = {"sample": str(SAMPLE.relative_to(ROOT))}
def timed(f, n=3):
    ts = []
    for _ in range(n):
        t = time.perf_counter(); r = f(); ts.append(time.perf_counter() - t)
    return r, round(min(ts), 3)
d, out["open_s"] = timed(lambda: open_dng(SAMPLE))
d.mosaic()
_, out["half_codes_s"] = timed(lambda: half_res_codes(d))
_, out["render_half_s"] = timed(lambda: render_half(d))
_, out["render_full_s"] = timed(lambda: render_full(d))
for name, crop, opts in (("jpeg_q95_original_full", None, ExportOptions(None, 95)),
                         ("jpeg_q85_2048_xpan", default_crop("xpan-65-24", 4288, 2848), ExportOptions(2048, 85)),
                         ("png_original_full", None, ExportOptions(None, 95, "png"))):
    (data, size), t = timed(lambda: render_raw(SAMPLE, crop, opts), 2)
    out[f"export_{name}"] = {"seconds": t, "bytes": len(data), "size": list(size)}
out["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 1)
# U3, code-domain version: demosaiced 2x2 mean vs half-res binning
full = demosaic_full(d); half = half_res_codes(d)
h2, w2 = half.shape[:2]
binned = full[:2*h2, :2*w2].reshape(h2, 2, w2, 2, 3).mean(axis=(1, 3))
mid = (half > 200) & (half < 3500)
rel = np.abs(binned - half)[mid] / half[mid]
out["demosaic_vs_half_binning_relative_diff"] = {"n": int(mid.sum()), "median": float(np.median(rel)), "p90": float(np.percentile(rel, 90)),
    "p99": float(np.percentile(rel, 99)), "mean_ratio_full_over_half": float(full.mean() / half.mean())}
cam = np.asarray(Image.open(SAMPLE.with_suffix(".JPG")).convert("L"), float)
mine = np.asarray(Image.fromarray(render_full(d)).convert("L"), float)
out["mean_luma_neutral_vs_camera_jpg"] = [round(float(mine.mean()), 1), round(float(cam.mean()), 1)]
print(json.dumps(out, indent=1))
