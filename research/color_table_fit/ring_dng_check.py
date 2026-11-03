#!/usr/bin/env python3
"""End-to-end check of the ring DNG scene path before the hue-ring photos exist. Analysis only.

Usage
  python3 -I research/color_table_fit/ring_dng_check.py [--part synthetic|screen|both] [--quick]

A. synthetic: hue_ring.png rendered into a camera frame (analyze_ring.render_base), written as a GXR-like
   12-bit DNG (big-endian, crop origin (8, 7), RGGB) from a known scene XYZ through an invented two-
   illuminant camera matrix, plus a JPEG shifted 1 px right of the raw crop as the GXR's are. Then the real
   path: analyze_ring.load_frame -> ring_patches.json (written to /tmp), fit_sectors with
   --ring-scene-source design and dng (as_shot and in_frame), and a frame whose AsShotNeutral is wrong.
   Pass: DNG ring scenes reproduce the design scene, the ring targets and rows agree.
B. screen: the 2026-10-16 MacBook screen-chart frames (GXR DNG+JPG, ROI masks from that analysis):
   the mask path against that analysis's raw means (identity mapping), the JPEG/raw offset, and how far the
   DNG-derived XYZ of real screen colours lies from their nominal sRGB (panel + metamerism + DNG matrix):
   the size of the change --ring-scene-source dng will make.

Writes /tmp/gxr_ring_dng_check/ (synthetic frames) and local/ring_dng_check.json. Captures are read-only
and SHA-256 checked before and after. No Ricoh matrix is embedded: part A uses an invented camera.
"""
import argparse
import importlib.util
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
TMP = Path("/tmp/gxr_ring_dng_check")
SCREEN = ROOT / "captures/a12-50/2026-10-16/macbook-screen-chart"
SCREEN_CHART = ROOT / "research/color_references/screen_chart.json"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fs = load_module("fit_sectors", HERE / "fit_sectors.py")
ds = fs.dsm()


def fmt(s):
    return "-" if not s or not s.get("n") else f"{s['median']:.3f}/{s['p90']:.3f}/{s['max']:.3f}"


# ----------------------------------------------------------------- A. synthetic ring frames

