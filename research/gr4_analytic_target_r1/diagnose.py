"""Untouched natural-mode validation and explicitly conditional error diagnostics."""
from pathlib import Path
from dataclasses import asdict
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import simulator as sim
from validate import load_arrays, predict, with_radial, relative
from scipy.optimize import minimize_scalar


def components(predicted, observed):
    p, y = rt.lab(predicted), rt.lab(observed)
    delta = p - y
    dc = np.hypot(p[:, 1], p[:, 2]) - np.hypot(y[:, 1], y[:, 2])
    return dict(DeltaE00=rt.stats(rt.cm.delta_e00(p, y)), signed_dL_median=float(np.median(delta[:, 0])),
                abs_dL=rt.stats(abs(delta[:, 0])), signed_dC_median=float(np.median(dc)), abs_dC=rt.stats(abs(dc)))


def natural_scores(common, options, tag):
    rows, arrays = [], {}
    for file, label, modes in (("natural.npz", "new_donor_standard", ("standard",)),
                               ("natural_modes.npz", "earlier_donor_modes", tuple(sim.MODES))):
        a = load_arrays(file)
        for mode in modes:
            use = np.ones(len(a["raw_wb"]), bool) if "mode" not in a else (a["mode"] == mode) & a["defaults_verified"]
            if not use.any(): continue
            idx = np.flatnonzero(use)
            actual = a["standard"][use] if "observed" not in a else a["observed"][use]
            rad = 2 ** np.interp(a["radius"][use], common["radius"], common["radial_ev"])
            exposure = 2 ** (a["baseline_exposure"][use] - common["template_baseline_exposure"])
            for coordinate in ("camera", "scene"):
                predicted = (sim.render(a["raw_wb"][use] * (rad * exposure)[:, None], mode, common, options)
                    if coordinate == "camera" else sim.render_scene(a["scene"][use] * rad[:, None], mode, common, options))
                arrays[f"{label}_{mode}_{coordinate}"] = predicted
                for frame in [*np.unique(a["frame"][use]), "pooled"]:
                    subset = np.ones(len(idx), bool) if frame == "pooled" else a["frame"][use] == frame
                    rows.append(dict(model=tag, data=label, mode=mode, coordinate=coordinate, frame=str(frame),
                        evidence="对真实 GR IV 照片的验证", split="whole_photo_holdout", defaults_verified=True,
                        metric=components(predicted[subset], actual[subset])))
                    if frame != "pooled":
                        print(tag, coordinate, frame, mode, rows[-1]["metric"]["DeltaE00"], flush=True)
    np.savez_compressed(rt.LOCAL / f"natural_predictions_{tag}.npz", **arrays)
    return rows


def recover_from_standard(a, common):
    """Oracle diagnostic: use a held-out JPEG Standard per patch. Never a portable calibration."""
    raw = with_radial(a["raw_wb"], a["radius"], common)
    p = sim.parameters()["modes"]["standard"]
    front = (np.asarray(p["saturation"]).reshape(3, 3) / 8192) @ (np.asarray(p["look"]).reshape(3, 3) / 8192) @ np.asarray(common["matrix"])
    z = raw @ front.T * 2 ** common["exposure_ev"]
    nodes = np.arange(256) * 16 / 4095
    gamma = sim.curve("standard", common["gain"])
    unique, indexes = np.unique(gamma, return_index=True)
    before_gamma = np.interp(a["standard"], unique, nodes[indexes])
    mats = np.asarray(p["ma"]).reshape(12, 5, 3, 3)[:, 0] / 1024
    # Refine sector membership from the inferred Standard signal, with no styled pixels.
    for _ in range(4):
        sector = sim.sector_of(z, "standard")[0]
        z = np.einsum("...ij,...j->...i", np.linalg.inv(mats[sector]), before_gamma)
    recovered = z @ np.linalg.inv(front).T / 2 ** common["exposure_ev"]
    return recovered


def dense_diagnostics(common, options):
    a = load_arrays("dense.npz")
    rows = []
    for mode in sim.MODES:
        predicted = predict(a, mode, common, options)
        selected = (a["band"] == 4) & a[mode + "_valid"] & np.isin(a["role"], ["colour", "tone", "reference", "natural"])
        actual_lab = rt.lab(a[mode])
        chromatic = np.hypot(actual_lab[:, 1], actual_lab[:, 2]) >= 8
        for name, flag in (("all", np.ones(len(selected), bool)), ("neutral", ~chromatic), ("chromatic", chromatic),
                           ("center_r_le_05", a["radius"] <= .5), ("outer_r_gt_05", a["radius"] > .5),
                           ("L_lt_30", actual_lab[:, 0] < 30),
                           ("L_30_70", (actual_lab[:, 0] >= 30) & (actual_lab[:, 0] <= 70)),
                           ("L_gt_70", actual_lab[:, 0] > 70)):
            use = selected & flag
            if use.any():
                rows.append(dict(mode=mode, slice=name, metric=components(predicted[use], a[mode][use])))
    oracle = recover_from_standard(a, common)
    predictions = {mode: sim.render(oracle, mode, common, options) for mode in sim.MODES}
    oracle_scores = []
    for mode in sim.MODES:
        use = (a["band"] == 4) & a[mode + "_valid"] & a["standard_valid"] & np.isin(a["role"], ["colour", "tone", "reference", "natural"])
        oracle_scores.append(dict(mode=mode, metric=components(predictions[mode][use], a[mode][use]),
            deployable=False, heldout_standard_JPEG_used_per_patch=True,
            meaning="conditional style diagnostic only; never counts as independent absolute accuracy"))
    rt.dump("dense_diagnostics.json", dict(slices=rows, oracle_standard=oracle_scores))


