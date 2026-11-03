#!/usr/bin/env python3
"""Chart scene colorimetry measured in the GXR DNGs vs the X-Rite published values. Analysis only.

Usage
  python3 -I research/color_table_fit/dng_chart_check.py [--fuji-zip PATH]

Reads (read-only, SHA-256 checked before and after) the nine stage 2e frames and the stage 2d 04 frame
(another session of the same DIOPTIX chart). Writes local/dng_chart_check.json (photo-derived: local only).

(a) Per patch CIEDE2000 between DNG-derived Lab (D50 PCS, DNG 1.7 pipeline in dng_scene.py) and the X-Rite
    published Lab (D50), for both white references, with the exposure fixed by D4 = published D4 Y, and
    again with L* matched (chromaticity only). This mixes the DIOPTIX-vs-X-Rite difference and the DNG
    matrix error; the two cannot be separated with these captures.
(c) Neutral a*b* after adaptation; grey-scale Y ratios Y(Dk)/Y(D4) against the published ones.
Also: the JPEG/raw mapping check of every frame; repeatability of the DNG scene over the nine frames and
against the stage 2d session; matrix sensitivity (interpolated vs ColorMatrix1-only vs ColorMatrix2-only,
SDK vs CIE illuminant temperatures) on the scene and on the Fuji targets; propagated standard errors.
"""
import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
CAP2E = ROOT / "captures/a12-50/2026-10-19/stage2e-colorchecker"
CAP2D = ROOT / "captures/a12-50/2026-10-19/stage2d-colorchecker"
M2D_FILE = ROOT / "research/stage2d_verification/measurements.json"
BASE = "R8051160"
D50_WHITE = np.array([0.96422, 1.0, 0.82521])     # Lab white of the published values (as fit_fuji)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fs = load_module("fit_sectors", HERE / "fit_sectors.py")
ds = fs.dsm()
LABELS, NEUTRAL = fs.LABELS, fs.NEUTRAL


def st(xs):
    return fs.stats(xs)


def lab50(xyz):
    return ds.xyz_to_lab(np.asarray(xyz, float), D50_WHITE)


def frame(dng_p, rois, guard, matrix="interp", white_patches=("D2", "D3", "D4")):
    """DNG scene of one chart frame: CFA stats in the given ROIs, both whites, PCS (D50) XYZ per white."""
    jpg_p = dng_p.with_suffix(".JPG")
    for p in (dng_p, jpg_p):
        guard.add(p)
    sc = ds.DngScene(dng_p, jpg_p, matrix=matrix)
    sts = {l: sc.stats({"rect": r}) for l, r in rois.items()}
    wif = sc.white_in_frame([sts[l]["cam"] for l in white_patches])
    whites = {"as_shot": (sc.white_as_shot, sc.white_as_shot_info), "in_frame": wif}
    pcs = {}
    for w, (wxy, _) in whites.items():
        M = sc.col.camera_to_pcs(wxy)
        pcs[w] = {l: (M @ np.array(s["cam"]), ds.propagate_se(M, s["se"])) for l, s in sts.items()}
    return {"scene": sc, "stats": sts, "whites": whites, "pcs": pcs}


def anchored(pcs_w, y_d4):
    """Scale PCS XYZ so D4 has Y = y_d4."""
    k = y_d4 / pcs_w["D4"][0][1]
    return {l: v * k for l, (v, _) in pcs_w.items()}, k


def lab_se_de00(xyz, se, n=200, rng=None):
    """RMS CIEDE2000 of the Lab of xyz under Gaussian XYZ noise of standard error se (Monte Carlo)."""
    rng = rng or np.random.default_rng(1)
    base = lab50(xyz)
    draws = lab50(xyz[None, :] + rng.normal(size=(n, 3)) * se[None, :])
    return float(np.sqrt(np.mean(fs.delta_e00(np.repeat(base[None, :], n, 0), draws) ** 2)))