def synthetic(args):
    t0 = time.time()
    ar = fs.arm()
    lay = ar.load_layout()
    frames = TMP / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    for p in frames.iterdir():
        if p.suffix.upper() in (".DNG", ".JPG", ".JSON"):
            p.unlink()
    W, H = (4288, 2848)
    rng = np.random.default_rng(20261020)
    # screen -> image homography, as analyze_ring's image self-test (small rotation and perspective)
    s, th = 1.12, math.radians(1.3)
    A = np.array([[s * math.cos(th), -s * math.sin(th), 0], [s * math.sin(th), s * math.cos(th), 0], [0, 0, 1]])
    A[0, 2] = W / 2 - (A[0, 0] * 1728 + A[0, 1] * 1117)
    A[1, 2] = H / 2 - (A[1, 0] * 1728 + A[1, 1] * 1117)
    Hm = np.array([[1, 0, 0], [0, 1, 0], [1.5e-6, -1.0e-6, 1]]) @ A
    Hm = Hm / Hm[2, 2]
    base = ar.render_base(Hm, (H, W), 1.6)                  # linear design sRGB of the screen, defocused
    print(f"[A] rendered base {time.time() - t0:.1f} s", flush=True)
    # invented camera; a template DNG to get the reader's own XYZ->camera at the screen white
    tmpl = ds.write_dng(TMP / "template.dng", np.zeros((16, 16), np.uint16), cm1=ds.INVENTED_CM_A,
                        cm2=ds.INVENTED_CM_D65, crop_origin=(0, 0))
    col = ds.DngColour(ds.Dng(tmpl))
    w_screen = np.array([0.3221, 0.3318])                     # a screen white near 6000 K, not D65
    w_wrong = np.array([0.3457, 0.3585])                      # an AsShotNeutral for D50: a wrong WB
    M_scene = col.xyz_to_camera(w_screen) @ ds.bradford(ds.D65_XY, w_screen)   # design XYZ -> camera
    cam_white = col.xyz_to_camera(w_screen) @ ds.xy_to_xyz(w_screen)
    gain = 0.75 / cam_white.max()
    neutral_ok = cam_white / cam_white.max()
    cw = col.xyz_to_camera(w_wrong) @ ds.xy_to_xyz(w_wrong)
    neutral_wrong = cw / cw.max()
    m_lin_to_cam = (M_scene @ fs.M709 * gain).astype(np.float32)           # design linear sRGB -> camera
    cam_img = (base.reshape(-1, 3) @ m_lin_to_cam.T).reshape(H, W, 3)
    jpeg_lin = base
    files = {}
    for role, neutral, seed in (("04a", neutral_ok, 1), ("04b", neutral_ok, 2), ("04x", neutral_wrong, 3)):
        r = np.random.default_rng(seed)
        mosaic = ds.mosaic_from_cam(cam_img, (0, 1, 1, 2), (8, 7), (H + 14, W + 16), rng=r, noise_dn=2.0)
        stem = f"S{len(files):02d}_{role}_iso100"
        dng = ds.write_dng(frames / f"{stem}.DNG", mosaic, as_shot_neutral=neutral, cm1=ds.INVENTED_CM_A,
                           cm2=ds.INVENTED_CM_D65, crop_origin=(8, 7), crop_size=(W, H), baseline_exposure=0.3,
                           exif={34855: (3, [100]), 33434: (5, [1 / 30]), 33437: (5, [4.0])})
        img = ar.camera_frame(jpeg_lin, None, None, 1.6, 1.0, r)
        shifted = img.copy()
        shifted[:, 1:] = img[:, :-1]                         # JPEG content 1 px right of the raw, as the GXR
        Image.fromarray(shifted).save(frames / f"{stem}.JPG", quality=95, subsampling=0)
        files[role] = (frames / f"{stem}.JPG", dng)
    print(f"[A] wrote frames {time.time() - t0:.1f} s", flush=True)
    # ring_patches.json through analyze_ring's own frame loader (ROIs, flags, raw checks)
    a_args = argparse.Namespace(inset=40.0, no_raw=False, moire_ratio=40.0, moire_amp=1.2, edge_sd=12.0)
    recs = {}
    for role in ("04a", "04b"):
        jpg, dng = files[role]
        meta = {"iso": 100, "t": 1 / 30, "when": "2026:10:20 10:00:00", "program": 1, "source": "synthetic"}
        rec = ar.load_frame(jpg, dng, meta, lay, a_args)
        if not rec.get("ring"):
            raise SystemExit(f"synthetic frame not recognised as ring: {rec.get('why_not_ring')}")
        recs[role] = rec
    groups = {100: [recs["04a"], recs["04b"]]}
    roles = {100: {recs["04a"]["file"]: "04a", recs["04b"]["file"]: "04b"}}
    rp = TMP / "ring_patches.json"
    ar.write_patch_table(groups, roles, lay, rp)
    flagged = sorted({p["id"] for r in recs.values() for p in r["patches"] if p.get("flags")})
    print(f"[A] ring_patches.json written ({time.time() - t0:.1f} s); flagged ids {flagged}", flush=True)
    # fit_sectors, design vs dng scenes
    runs = {}
    for name, extra in (("design", []), ("dng_as_shot", ["--ring-scene-source", "dng", "--dng-white", "as_shot"]),
                        ("dng_in_frame", ["--ring-scene-source", "dng", "--dng-white", "in_frame"])):
        prefix = f"synthring_{name}_"
        cmd = [sys.executable, "-I", str(HERE / "fit_sectors.py"), "--target", "fuji:classic_chrome",
               "--ring-patches", str(rp), "--ring-iso", "100", "--ring-dir", str(frames), "--smooth", "1",
               "--no-loo", "--out-prefix", prefix] + extra
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise SystemExit(f"fit_sectors {name} failed:\n{p.stdout}\n{p.stderr}")
        runs[name] = json.loads((LOCAL / f"{prefix}fuji_classic_chrome.json").read_text())
        print(f"[A] fit_sectors {name} done ({time.time() - t0:.1f} s)", flush=True)
    ref = {r["label"]: np.array(r["lab_target"]) for r in runs["design"]["per_sample"] if r["source"] == "ring"}
    out = {"frames_dir": str(frames), "ring_patches": str(rp), "screen_white_xy": w_screen.tolist(),
           "flagged_ids": flagged, "runs": {}}
    for name, r in runs.items():
        tg = {s["label"]: np.array(s["lab_target"]) for s in r["per_sample"] if s["source"] == "ring"}
        d = [float(fs.delta_e00(tg[k], ref[k])) for k in ref if k in tg]
        rec = {"n_ring_samples": len(tg), "target_de00_vs_design": fs.stats(d), "row_hex": r["row_hex"],
               "row_equals_design": r["row_hex"] == runs["design"]["row_hex"],
               "ring_summary": r["summary"].get("ring")}
        rs = (r.get("ring_samples") or {}).get("scene")
        if rs:
            rec["scene"] = {k: rs[k] for k in ("de00_scene_dng_vs_design", "de00_between_04_frames",
                                               "de00_ring_scene_between_whites", "raw_clipped_ids_weight0",
                                               "missing_ids", "inset_screen_px", "white")}
            rec["scene"]["map"] = [{"file": f["file"], "shift": f["verify"].get("shift_mean_xy"),
                                    "offset": f["map"]["offset_xy"],
                                    "after": (f["verify"].get("after_offset") or {}).get("shift_mean_xy"),
                                    "whites": {k: [v["cct_K"], v["tint"]] for k, v in f["whites"].items()}}
                                   for f in rs["frames"]]
        if name != "design":
            a, b = np.array(bytes.fromhex(r["row_hex"])), np.array(bytes.fromhex(runs["design"]["row_hex"]))
            rec["row_bytes_differing"] = int(np.sum(a != b))
        out["runs"][name] = rec
    # wrong AsShotNeutral: one frame, both whites, through the fitter's own ring_dng()
    lay_idx = {p["id"]: p for p in lay["patches"]}
    wrong = {}
    for w in ("as_shot", "in_frame"):
        ns = argparse.Namespace(u_m=None, ring_dir=str(frames), ring_inset=40.0, ring_white_ids=fs.RING_WHITE_IDS,
                                dng_white=w, dng_matrix="interp")
        ctx = fs.Context(ns)
        for role in ("04a", "04x"):
            scene, info = ctx.ring_dng([files[role][0].name])
            d = []
            for i, v in scene.items():
                p = lay_idx[i]
                if p["ring"] in (1, 2):
                    lin = fs.srgb_to_linear(np.array(p["srgb8"], float) / 255)
                    d.append(float(fs.delta_e00(fs.xyz_to_lab(v["xyz"]), fs.xyz_to_lab(lin @ fs.M709.T))))
            wrong[f"{role}_{w}"] = {"de00_scene_vs_design": fs.stats(d),
                                    "white_cct_tint": [info["frames"][0]["whites"][w]["cct_K"],
                                                       info["frames"][0]["whites"][w]["tint"]]}
    out["wrong_as_shot_neutral"] = wrong
    out["pass"] = bool(out["runs"]["dng_as_shot"]["target_de00_vs_design"]["max"] < 0.3
                       and out["runs"]["dng_in_frame"]["target_de00_vs_design"]["max"] < 0.3
                       and wrong["04x_in_frame"]["de00_scene_vs_design"]["max"] < 0.3
                       and wrong["04x_as_shot"]["de00_scene_vs_design"]["median"] > 1.0)
    out["seconds"] = round(time.time() - t0, 1)
    return out


