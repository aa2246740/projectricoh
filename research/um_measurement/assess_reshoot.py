#!/usr/bin/env python3
"""Summarize the new measurements and evaluate ideal Fuji curves, without refitting."""
import sys

sys.dont_write_bytecode = True

import importlib.util
import json
import math
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / "local/reshoot"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    guard = load("um_reshoot_guard", HERE / "measure.py")
    guard.verify_volume()
    f = load("um_reshoot_fuji", ROOT / "research/fuji_phase2/fit_fuji.py")
    source = LOCAL / "measurements.json"
    old_source = ROOT / "research/stage2e_verification/local/measurements.json"
    fit_source = ROOT / "research/fuji_phase2/local/fit.json"
    archive = Path("/tmp/gxr_fuji/downloads/gfx-eterna-55-3d-lut-v110.zip")
    paths = [source, old_source, fit_source, archive, Path(f.__file__)]
    before = {str(p): guard.sha(p) for p in paths}
    data = json.loads(source.read_text())
    frames = data["frames"]
    old = json.loads(old_source.read_text())
    anchor = json.loads(fit_source.read_text())["anchor"]
    old_um, bias = anchor["u_m"], anchor["f"]
    mid = np.array([frames[k]["center_windows"]["80"]["u"] for k in ("R8051188", "R8051192")])
    new_um = float(mid.mean())
    result = {"u_m_centre_assuming_default_spot_target": new_um,
              "scope": "ISO200, f4, manual WB, A/spot/EC0; actual AE target position and footprint are not recorded",
              "u_m_each": mid.tolist(), "sensor_code": new_um * 4095,
              "u_m_mean_statistic": float(np.mean([frames[k]["center_windows"]["80"]["u_mean"] for k in ("R8051188", "R8051192")])),
              "between_frame_EV": float(np.log2(mid[0] / mid[1])),
              "raw_EV_vs_old": float(np.log2(new_um / old_um)),
              "signal_EV_vs_old": float(np.log2((new_um - bias) / (old_um - bias))),
              "f_retained": bias, "old_u_m": old_um, "grey_fits": {}, "old_2e_WB": {}}
    published_y = dict(zip(f.CC_LABELS, f.lab_to_xyz(f.CC_LAB_D50, f.D50)[:, 1]))
    for stem, frame in frames.items():
        result["grey_fits"][stem] = {}
        for labels in (["D2", "D3", "D4"], ["D1", "D2", "D3", "D4", "D5"]):
            yy = np.array([published_y[g] for g in labels])
            uu = np.array([frame["patches"][g]["u"] for g in labels])
            A = np.c_[yy, np.ones(len(labels))]
            slope, intercept = np.linalg.lstsq(A, uu, rcond=None)[0]
            error = uu - A @ [slope, intercept]
            result["grey_fits"][stem]["_".join(labels)] = {
                "slope": float(slope), "intercept": float(intercept),
                "rmse_u": float(np.sqrt(np.mean(error ** 2))),
                "u18": float(.18 * slope + intercept),
                "u_div_reflectance": dict(zip(labels, (uu / yy).tolist())),
                "t_normalized_D4": frame["patches"]["D4"]["u"] / frame["meta"]["t"]}
        m = frame["meta"]
        frame["apex_AV_TV_SV_minus_BV"] = 2 * math.log2(m["f"]) + math.log2(1 / m["t"]) - math.log2(m["iso"] / 3.125) - m["bv"]
    result["apex_residual_EV"] = {s: f["apex_AV_TV_SV_minus_BV"] for s, f in frames.items()}
    for stem in ("R8051152", "R8051160"):
        patches = {p["label"]: p for p in old["frames"][stem]["patches"]}
        result["old_2e_WB"][stem] = {g: {"a": patches[g]["lab"][1], "b": patches[g]["lab"][2],
                                          "B_over_G": patches[g]["camera_rgb_wb"][2] / patches[g]["camera_rgb_wb"][1]}
                                           for g in ("D2", "D3", "D4")}
    lut_patterns = {"05": "FLog2_to_CLASSIC-CHROME_65grid", "06": "FLog2_to_CLASSIC-Neg._65grid"}
    expected = {"05": "43f7fc5f262eaa2525c0de805ad7fa50f5b77d85873840ae48ab2a07a6b36ff9",
                "06": "f890a58d2ae278703aa09e73d6037a32cb925a6d90414292da7675e12b7dd3c9"}
    stops = np.array([-2, -1, 0, 1, 2, 3], dtype=float)
    probe_u = bias + (old_um - bias) * 2 ** stops
    result["tone"] = {"stops_at_old_anchor": stops.tolist(), "fixed_probe_u": probe_u.tolist(),
                      "meaning": "fixed sensor inputs; passthrough ideal LUT codes; no table refit or quantization",
                      "profiles": {}}
    with zipfile.ZipFile(archive) as z:
        for key, pattern in lut_patterns.items():
            names = [name for name in z.namelist() if pattern in name and name.endswith(".cube")]
            assert len(names) == 1
            lut = f.load_cube(z, names[0])
            assert lut["sha256"] == expected[key]
            def code(u, um):
                rho = .18 * np.maximum(np.asarray(u) - bias, 0) / (um - bias)
                return f.neutral_codes(lut, rho) @ f.LUMA_W * 255
            baseline = code(probe_u, old_um)
            replacement = code(probe_u, new_um)
            result["tone"]["profiles"][key] = {
                "lut_sha256": expected[key], "old_codes": baseline.tolist(),
                "new_codes": replacement.tolist(), "delta_codes": (replacement - baseline).tolist(),
                "at_measured_mid_old": float(code(new_um, old_um)),
                "at_measured_mid_new": float(code(new_um, new_um)),
                "delta_codes_each_frame": [(code(probe_u, float(m)) - baseline).tolist() for m in mid]}
    after = {str(p): guard.sha(p) for p in paths}
    assert before == after
    result["input_sha256_before"] = before
    result["input_sha256_after"] = after
    (LOCAL / "assessment.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("u_m_centre_assuming_default_spot_target", "sensor_code", "between_frame_EV", "raw_EV_vs_old", "signal_EV_vs_old")}))
    for k, v in result["tone"]["profiles"].items():
        print(k, "delta_codes", [round(x, 3) for x in v["delta_codes"]],
              "measured_mid", round(v["at_measured_mid_old"], 3), round(v["at_measured_mid_new"], 3))


if __name__ == "__main__":
    main()