def compare(labd, labp):
    """Per patch dE00 (full and with L* matched) and components."""
    rows = []
    for l in LABELS:
        d, p = labd[l], labp[l]
        dm = d.copy()
        dm[0] = p[0]
        Ld, Cd, hd = fs.lch(d)
        Lp, Cp, hp = fs.lch(p)
        rows.append({"label": l, "name": fs.NAMES[l], "neutral": l in NEUTRAL, "lab_dng": d.tolist(),
                     "lab_published": p.tolist(), "dL": float(d[0] - p[0]), "da": float(d[1] - p[1]),
                     "db": float(d[2] - p[2]), "dC": float(Cd - Cp),
                     "dh_deg": float((hd - hp + 180) % 360 - 180) if l not in NEUTRAL else None,
                     "de00": float(fs.delta_e00(d, p)), "de00_L_matched": float(fs.delta_e00(dm, p))})
    summ = {}
    for key in ("de00", "de00_L_matched"):
        summ[key] = {"neutral": st([r[key] for r in rows if r["neutral"]]),
                     "chromatic": st([r[key] for r in rows if not r["neutral"]]),
                     "all": st([r[key] for r in rows])}
    return rows, summ


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fuji-zip", default=str(fs.FUJI_ZIP))
    args = ap.parse_args()
    LOCAL.mkdir(parents=True, exist_ok=True)
    guard = ds.CaptureGuard()
    m2e = json.loads(fs.S2E.read_text())
    fuji = json.loads(fs.FUJI_FIT.read_text())
    pubp = {p["label"]: p for p in fuji["chart_patches"]["classic_chrome"]}
    pub_lab = {l: np.array(pubp[l]["published_Lab_D50"]) for l in LABELS}
    pub_xyz = {l: fs.lab_to_xyz(pub_lab[l], D50_WHITE) for l in LABELS}
    y_pub_d4 = float(pub_xyz["D4"][1])
    out = {"inputs": {}, "published_source": "research/fuji_phase2/local/fit.json chart_patches.*.published_Lab_D50 "
                                              "(X-Rite 2014+ ColorChecker, D50)"}

    # --- all nine stage 2e frames
    frames = {}
    for stem, fr in sorted(m2e["frames"].items()):
        rois = {p["label"]: p["roi"] for p in fr["patches"]}
        frames[stem] = frame(CAP2E / f"{stem}.DNG", rois, guard)
    base = frames[BASE]
    out["base_frame"] = BASE
    out["dng_tags"] = {k: v for k, v in base["scene"].dng.summary().items()}
    out["mapping"] = {}
    for stem, f in frames.items():
        v = f["scene"].verify
        out["mapping"][stem] = {"tiles_used": v.get("tiles_used"), "tiles_total": v.get("tiles_total"),
                                "shift_mean_xy": v.get("shift_mean_xy"),
                                "translation_residual_rms_px": v.get("translation_residual_rms_px"),
                                "translation_residual_max_px": v.get("translation_residual_max_px"),
                                "affine_scale_minus_1_xy": v.get("affine", {}).get("scale_minus_1_xy"),
                                "affine_rotation_mrad": v.get("affine", {}).get("rotation_mrad"),
                                "affine_residual_rms_px": v.get("affine", {}).get("residual_rms_px"),
                                "offset_applied_xy": f["scene"].map.offset,
                                "after_offset_shift_xy": (v.get("after_offset") or {}).get("shift_mean_xy"),
                                "after_offset_residual_rms_px": (v.get("after_offset") or {}).get(
                                    "translation_residual_rms_px")}

    # --- (a) and (c) on the base frame, both whites
    res = {}
    for w in ("as_shot", "in_frame"):
        xyz, k = anchored(base["pcs"][w], y_pub_d4)
        labd = {l: lab50(xyz[l]) for l in LABELS}
        rows, summ = compare(labd, pub_lab)
        rng = np.random.default_rng(7)
        for r in rows:
            v, se = base["pcs"][w][r["label"]]
            r["de00_se"] = lab_se_de00(v * k, se * k, rng=rng)
            r["cam"] = base["stats"][r["label"]]["cam"]
            r["cam_se"] = base["stats"][r["label"]]["se"]
            r["n_sites"] = base["stats"][r["label"]]["n"]
            r["raw_max_frac_of_white"] = base["stats"][r["label"]]["max_frac_of_white"]
        neutrals = {l: {"a": float(labd[l][1]), "b": float(labd[l][2]), "C": float(math.hypot(labd[l][1], labd[l][2]))}
                    for l in fs.LABELS if l in NEUTRAL}
        yr = {l: {"Y_dng_over_D4": float(xyz[l][1] / xyz["D4"][1]), "Y_pub_over_D4": float(pub_xyz[l][1] / y_pub_d4),
                  "ratio_dng_over_pub": float((xyz[l][1] / xyz["D4"][1]) / (pub_xyz[l][1] / y_pub_d4)),
                  "stops_dng_vs_pub": float(math.log2((xyz[l][1] / xyz["D4"][1]) / (pub_xyz[l][1] / y_pub_d4)))}
              for l in ("D1", "D2", "D3", "D4", "D5", "D6")}
        res[w] = {"white": base["whites"][w][1], "anchor": {"Y_D4": y_pub_d4, "scale_k": k},
                  "per_patch": rows, "summary": summ, "neutral_ab_after_adaptation": neutrals,
                  "grey_Y_ratios": yr, "de00_se_max": max(r["de00_se"] for r in rows)}
    out["base_vs_published"] = res
    wa, wi = base["whites"]["as_shot"][1], base["whites"]["in_frame"][1]
    xa, xi = base["pcs"]["as_shot"], base["pcs"]["in_frame"]
    de_w = [float(fs.delta_e00(lab50(anchored(xa, y_pub_d4)[0][l]), lab50(anchored(xi, y_pub_d4)[0][l]))) for l in LABELS]
    out["white_difference"] = {
        "as_shot_xy": wa["white_xy"], "in_frame_xy": wi["white_xy"],
        "as_shot_cct_tint": [wa["cct_K"], wa["tint"]], "in_frame_cct_tint": [wi["cct_K"], wi["tint"]],
        "delta_uv": float(np.hypot(*(np.array(uv(wa["white_xy"])) - np.array(uv(wi["white_xy"]))))),
        "in_frame_members_rb_sd": wi["member_spread_rb_sd"],
        "de00_scene_between_whites": {"neutral": st([d for d, l in zip(de_w, LABELS) if l in NEUTRAL]),
                                      "chromatic": st([d for d, l in zip(de_w, LABELS) if l not in NEUTRAL])}}

    # --- repeatability: every 2e frame vs the base (own ROIs, own white), D4 anchored
    rep = {}
    for w in ("in_frame", "as_shot"):
        ref = {l: lab50(v) for l, v in anchored(base["pcs"][w], y_pub_d4)[0].items()}
        per = {}
        for stem, f in frames.items():
            if stem == BASE:
                continue
            labf = {l: lab50(v) for l, v in anchored(f["pcs"][w], y_pub_d4)[0].items()}
            d = [float(fs.delta_e00(labf[l], ref[l])) for l in LABELS]
            per[stem] = {"identified": m2e["order"][stem]["identified"], "asn": m2e["order"][stem]["asn"],
                         "white_cct_tint": [f["whites"][w][1]["cct_K"], f["whites"][w][1]["tint"]],
                         "de00_vs_base": st(d)}
        rep[w] = per
    out["repeatability_2e_frames"] = rep

    # --- another session: stage 2d 04 frame (chart rotated, own ROIs)
    m2d = json.loads(M2D_FILE.read_text())
    f2d = m2d["frames"]["04_std"]
    rois2d = {p["label"]: p["roi"] for p in f2d["patches"]}
    s2d = frame(CAP2D / f"{f2d['file']}.DNG", rois2d, guard)
    sess = {}
    for w in ("in_frame", "as_shot"):
        ref = {l: lab50(v) for l, v in anchored(base["pcs"][w], y_pub_d4)[0].items()}
        lab2 = {l: lab50(v) for l, v in anchored(s2d["pcs"][w], y_pub_d4)[0].items()}
        d = {l: float(fs.delta_e00(lab2[l], ref[l])) for l in LABELS}
        rows2, summ2 = compare(lab2, pub_lab)
        sess[w] = {"white": s2d["whites"][w][1], "de00_vs_2e_base": {"neutral": st([d[l] for l in LABELS if l in NEUTRAL]),
                                                                     "chromatic": st([d[l] for l in LABELS if l not in NEUTRAL]),
                                                                     "per_patch": d},
                   "vs_published": summ2, "dL_per_patch_vs_published": {r["label"]: r["dL"] for r in rows2}}
    out["stage2d_session"] = {"file": f2d["file"], "mapping": {k: s2d["scene"].verify.get(k) for k in
                                                               ("shift_mean_xy", "translation_residual_rms_px", "tiles_used")},
                              **sess}

    # --- matrix sensitivity on the base frame: interp vs cm1 vs cm2, and CIE vs SDK illuminant temperatures
    rois = {p["label"]: p["roi"] for p in m2e["frames"][BASE]["patches"]}
    variants = {"interp": base}
    for mm in ("cm1", "cm2"):
        variants[mm] = frame(CAP2E / f"{BASE}.DNG", rois, guard, matrix=mm)
    saved = dict(ds.ILLUMINANT_K)
    try:
        ds.ILLUMINANT_K[17], ds.ILLUMINANT_K[21] = 2856.0, 6504.0
        variants["interp_cie_temps"] = frame(CAP2E / f"{BASE}.DNG", rois, guard)
    finally:
        ds.ILLUMINANT_K.clear()
        ds.ILLUMINANT_K.update(saved)
    ctx = fs.Context(argparse.Namespace(u_m=None))
    e = ctx.anchor_ratio(None)[0]
    a = fuji["anchor"]
    y_d4_metered = 0.18 * (e * ctx.u04["D4"] - a["f"]) / (a["u_m"] - a["f"])
    lut = fs.FujiLUT(Path(args.fuji_zip))
    sens = {"e": e, "Y_D4_metered": y_d4_metered, "weights_cm_low_T": {}}
    for w in ("as_shot", "in_frame"):
        scenes, targets = {}, {}
        for name, f in variants.items():
            sens["weights_cm_low_T"].setdefault(name, {})[w] = f["whites"][w][1]["weight_cm_low_T"]
            pcs_d65 = {l: ds.bradford(ds.D50_XY, ds.D65_XY) @ v for l, (v, _) in f["pcs"][w].items()}
            kk = y_d4_metered / pcs_d65["D4"][1]
            scenes[name] = {l: v * kk for l, v in pcs_d65.items()}
            if lut.ok:
                targets[name] = {sim: {l: fs.lab_from_codes(lut.render_xyz(sim, scenes[name][l])) for l in LABELS}
                                 for sim in ("classic_chrome", "classic_neg")}
        cmp_ = {}
        for name in variants:
            if name == "interp":
                continue
            ds_ = [float(fs.delta_e00(fs.xyz_to_lab(scenes[name][l]), fs.xyz_to_lab(scenes["interp"][l]))) for l in LABELS]
            rec = {"scene_de00_vs_interp": {"neutral": st([d for d, l in zip(ds_, LABELS) if l in NEUTRAL]),
                                            "chromatic": st([d for d, l in zip(ds_, LABELS) if l not in NEUTRAL])},
                   "white_cct": variants[name]["whites"][w][1]["cct_K"]}
            if lut.ok:
                for sim in ("classic_chrome", "classic_neg"):
                    dt = [float(fs.delta_e00(targets[name][sim][l], targets["interp"][sim][l])) for l in LABELS]
                    rec[f"target_de00_vs_interp_{sim}"] = {"neutral": st([d for d, l in zip(dt, LABELS) if l in NEUTRAL]),
                                                           "chromatic": st([d for d, l in zip(dt, LABELS) if l not in NEUTRAL])}
            cmp_[name] = rec
        sens[w] = cmp_
    out["matrix_sensitivity"] = sens
    out["captures"] = guard.after()
    (LOCAL / "dng_chart_check.json").write_text(json.dumps(fs.sm.jsonable(out), indent=1, default=float) + "\n")
    print_summary(out)
    if not out["captures"]["all_unchanged"]:
        raise SystemExit("a capture changed")


