#!/usr/bin/env python3
"""Recalculate the screen ramp from the two frozen capture analyses, offline."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess

for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[name] = "1"
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
OUT = HERE / "local/ramp"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import plistlib
    volume = plistlib.loads(subprocess.check_output(
        ["/usr/sbin/diskutil", "info", "-plist", "/Volumes/Workspace"]))
    assert volume["VolumeUUID"].upper() == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
    assert volume["FilesystemType"] == "apfs" and volume["WritableVolume"]
    OUT.mkdir(parents=True, exist_ok=True)
    model = HERE / "local/bracket_20261103/model.json"
    knots = np.array(json.loads(model.read_text())["xs"])[15:18]
    sources = {str(model.relative_to(HERE)): digest(model)}
    fits, boundaries = [], []
    for name, folder, frames, multiplier in [
        ("noon_1_15", "bracket_20261103", [1902], 1),
        ("morning_projected_1_15", "field_20261103",
         [1878, 1882, 1884, 1888, 1892, 1893], 2),
    ]:
        metadata_path = HERE / f"local/{folder}/metadata.json"
        sources[str(metadata_path.relative_to(HERE))] = digest(metadata_path)
        metadata = {row["frame"]: row["dng"] for row in json.loads(metadata_path.read_text())}
        measured = []
        for frame in frames:
            source = HERE / f"local/{folder}/frames/R805{frame}.json"
            sources[str(source.relative_to(HERE))] = digest(source)
            data = json.loads(source.read_text())
            neutral = np.array(metadata[f"R805{frame}"]["as_shot_neutral"])
            assert neutral.shape == (3,) and np.all(neutral > 0)
            assert abs(metadata[f"R805{frame}"]["exposure_s"] * multiplier - 1/15) < 1e-6
            measured.append(np.array([p["raw_dn_mean"]
                for p in data["patches"]["0.5"][:3]]) / neutral * multiplier)
        values = np.median(measured, axis=0)
        fit = PchipInterpolator([48, 128, 208], values, axis=0)
        inverse = [[brentq(lambda code: float(fit(code)[c] - x), 48, 208)
                    for x in knots] for c in range(3)]
        boundaries.extend(inverse)
        fits.append(dict(name=name, frames=frames, exposure_multiplier=multiplier,
                         observed_screen_codes=[48, 128, 208],
                         raw_wb_median=values.tolist(), inverse_screen_codes=inverse))
    lower = math.floor(min(b[0] for b in boundaries) / 2) * 2 - 16
    upper = math.ceil(max(b[2] for b in boundaries) / 2) * 2 + 16
    dense = np.rint(np.linspace(lower, upper, 45)).astype(int)
    codes = np.r_[48, 96, dense, 240, 254]
    assert len(codes) == len(set(codes)) == 49 and np.all(np.diff(codes) > 0)
    html = (HERE / "ramp.html").read_text()
    actual = json.loads(re.search(r"const GRAYS = (\[[\d,\s]+\]);", html)[1])
    assert actual == codes.tolist(), (actual, codes.tolist())
    for result in fits:
        fit = PchipInterpolator([48, 128, 208], result["raw_wb_median"], axis=0)
        predicted = fit(codes)
        result["predicted_raw_wb"] = predicted.tolist()
        coverage = []
        for c in range(3):
            values = predicted[:, c]
            active = values[(values >= knots[0]) & (values <= knots[2])]
            left = int(np.sum((values > knots[0]) & (values < knots[1])))
            right = int(np.sum((values > knots[1]) & (values < knots[2])))
            near_peak = float(np.min(abs(values - knots[1])))
            assert left >= 4 and right >= 4 and near_peak < 15
            gaps = np.diff(np.r_[knots[0], active, knots[2]])
            coverage.append(dict(channel="RGB"[c], ascending_points=left,
                descending_points=right, nearest_peak_distance=near_peak,
                max_input_gap=float(max(gaps)),
                support_screen_codes=result["inverse_screen_codes"][c]))
        result["coverage"] = coverage
    output = dict(status="PASS_PREDICTION_ONLY", method="monotone PCHIP through three measured greys",
        limitation="Same lens/aperture/screen brightness assumed. Morning multiplied by two; "
                   "new layout and f/5.6 fallback need captured RAW verification. "
                   "Values above screen code 208 are extrapolated, not calibrated.",
        sources=sources, node_window=knots.tolist(), dense_levels=dense.tolist(),
        gray_levels=codes.tolist(), gray_count=49, dense_count=45,
        max_dense_screen_gap=int(max(np.diff(dense))), fits=fits)
    (OUT / "plan.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(dict(status=output["status"], grays=49, dense=45,
        dense_range=[lower, upper], max_dense_screen_gap=output["max_dense_screen_gap"],
        coverage=[dict(name=f["name"], channels=f["coverage"]) for f in fits])))


if __name__ == "__main__":
    main()
