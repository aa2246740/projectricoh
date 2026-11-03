#!/usr/bin/env python3
"""Read-only capture analysis. Writes only this directory's local/ and /tmp/um_gpt."""
import sys

sys.dont_write_bytecode = True

import hashlib
import importlib.util
import json
import os
import plistlib
import subprocess
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
TMP = Path("/tmp/um_gpt")
CAP = ROOT / "captures/a12-50/2026-10-20/stage2j-notables-huering"
STEM = "R8051170"
W = np.array([0.2126, 0.7152, 0.0722])
UW = np.array([0.25, 0.5, 0.25])


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(name, value):
    (LOCAL / name).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                        allow_nan=False) + "\n")


def verify_volume():
    v = plistlib.loads(subprocess.check_output(
        ["diskutil", "info", "-plist", "/Volumes/Workspace"]))
    assert os.path.ismount("/Volumes/Workspace")
    assert v["VolumeUUID"] == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
    assert v["FilesystemType"] == "apfs" and v["WritableVolume"]
    return {"uuid": v["VolumeUUID"], "filesystem": v["FilesystemType"],
            "writable": v["WritableVolume"], "df": subprocess.check_output(
                ["df", "-h", "/Volumes/Workspace"], text=True)}


def tone_analysis(f, measurement):
    fit = json.loads((ROOT / "research/fuji_phase2/local/fit.json").read_text())
    stock = json.loads((ROOT / "research/phase1_curves/local/firmware_and_fit.json").read_text())["stock_row5"]
    sx = np.r_[0, stock["input31_u16"], 4095]
    sy = np.array(stock["output33_u8"], dtype=float)
    a = fit["anchor"]
    um, bias = a["u_m"], a["f"]
    archive = Path("/tmp/gxr_fuji/downloads/gfx-eterna-55-3d-lut-v110.zip")
    archive_sha = sha(archive)
    expected = {"classic_chrome": "43f7fc5f262eaa2525c0de805ad7fa50f5b77d85873840ae48ab2a07a6b36ff9",
                "classic_neg": "f890a58d2ae278703aa09e73d6037a32cb925a6d90414292da7675e12b7dd3c9"}
    patterns = {"classic_chrome": "FLog2_to_CLASSIC-CHROME_65grid",
                "classic_neg": "FLog2_to_CLASSIC-Neg._65grid"}
    luts = {}
    with zipfile.ZipFile(archive) as z:
        for key, pattern in patterns.items():
            names = [n for n in z.namelist() if pattern in n and n.endswith(".cube")]
            assert len(names) == 1
            luts[key] = f.load_cube(z, names[0])
            assert luts[key]["sha256"] == expected[key]

    def code(key, u, mid):
        rho = 0.18 * np.maximum(np.asarray(u) - bias, 0) / (mid - bias)
        return f.neutral_codes(luts[key], rho) @ W * 255

    stops = np.array([-2, -1, 0, 1, 2, 3], dtype=float)
    probe_u = bias + (um - bias) * 2 ** stops
    scenarios = {
        "center40_INVALID": measurement["center_windows"]["40"]["u_robust"],
        "D4_NOT_METERED": measurement["patches"]["D4"]["u_robust"],
        "chart18_NOT_METERED": measurement["grey_line_fits"]["5"]["u_at_18pct"],
    }
    for shift in (-0.3, -0.2, -0.1, 0.1, 0.2, 0.3):
        scenarios[f"signal_EV_{shift:+.1f}"] = bias + (um - bias) * 2 ** shift
    result = {"u_m_assumed": um, "f_retained": bias, "curve_lut_sha256": expected,
              "archive_sha256": archive_sha, "comparison": "fixed sensor u, ideal LUT luma; no curve or table rebuilt",
              "stops_at_old_anchor": stops.tolist(), "probe_u": probe_u.tolist(),
              "old_codes": {key: code(key, probe_u, um).tolist() for key in luts},
              "scenarios": {}}
    for label, mid in scenarios.items():
        result["scenarios"][label] = {
            "u_candidate": mid,
            "raw_EV_vs_assumed": float(np.log2(mid / um)),
            "signal_EV_vs_assumed": float(np.log2((mid - bias) / (um - bias))),
            "codes": {key: code(key, probe_u, mid).tolist() for key in luts},
            "delta_codes": {key: (code(key, probe_u, mid) - code(key, probe_u, um)).tolist()
                            for key in luts},
            "delta_on_capture_greys": {
                key: {g: float(code(key, p["u_robust"], mid) - code(key, p["u_robust"], um))
                      for g, p in measurement["patches"].items() if g.startswith("D")}
                for key in luts}}
    for label, p in measurement["patches"].items():
        if label.startswith("D"):
            p["stock_row5_predicted_code"] = float(np.interp(p["u_robust"] * 4095, sx, sy))
            p["stock_row5_prediction_residual"] = p["jpeg_y709_robust"] - p["stock_row5_predicted_code"]
    result["D4_to_18pct_reflectance_EV"] = float(np.log2(measurement["patches"]["D4"]["published_Y"] / 0.18))
    result["D4_raw_EV_vs_assumed"] = float(np.log2(measurement["patches"]["D4"]["u_robust"] / um))
    assert sha(archive) == archive_sha
    dump("tone_sensitivity.json", result)
    return result


