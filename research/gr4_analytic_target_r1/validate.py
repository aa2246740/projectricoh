"""Standard-only calibration with complete page 4 and all natural photos held out."""
from pathlib import Path
import json
import sys
from dataclasses import asdict
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import simulator as sim
from scipy.optimize import least_squares

RADII = np.array([0., .25, .5, .75, 1.])
OFF = [(i, j) for i in range(3) for j in range(3) if i != j]


def load_arrays(name):
    with np.load(rt.LOCAL / name, allow_pickle=False) as z:
        return dict(z)


def common_of(p, gain):
    matrix = np.eye(3)
    for v, (i, j) in zip(p[:6], OFF):
        matrix[i, j] = v
    for i in range(3):
        matrix[i, i] = 1 - sum(matrix[i, j] for j in range(3) if j != i)
    base = matrix.copy()
    wb = 2 ** np.array([p[6], 0., p[7]])
    matrix = matrix @ np.diag(wb)
    return dict(matrix=matrix, matrix_base=base, wb_correction=wb, exposure_ev=p[8], gain=int(gain),
        radius=RADII, radial_ev=np.r_[0., p[9:13]])


def with_radial(raw, radius, common):
    return raw * 2 ** np.interp(radius, common["radius"], common["radial_ev"])[..., None]


def predict(a, mode, common, options, index=None):
    index = np.arange(len(a["raw_wb"])) if index is None else index
    raw = with_radial(a["raw_wb"][index], a["radius"][index], common)
    if "baseline_exposure" in a:
        raw *= 2 ** (a["baseline_exposure"][index] - common["template_baseline_exposure"])[..., None]
    return sim.render(raw, mode, common, options)


def fit(a, options, tag, gains=None):
    train = (a["band"] < 4) & a["standard_valid"]
    # No held-page means, radial correction, WB, exposure or style values enter this function.
    index = np.flatnonzero(train)
    prior = np.asarray(sim.parameters()["modes"]["standard"]["sensor"], float).reshape(3, 3) / 8192
    p0 = np.r_[[prior[i, j] for i, j in OFF], 0., 0., -.5, .2, .45, .75, 1.1]
    lower = np.r_[np.repeat(-1.5, 6), -.5, -.5, -3., np.repeat(-.5, 4)]
    upper = np.r_[np.repeat(1.5, 6), .5, .5, 3., np.repeat(2.5, 4)]
    # Weights balance the neutral/radial calibration blocks against the many color blocks.
    role = a["role"][index]
    weights = np.where(np.isin(role, ["reference", "radial", "tone"]), 2., 1.)
    observations = a["standard"][index]
    attempts = []
    best = None
    if gains is None:
        gains = [4096, 6144, 8192, 11222, 14336, 18432, 24576]
    def solve_gain(gain):
        def residual(p):
            common = common_of(p, gain)
            result = predict(a, "standard", common, options, index)
            regularizer = np.r_[(p[:6] - p0[:6]) * .004, p[6:8] * .005,
                np.diff(p[9:13], n=2) * .01]
            return np.r_[((result - observations) * weights[:, None]).ravel(), regularizer]
        result = least_squares(residual, p0, bounds=(lower, upper), loss="soft_l1", f_scale=.02,
            max_nfev=140, diff_step=2e-4, ftol=2e-7, xtol=2e-7, gtol=2e-7)
        common = common_of(result.x, gain)
        errors = rt.de(predict(a, "standard", common, options, index), observations)
        attempt = dict(gain=gain, solver_success=bool(result.success), evaluations=result.nfev,
            cost=float(result.cost), training_standard=rt.stats(errors), parameters=result.x)
        attempts.append(attempt)
        print(tag, "gain", gain, "train Standard median", round(float(np.median(errors)), 4),
              "nfev", result.nfev, "success", result.success, flush=True)
        return result.cost, common, result.x
    for gain in gains:
        solved = solve_gain(gain)
        if best is None or solved[0] < best[0]:
            best = solved
    # Resolve the coarse minimum using Standard training observations only.
    coarse_best = int(best[1]["gain"])
    for gain in range(max(1024, coarse_best - 2048), min(65535, coarse_best + 2048) + 1, 256):
        if gain in gains:
            continue
        solved = solve_gain(gain)
        if solved[0] < best[0]:
            best = solved
    common = best[1]
    dense_audit = rt.read(rt.LOCAL / "dense_audit.json")
    common["raw_wb_to_scene"] = dense_audit[0]["raw_wb_to_scene"]
    common["template_baseline_exposure"] = dense_audit[0]["geometry"]["baseline_exposure"]
    rt.dump(f"calibration/{tag}.json", dict(common=common, options=asdict(options),
        train_pages=[1, 2, 3], held_pages=[4], train_n=len(index), training_keys=a["id"][index],
        any_style_used_for_fit=False, held_photos_used_for_fit=False, attempts=attempts,
        gamma_gain_selection="minimum robust Standard-only training RGB cost, never style/held-out error"))
    return common