def semantic_sensitivity(common, options):
    a = load_arrays("dense.npz")
    rows = []
    for tag, other in (("level1", sim.Options(level=1)), ("level4", sim.Options(level=4)),
                       ("Q8_front", sim.Options(quantize_front=True))):
        for mode in sim.MODES:
            use = (a["band"] == 4) & a[mode + "_valid"] & (a["role"] == "colour")
            p = predict(a, mode, common, other)
            baseline = predict(a, mode, common, options)
            rows.append(dict(hypothesis=tag, mode=mode, error=rt.stats(rt.de(p[use], a[mode][use])),
                             change_vs_primary=rt.stats(rt.de(p[use], baseline[use])), recalibrated=False))
    rt.dump("semantic_sensitivity.json", rows)


def exposure_diagnostics(common, options):
    """Fit only held-out Standard for diagnosis. Results never replace the frozen model."""
    a = load_arrays("natural.npz")
    rows = []
    for frame in np.unique(a["frame"]):
        use = a["frame"] == frame
        actual, scene = a["standard"][use], a["scene"][use]
        radial = 2 ** np.interp(a["radius"][use], common["radius"], common["radial_ev"])
        def render(ev, shading=True):
            return sim.render_scene(scene * (radial[:, None] if shading else 1.) * 2 ** ev,
                                    "standard", common, options)
        solution = minimize_scalar(lambda ev: float(np.mean((render(ev) - actual) ** 2)),
                                   bounds=(-2., 2.), method="bounded", options={"xatol": 1e-6})
        rows.append(dict(frame=str(frame), n=int(use.sum()), fitted_ev=float(solution.x),
            fixed=components(render(0), actual), fitted_standard_ev=components(render(solution.x), actual),
            radial_off=components(render(0, False), actual),
            independent_validation=False, heldout_JPEG_used_to_fit_this_diagnostic=True,
            style_JPEG_used=False, accepted_model_changed=False))
    rt.dump("exposure_diagnostics.json", rows)


def main():
    scores = []
    for tag in ("primary_pre_hard", "pre_linear", "ma_off", "requested_post_hard"):
        state = rt.read(rt.LOCAL / f"calibration/{tag}.json")
        common, options = state["common"], sim.Options(**state["options"])
        scores += natural_scores(common, options, tag)
    rt.dump("natural_scores.json", scores)
    state = rt.read(rt.LOCAL / "calibration/primary_pre_hard.json")
    common, options = state["common"], sim.Options(**state["options"])
    dense_diagnostics(common, options)
    semantic_sensitivity(common, options)
    exposure_diagnostics(common, options)
    dense = rt.read(rt.LOCAL / "scores.json")
    checks = []
    for mode in ("positive", "negative"):
        absolute = next(s for s in dense if s["model"] == "primary_pre_hard" and s["split"] == "held_page4" and s["mode"] == mode and s["kind"] == "absolute")
        natural = next(s for s in scores if s["model"] == "primary_pre_hard" and s["coordinate"] == "scene" and s["frame"] == "pooled" and s["mode"] == mode)
        checks.append(dict(mode=mode, held_dense_median=absolute["median"],
            held_natural_median=natural["metric"]["DeltaE00"]["median"],
            passed=absolute["median"] <= 1.0 and natural["metric"]["DeltaE00"]["median"] <= 1.0))
    accepted = all(c["passed"] for c in checks)
    rt.dump("gate.json", dict(accepted=accepted, checks=checks, threshold=1.0,
        reason="absolute real-photo holdouts exceed threshold" if not accepted else "holdout gate passed",
        old_bridge_uncertainty_not_same_metric=True, GXR_refit_authorized_by_gate=accepted,
        proposed_target_definition_differs=True, existing_target_modified=False,
        style_pixels_used_for_calibration=False))
    print("GXR analytic-target refit gate:", "PASS" if accepted else "FAIL", checks, flush=True)


if __name__ == "__main__":
    main()
