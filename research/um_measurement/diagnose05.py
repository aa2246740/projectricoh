#!/usr/bin/env python3
"""Read the existing 05 candidate; split its neutral error without fitting tables."""
import sys

sys.dont_write_bytecode = True

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    # Reuse the volume guard before creating any analysis output.
    spec = importlib.util.spec_from_file_location("um_measure", HERE / "measure.py")
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.verify_volume()
    path = ROOT / "research/color_fit_v2/05_classic_chrome/fit_v2.py"
    spec = importlib.util.spec_from_file_location("um_chrome_readonly", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    train_path = path.parent / "local/training.json"
    training_bytes = train_path.read_bytes()
    data = json.loads(training_bytes)
    S, target, samples, exposure, einfo = m.setup()
    P = m.problem(S, samples, exposure, "sector")
    theta = np.array(data["variants"]["sector"]["full"]["theta"])
    prediction = P.predict(theta)
    idx = [i for i, label in enumerate(P.labels) if label.startswith("D")]
    expected = P.lt[idx]
    neutral = prediction[idx]
    lightness_only = np.c_[neutral[:, 0], expected[:, 1:]]
    tint_only = np.c_[expected[:, 0], neutral[:, 1:]]
    full_de = m.fs.delta_e00(neutral, expected)
    lightness_de = m.fs.delta_e00(lightness_only, expected)
    tint_de = m.fs.delta_e00(tint_only, expected)
    rows = []
    for j, i in enumerate(idx):
        rows.append({"label": P.labels[i], "target_lab": expected[j].tolist(),
                     "predicted_lab": neutral[j].tolist(),
                     "dL": float(neutral[j, 0] - expected[j, 0]),
                     "full_de00": float(full_de[j]),
                     "lightness_only_de00": float(lightness_de[j]),
                     "tint_only_de00": float(tint_de[j])})

    bias = einfo["f"]
    um = einfo["u_m"]

    class ShiftedCurve:
        def __init__(self, shift):
            self.shift = shift

        def __call__(self, codes):
            u = np.asarray(codes) / 4095
            old_u = bias + (u - bias) * 2 ** (-self.shift)
            return P.curve(old_u * 4095)

    def evaluate(shift, renormalize_exposure=False):
        mid = bias + (um - bias) * 2 ** shift
        e = S.ctx.anchor_ratio(mid)[0] if renormalize_exposure else exposure
        shifted = m.f.JointProblemV2(S, samples, ShiftedCurve(shift), e, "sector")
        lab = shifted.predict(theta)[idx]
        return lab

    assert np.max(abs(evaluate(0) - neutral)) < 1e-10
    def lightness_mse(shift):
        return float(np.mean((evaluate(shift)[:, 0] - expected[:, 0]) ** 2))

    optimum = minimize_scalar(lightness_mse, bounds=(-0.5, 0.5), method="bounded",
                              options={"xatol": 1e-6, "maxiter": 60})
    sweeps = {}
    for shift in (-0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3, float(optimum.x)):
        new = evaluate(shift)
        new_de = m.fs.delta_e00(new, expected)
        light = m.fs.delta_e00(np.c_[new[:, 0], expected[:, 1:]], expected)
        consistent = evaluate(shift, True)
        sweeps[f"{shift:+.6f}"] = {
            "signal_EV": shift, "fixed_exposure_dL": (new[:, 0] - expected[:, 0]).tolist(),
            "fixed_exposure_total_median_de00": float(np.median(new_de)),
            "fixed_exposure_lightness_median_de00": float(np.median(light)),
            "fixed_exposure_lightness_rmse": float(np.sqrt(lightness_mse(shift))),
            "renormalized_exposure_max_abs_dL_change": float(np.max(abs(consistent[:, 0] - neutral[:, 0]))),
        }
    result = {"source_training_sha256": hashlib.sha256(training_bytes).hexdigest(),
              "model_sha256": guard.sha(S.model_path), "variant": "sectors-only, ISO200",
              "method": "existing candidate only; no optimization of colour rows; optional single EV oracle minimizes neutral L RMSE",
              "decomposition": "CIEDE2000 with one part replaced by target; components do not add",
              "exposure": exposure, "u_m": um, "f": bias, "rows": rows,
              "median_full_de00": float(np.median(full_de)),
              "median_lightness_only_de00": float(np.median(lightness_de)),
              "median_tint_only_de00": float(np.median(tint_de)),
              "single_shift_oracle_EV": float(optimum.x),
              "sweeps": sweeps}
    (HERE / "local/neutral05_diagnostic.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("median_full_de00", "median_lightness_only_de00",
                                           "median_tint_only_de00", "single_shift_oracle_EV")}))


if __name__ == "__main__":
    main()