def uv(xy):
    x, y = xy
    d = -2 * x + 12 * y + 3
    return 4 * x / d, 6 * y / d


def fmt(s):
    return "-" if not s or not s.get("n") else f"{s['median']:.2f}/{s['p90']:.2f}/{s['max']:.2f}"


def print_summary(o):
    print("== JPEG/raw mapping (shift raw = jpeg + s, px; residual rms px)")
    for stem, m in o["mapping"].items():
        print(f"  {stem}: shift {np.round(m['shift_mean_xy'], 3).tolist()} resid {m['translation_residual_rms_px']:.3f}"
              f" (max {m['translation_residual_max_px']:.3f}) tiles {m['tiles_used']}/{m['tiles_total']} affine scale-1 "
              f"{np.round(m['affine_scale_minus_1_xy'], 6).tolist()} rot {m['affine_rotation_mrad']:.3f} mrad; offset "
              f"{m['offset_applied_xy']} -> residual shift {np.round(m['after_offset_shift_xy'] or [0, 0], 3).tolist()}")
    wd = o["white_difference"]
    print(f"== whites: as_shot xy {np.round(wd['as_shot_xy'], 5).tolist()} CCT/tint {np.round(wd['as_shot_cct_tint'], 1).tolist()}"
          f"; in_frame xy {np.round(wd['in_frame_xy'], 5).tolist()} CCT/tint {np.round(wd['in_frame_cct_tint'], 1).tolist()}"
          f"; duv {wd['delta_uv']:.4f}; scene dE00 between whites neutral {fmt(wd['de00_scene_between_whites']['neutral'])}"
          f" chromatic {fmt(wd['de00_scene_between_whites']['chromatic'])}")
    for w, r in o["base_vs_published"].items():
        s = r["summary"]
        print(f"== (a) {BASE} DNG vs X-Rite published, white {w} (D4 at published Y), dE00 median/p90/max")
        print(f"  full     neutral {fmt(s['de00']['neutral'])}  chromatic {fmt(s['de00']['chromatic'])}")
        print(f"  L*-matched neutral {fmt(s['de00_L_matched']['neutral'])}  chromatic {fmt(s['de00_L_matched']['chromatic'])}"
              f"   (max SE in dE00 {r['de00_se_max']:.3f})")
        print("  " + " ".join(f"{p['label']}:{p['de00']:.1f}({p['dL']:+.1f})" for p in r["per_patch"]))
        print("  (c) neutral a*/b*: " + " ".join(f"{l} {v['a']:+.2f}/{v['b']:+.2f}" for l, v in r["neutral_ab_after_adaptation"].items()))
        print("      Y/Y(D4) dng vs pub: " + " ".join(f"{l} {v['Y_dng_over_D4']:.3f}/{v['Y_pub_over_D4']:.3f}"
                                                   for l, v in r["grey_Y_ratios"].items()))
    for w, per in o["repeatability_2e_frames"].items():
        print(f"== repeatability over 2e frames, white {w}: chromatic+neutral dE00 vs {BASE} (median/p90/max)")
        print("  " + "; ".join(f"{s}({v['identified']}) {fmt(v['de00_vs_base'])}" for s, v in per.items()))
    s2 = o["stage2d_session"]
    for w in ("in_frame", "as_shot"):
        print(f"== stage 2d session {s2['file']} white {w}: vs 2e base neutral {fmt(s2[w]['de00_vs_2e_base']['neutral'])} "
              f"chromatic {fmt(s2[w]['de00_vs_2e_base']['chromatic'])}; vs published chromatic "
              f"{fmt(s2[w]['vs_published']['de00']['chromatic'])}; white CCT {s2[w]['white']['cct_K']:.0f}")
    ms = o["matrix_sensitivity"]
    print(f"== matrix sensitivity (D4 metered Y {ms['Y_D4_metered']:.4f}); weights {ms['weights_cm_low_T']}")
    for w in ("as_shot", "in_frame"):
        for name, rec in ms[w].items():
            line = f"  {w} {name}: scene neutral {fmt(rec['scene_de00_vs_interp']['neutral'])} chromatic " \
                   f"{fmt(rec['scene_de00_vs_interp']['chromatic'])}"
            for sim in ("classic_chrome", "classic_neg"):
                k = f"target_de00_vs_interp_{sim}"
                if k in rec:
                    line += f"; {sim} targets chromatic {fmt(rec[k]['chromatic'])}"
            print(line)
    c = o["captures"]
    print(f"== captures read {len(c['files'])}, unchanged {c['all_unchanged']}, with reference {c['n_with_reference']}, "
          f"none mismatching {c['none_mismatch_reference']}")


if __name__ == "__main__":
    main()