def relative(base, standard, styled):
    cs, cm, cb = [np.hypot(x[..., 1], x[..., 2]) for x in (standard, styled, base)]
    active = (cs >= 8) & (cm >= 8) & (cb >= 8)
    quotient = np.ones(cs.shape, complex)
    np.divide(styled[..., 1] + 1j * styled[..., 2], standard[..., 1] + 1j * standard[..., 2],
              out=quotient, where=active)
    ab = (base[..., 1] + 1j * base[..., 2]) * quotient
    return np.stack([base[..., 0] + styled[..., 0] - standard[..., 0], ab.real, ab.imag], axis=-1)


def evaluate_dense(a, common, options, tag):
    rows = []
    saved = {}
    for mode in sim.MODES:
        pred = predict(a, mode, common, options)
        saved[mode] = pred
        observed = a[mode]
        for group, mask in (("train", a["band"] < 4), ("held_page4", a["band"] == 4)):
            use = mask & a[mode + "_valid"] & np.isin(a["role"], ["colour", "tone", "reference", "natural"])
            errors = rt.de(pred[use], observed[use])
            rr = dict(model=tag, split=group, mode=mode, kind="absolute",
                evidence="对真实 GR IV 照片的验证", **rt.stats(errors))
            rows.append(rr)
            print(tag, group, mode, rr.get("median"), rr.get("p90"), rr["n"], flush=True)
        for band in range(1, 5):
            use = (a["band"] == band) & a[mode + "_valid"] & (a["role"] == "colour")
            rows.append(dict(model=tag, split=f"page{band}_colors", mode=mode, kind="absolute", **rt.stats(rt.de(pred[use], observed[use]))))
    for mode in ("positive", "negative"):
        for group, mask in (("train", a["band"] < 4), ("held_page4", a["band"] == 4)):
            use = mask & a[mode + "_valid"] & a["standard_valid"] & np.isin(a["role"], ["colour", "tone", "reference", "natural"])
            baseline, actual = rt.lab(a["standard"][use]), rt.lab(a[mode][use])
            ps, pm = rt.lab(saved["standard"][use]), rt.lab(saved[mode][use])
            rel = relative(baseline, ps, pm)
            vector = baseline + pm - ps
            errors = rt.cm.delta_e00(rel, actual)
            neutral = np.hypot(baseline[:, 1], baseline[:, 2]) < 8
            rows.append(dict(model=tag, split=group, mode=mode, kind="relative_LCh", **rt.stats(errors),
                baseline_standard_to_mode=rt.stats(rt.cm.delta_e00(baseline, actual)),
                deltaLab_vector_error=rt.stats(rt.cm.delta_e00(vector, actual)),
                neutral=rt.stats(errors[neutral]), chromatic=rt.stats(errors[~neutral])))
    np.savez_compressed(rt.LOCAL / f"predictions_{tag}.npz", **saved)
    return rows


def evaluate_natural(common, options, tag):
    a = load_arrays("natural.npz")
    pred = predict(a, "standard", common, options)
    rows = []
    for frame in np.unique(a["frame"]):
        use = a["frame"] == frame
        rows.append(dict(model=tag, frame=str(frame), mode="standard", kind="natural_absolute",
            split="whole_photo_holdout", **rt.stats(rt.de(pred[use], a["standard"][use]))))
    rows.append(dict(model=tag, frame="pooled", mode="standard", kind="natural_absolute",
        split="whole_photo_holdout", **rt.stats(rt.de(pred, a["standard"]))))
    return rows


def main():
    a = load_arrays("dense.npz")
    hypotheses = [("primary_pre_hard", sim.Options()),
        ("pre_linear", sim.Options(sectors="linear")),
        ("ma_off", sim.Options(sectors="off")),
        ("requested_post_hard", sim.Options(order="after_gamma"))]
    all_scores = []
    for tag, options in hypotheses:
        common = fit(a, options, tag)
        all_scores += evaluate_dense(a, common, options, tag)
        all_scores += evaluate_natural(common, options, tag)
        rt.dump("scores.json", all_scores)
    rt.dump("gate.json", dict(accepted=False, decision="pending complete natural-mode validation",
        threshold=1.0, criterion="held-out real Positive/Negative median DeltaE00 <= 1.0; no style calibration"))


if __name__ == "__main__":
    main()