# ----------------------------------------------------------------- B. real screen-chart frames

def screen(args, guard):
    t0 = time.time()
    m = json.loads((SCREEN / "measurements.json").read_text())
    chart = json.loads(SCREEN_CHART.read_text())
    nominal = {p["id"]: p for pg in chart["pages"] for p in pg["patches"]}
    caps = {c["shot"]: c for c in m["captures"]}
    res = {"frames": {}}
    raw = {}
    for shot, c in caps.items():
        dng, jpg = SCREEN / f"{shot}.DNG", SCREEN / f"{shot}.JPG"
        for p in (dng, jpg):
            guard.add(p)
        sc = ds.DngScene(dng, jpg)
        rm0 = ds.RawMap(sc.dng, sc.jpeg_info["size_wh"], sc.jpeg_info["orientation"], (0, 0))
        per, xdiff = {}, []
        for p in c["patches"]:
            mask = np.asarray(Image.open(SCREEN / "roi_masks" / f"{shot}_{p['id']}.png")) > 127
            x0, y0 = p["roi_jpeg_bbox_xyxy"][:2]
            region = {"mask": mask, "origin_yx": (y0, x0)}
            st = sc.stats(region)
            st0 = ds.cfa_stats(sc.dng, *ds.roi_pixels(rm0, region))
            xdiff.append(float(np.max(np.abs(np.array(st0["cam"]) - np.array(p["raw_RGB_black_white_normalized"])))))
            per[p["id"]] = st
        v = sc.verify
        res["frames"][shot] = {"page": c["page"], "iso": c["metadata_dng"].get("iso"), "t": c["metadata_dng"].get("exposure"),
                               "map_shift_xy": v.get("shift_mean_xy"), "map_residual_rms_px": v.get("translation_residual_rms_px"),
                               "tiles_used": v.get("tiles_used"), "offset_applied": sc.map.offset,
                               "mask_means_vs_previous_analysis_max_abs": max(xdiff),
                               "as_shot_white": sc.white_as_shot_info}
        raw[shot] = (sc, per)
    # in-session neutral and exposure: the T1 frame at the T2-T4 exposure (R8051140), greys TN13..TN30
    ramp_ids = [f"TN{i:02d}" for i in range(13, 31)]
    ref_shot = "R8051140"
    sc_ref, per_ref = raw[ref_shot]
    wxy_if, info_if = sc_ref.white_in_frame([per_ref[i]["cam"] for i in ramp_ids])
    res["in_session_white"] = {k: info_if[k] for k in ("white_xy", "cct_K", "tint", "member_spread_rb_sd")}
    out_pages = {}
    for wname in ("in_session", "as_shot"):
        pages = {}
        for shot, (sc, per) in raw.items():
            page = caps[shot]["page"]
            wxy = wxy_if if wname == "in_session" else sc.white_as_shot
            # exposure: own grey ramp (T1 frames) or the T1 frame at the same exposure (T2-T4), Y 0.184 anchor
            ramp_sc, ramp_per = (sc, per) if page == "T1" else (sc_ref, per_ref)
            ramp_w = wxy if wname == "in_session" else ramp_sc.white_as_shot
            yd = np.array([fs.srgb_to_linear(np.array(nominal[i]["rgb8_srgb"], float) / 255)[1] for i in ramp_ids])
            ym = np.array([ramp_sc.xyz(ramp_per[i]["cam"], ramp_w)[0][1] for i in ramp_ids])
            k = 0.184 / float(np.interp(0.184, yd, ym))
            rows = []
            for i, st in per.items():
                xyz = sc.xyz(st["cam"], wxy)[0] * k
                lin = fs.srgb_to_linear(np.array(nominal[i]["rgb8_srgb"], float) / 255)
                lab_d, lab_n = fs.xyz_to_lab(xyz), fs.xyz_to_lab(lin @ fs.M709.T)
                grp = nominal[i].get("group", "")
                C = float(np.hypot(*lab_n[1:]))
                mC = re.search(r"_C(\d+)_H", i)
                c_nom = int(mC.group(1)) if mC else None
                rows.append({"id": i, "group": grp, "C_design": C, "C_nominal": c_nom, "lab_dng": lab_d.tolist(), "lab_design": lab_n.tolist(),
                             "de00": float(fs.delta_e00(lab_d, lab_n)),
                             "dL": float(lab_d[0] - lab_n[0]),
                             "de00_L_matched": float(fs.delta_e00(np.r_[lab_n[0], lab_d[1:]], lab_n)),
                             "raw_clip_frac": st["clip_frac"]})
            pages[shot] = {"page": page, "k": k, "rows": rows}
        summ = {}
        for shot, pg in pages.items():
            rows = [r for r in pg["rows"] if r["raw_clip_frac"] == 0 and r["lab_design"][0] > 8]
            chrom = [r for r in rows if r["C_design"] > 5]
            neut = [r for r in rows if r["C_design"] <= 5]
            summ[shot] = {"page": pg["page"], "chromatic_de00": fs.stats([r["de00"] for r in chrom]),
                          "chromatic_de00_L_matched": fs.stats([r["de00_L_matched"] for r in chrom]),
                          "neutral_de00": fs.stats([r["de00"] for r in neut]),
                          "chromatic_by_C": {c: fs.stats([r["de00_L_matched"] for r in chrom if r["C_nominal"] == c])
                                             for c in (12, 25, 40)}}
        out_pages[wname] = {"summary": summ, "pages": pages}
    res["dng_vs_nominal"] = out_pages
    res["seconds"] = round(time.time() - t0, 1)
    res["pass_mask_path"] = all(f["mask_means_vs_previous_analysis_max_abs"] < 1e-9 for f in res["frames"].values())
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--part", choices=("synthetic", "screen", "both"), default="both")
    args = ap.parse_args()
    LOCAL.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    out = {}
    guard = ds.CaptureGuard()
    if args.part in ("synthetic", "both"):
        out["synthetic"] = synthetic(args)
        a = out["synthetic"]
        print(f"== A synthetic ({a['seconds']} s): pass {a['pass']}; flagged {a['flagged_ids']}")
        for name, r in a["runs"].items():
            line = f"  {name}: ring targets dE00 vs design {fmt(r['target_de00_vs_design'])}; row = design {r['row_equals_design']}"
            if "row_bytes_differing" in r:
                line += f" ({r['row_bytes_differing']} bytes differ)"
            if "scene" in r:
                s = r["scene"]
                line += (f"; scene vs design {fmt(s['de00_scene_dng_vs_design'])}; 04a/04b {fmt(s['de00_between_04_frames'])}"
                         f"; whites {fmt(s['de00_ring_scene_between_whites'])}; map {[(m['shift'], m['offset'], m['after']) for m in s['map']]}")
            print(line)
        for k, v in a["wrong_as_shot_neutral"].items():
            print(f"  wrong-WB test {k}: scene vs design {fmt(v['de00_scene_vs_design'])} white CCT/tint "
                  f"{np.round(v['white_cct_tint'], 1).tolist()}")
    if args.part in ("screen", "both") and SCREEN.exists():
        out["screen"] = screen(args, guard)
        b = out["screen"]
        print(f"== B screen chart ({b['seconds']} s): mask path equals the previous analysis {b['pass_mask_path']}; "
              f"in-session white {b['in_session_white']}")
        for shot, f in b["frames"].items():
            print(f"  {shot} {f['page']}: map shift {np.round(f['map_shift_xy'], 3).tolist()} rms {f['map_residual_rms_px']:.3f} "
                  f"tiles {f['tiles_used']} offset {f['offset_applied']}; mask means diff {f['mask_means_vs_previous_analysis_max_abs']:.2e}; "
                  f"as-shot CCT {f['as_shot_white']['cct_K']:.0f} tint {f['as_shot_white']['tint']:.1f}")
        for wname, d in b["dng_vs_nominal"].items():
            for shot, s in d["summary"].items():
                print(f"  {wname} {shot} {s['page']}: chromatic dE00 {fmt(s['chromatic_de00'])}  L-matched "
                      f"{fmt(s['chromatic_de00_L_matched'])}  neutral {fmt(s['neutral_de00'])}  by C (L-matched) "
                      + " ".join(f"C{c}:{fmt(v)}" for c, v in s["chromatic_by_C"].items()))
    out["captures"] = guard.after()
    print(f"== captures read {len(out['captures']['files'])}, unchanged {out['captures']['all_unchanged']}, "
          f"with reference {out['captures']['n_with_reference']}, none mismatching {out['captures']['none_mismatch_reference']}")
    (LOCAL / "ring_dng_check.json").write_text(json.dumps(fs.sm.jsonable(out), indent=1, default=float) + "\n")
    print(f"wrote {LOCAL / 'ring_dng_check.json'}")
    if not out["captures"]["all_unchanged"]:
        raise SystemExit("a capture changed")


if __name__ == "__main__":
    main()