def main():
    volume = verify_volume()
    LOCAL.mkdir(exist_ok=True)
    TMP.mkdir(exist_ok=True)
    inputs = [CAP / (STEM + ext) for ext in (".DNG", ".JPG")]
    inputs += [ROOT / "research/stage2e_verification/analyze_2e.py",
               ROOT / "research/stage2d_verification/analyze.py",
               ROOT / "research/color_calibration/analyze_capture.py",
               ROOT / "research/fuji_phase2/fit_fuji.py",
               ROOT / "research/fuji_phase2/local/fit.json",
               ROOT / "research/phase1_curves/local/firmware_and_fit.json"]
    before = {str(p): sha(p) for p in inputs}
    s = load_module("um_stage2e", inputs[2])
    f = load_module("um_fuji", ROOT / "research/fuji_phase2/fit_fuji.py")
    s.CAP = CAP
    metadata = s.metadata(STEM)
    metadata.pop("record_hex")
    metadata.pop("raw13")
    crop, black, white, neutral, raw_stats = s.decode_raw(s.Tiff(inputs[0].read_bytes()))
    jpeg = np.asarray(Image.open(inputs[1]).convert("RGB"), dtype=np.float64)
    h, w = crop.shape
    assert jpeg.shape == (h, w, 3)
    ox, oy = raw_stats["crop_origin_xy"]
    Y, (sx, sy) = s.raw_luminance(crop, black, white, neutral, (ox, oy))
    half_centres, geo = s.detect_lattice(Y)
    centres = half_centres * 2 + [sx + 0.5, sy + 0.5]
    grid = centres.reshape(4, 6, 2)
    pitch = min(float(np.median(np.diff(grid[:, :, 0], axis=1))),
                float(np.median(np.diff(grid[:, :, 1], axis=0))))
    half = round(0.16 * pitch)

    def sample(roi):
        x0, y0, x1, y1 = map(int, roi)
        assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h
        dn = np.array(s.cfa_means(crop, y0, y1, x0, x1, oy, ox))
        rgbwb = (dn - black) / (white - black) / neutral
        rgb = jpeg[y0:y1, x0:x1]
        values, codes = [], []
        xx = np.linspace(x0, x1, 9).round().astype(int)
        yy = np.linspace(y0, y1, 9).round().astype(int)
        for ya, yb in zip(yy[:-1], yy[1:]):
            for xa, xb in zip(xx[:-1], xx[1:]):
                td = np.array(s.cfa_means(crop, ya, yb, xa, xb, oy, ox))
                values.append(float(((td - black) / (white - black) / neutral) @ UW))
                codes.append(float(jpeg[ya:yb, xa:xb].mean((0, 1)) @ W))
        values, codes = np.array(values), np.array(codes)
        tile_mad = np.median(abs(values - np.median(values)))
        return {"roi_xyxy": [x0, y0, x1, y1], "raw_dn_mean": dn.tolist(),
                "camera_rgb_wb_mean": rgbwb.tolist(), "u_mean": float(rgbwb @ UW),
                "u_robust": float(np.median(values)), "tile_u_mad": float(tile_mad),
                "tile_u_p05_p95": np.percentile(values, [5, 95]).tolist(),
                "tile_u_min_max": [float(values.min()), float(values.max())],
                "tile_u_cv": float(values.std() / values.mean()),
                "jpeg_rgb_mean": rgb.mean((0, 1)).tolist(),
                "jpeg_y709_mean": float(rgb.mean((0, 1)) @ W),
                "jpeg_y709_robust": float(np.median(codes)),
                "tile_jpeg_p05_p95": np.percentile(codes, [5, 95]).tolist(),
                "pixel_jpeg_p05_p95": np.percentile(rgb @ W, [5, 95]).tolist(),
                "tile_u": values.tolist(), "tile_jpeg_y709": codes.tolist()}

    published_y = dict(zip(f.CC_LABELS,
                          f.lab_to_xyz(f.CC_LAB_D50, f.D50)[:, 1].tolist()))
    patches = {}
    for label, (cx, cy) in zip(s.LABELS, centres):
        p = sample([round(cx - half), round(cy - half),
                    round(cx + half), round(cy + half)])
        p.update(center_xy=[float(cx), float(cy)], published_Y=published_y[label])
        patches[label] = p
    center = np.array([w / 2, h / 2])
    windows = {}
    for side in (20, 40, 80, 160, 320, 600):
        windows[str(side)] = sample([int(center[0] - side / 2),
                                    int(center[1] - side / 2),
                                    int(center[0] + side / 2),
                                    int(center[1] + side / 2)])
    H = s.homography(np.array([[i, j] for j in range(4) for i in range(6)]), centres)
    lattice_center = s.apply_h(np.linalg.inv(H), center[None])[0]
    grey_labels = ["D" + str(i) for i in range(1, 7)]
    line_fits = {}
    for n in (5, 6):
        labels = grey_labels[:n]
        yy = np.array([published_y[k] for k in labels])
        uu = np.array([patches[k]["u_robust"] for k in labels])
        A = np.c_[yy, np.ones(n)]
        c, intercept = np.linalg.lstsq(A, uu, rcond=None)[0]
        residual = uu - A @ [c, intercept]
        line_fits[str(n)] = {"labels": labels, "c": float(c), "f": float(intercept),
                            "rmse_u": float(np.sqrt(np.mean(residual ** 2))),
                            "r2": float(1 - residual @ residual / np.sum((uu - uu.mean()) ** 2)),
                            "u_at_18pct": float(c * 0.18 + intercept),
                            "u_at_D4_Y": float(c * published_y["D4"] + intercept),
                            "residual_u": dict(zip(labels, residual.tolist()))}
    out = {"volume": volume, "metadata": metadata, "raw_stats": raw_stats,
           "geometry": {**geo, "pitch_px": pitch, "roi_half_px": half,
                        "center_xy": center.tolist(), "center_grid_xy": lattice_center.tolist()},
           "patches": patches, "center_windows": windows, "grey_line_fits": line_fits,
           "u_m_measured": None,
           "u_m_rejected_reason": "Frame centre is black gutter at the B3/B4/C3/C4 junction; spot footprint and weights are unknown.",
           "statistic": "median of 64 CFA-aware tile means; untrimmed CFA mean also retained"}
    tone_analysis(f, out)
    out["tone_result_file"] = "tone_sensitivity.json"

    # Coordinates and overlays are evidence only, not a colour transform.
    overlay = Image.open(inputs[1]).convert("RGB")
    draw = ImageDraw.Draw(overlay)
    for label, p in patches.items():
        draw.rectangle(p["roi_xyxy"], outline="cyan", width=5)
        draw.text(tuple(p["roi_xyxy"][:2]), label, fill="white", stroke_width=1)
    cx, cy = map(int, center)
    draw.line((cx - 100, cy, cx + 100, cy), fill="white", width=4)
    draw.line((cx, cy - 100, cx, cy + 100), fill="white", width=4)
    for key, color in (("40", "red"), ("160", "yellow"), ("600", "lime")):
        draw.rectangle(windows[key]["roi_xyxy"], outline=color, width=5)
    overlay.thumbnail((1500, 1100))
    overlay.save(LOCAL / "roi_overlay.jpg", quality=92)
    Image.open(inputs[1]).crop((cx - 400, cy - 400, cx + 400, cy + 400)).save(
        LOCAL / "center_native.jpg", quality=95)
    after = {str(p): sha(p) for p in inputs}
    assert before == after, "Read-only input changed while measuring"
    out["input_sha256_before"] = before
    out["input_sha256_after"] = after
    dump("measurement.json", out)
    print(json.dumps({"center_grid_xy": lattice_center.round(4).tolist(),
                      "center40": {k: windows["40"][k] for k in
                                   ("u_robust", "u_mean", "jpeg_y709_robust", "tile_u_cv")},
                      "greys": {k: {key: patches[k][key] for key in
                                     ("u_robust", "jpeg_y709_robust", "tile_u_cv")}
                                for k in grey_labels}, "grey_fit": line_fits["5"],
                      "unchanged": before == after}, ensure_ascii=False))


if __name__ == "__main__":
    main()
