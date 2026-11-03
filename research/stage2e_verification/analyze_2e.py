#!/usr/bin/env python3
"""Stage 2e colour-chart verification. Read-only on captures, firmware and packages.

Run with:  python3 -I research/stage2e_verification/analyze_2e.py

Reuses the stage 2d helpers (decode_raw, CFA means, Lab, CIEDE2000). Patch
centres come from a lattice fitted on the raw luminance, so the B&W frame and
a moved camera use the same detector. Everything derived from Ricoh tables or
the Fujifilm fit goes to local/ only. Overlays go to /tmp/gxr_stage2e_verif/.
"""
import hashlib
import importlib.util
import json
import math
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from scipy import ndimage  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAP = ROOT / "captures/a12-50/2026-10-19/stage2e-colorchecker"
CAP2D = ROOT / "captures/a12-50/2026-10-19/stage2d-colorchecker"
LOCAL = HERE / "local"
TMP = Path("/tmp/gxr_stage2e_verif")
STEMS = [f"R805{i}" for i in range(1152, 1161)]
EXPECTED = {
    "R8051152": "04 Std (A, spot D4, EC 0)", "R8051153": "04 Std", "R8051154": "01 Posi",
    "R8051155": "02 Nega", "R8051156": "05Chrome", "R8051157": "06ClsNeg",
    "R8051158": "07 PrbA", "R8051159": "08 PrbB", "R8051160": "04 Std (repeat)",
}

_spec = importlib.util.spec_from_file_location("s2d", ROOT / "research/stage2d_verification/analyze.py")
s2d = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s2d)
Tiff, decode_raw, shot_info, jpeg_tiff = s2d.Tiff, s2d.decode_raw, s2d.shot_info, s2d.jpeg_tiff
delta_e00, lab_from_srgb, lab_from_linear, srgb_to_linear = (
    s2d.delta_e00, s2d.lab_from_srgb, s2d.lab_from_linear, s2d.srgb_to_linear)
lch_of, wrap180, cfa_means, decode_coeff = s2d.lch_of, s2d.wrap180, s2d.cfa_means, s2d.decode_coeff

# Upright chart this time (DIOPTIX logo top-left reads normally): image row-major
# order is A1..A6 (dark skin .. bluish green), B1..B6, C1..C6, D1 white .. D6 black.
LABELS = [r + str(c + 1) for r in "ABCD" for c in range(6)]
NAMES = {
    "A1": "dark skin", "A2": "light skin", "A3": "blue sky", "A4": "foliage", "A5": "blue flower",
    "A6": "bluish green", "B1": "orange", "B2": "purplish blue", "B3": "moderate red", "B4": "purple",
    "B5": "yellow green", "B6": "orange yellow", "C1": "blue", "C2": "green", "C3": "red",
    "C4": "yellow", "C5": "magenta", "C6": "cyan", "D1": "white", "D2": "N8", "D3": "N6.5",
    "D4": "N5", "D5": "N3.5", "D6": "black",
}
GREYS = ["D1", "D2", "D3", "D4", "D5", "D6"]
CHROMATIC = [l for l in LABELS if l not in GREYS]
MID_GREYS = ("D2", "D3", "D4")
PROBE_SECTORS = {"07": (0, 4, 8, 12, 16, 20), "08": (2, 6, 10, 14, 18, 22)}
PROBE_ANGLES = (18, 12, 6, -6, -12, -18)
PROBE_SCALE = 1.30
EXIF_TAGS = {0x8822: "ExposureProgram", 0x9207: "MeteringMode", 0x9204: "ExposureBiasValue",
             0x9203: "BrightnessValue", 0x9202: "ApertureValue", 0xA402: "ExposureMode",
             0xA403: "WhiteBalance", 0x829A: "ExposureTime", 0x829D: "FNumber", 0x8827: "ISO",
             0x9003: "DateTimeOriginal"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def capture_hashes():
    return {p.name: sha256(p) for p in sorted(CAP.iterdir()) if p.suffix in (".DNG", ".JPG")}


# ----------------------------------------------------------------- metadata

def metadata(stem):
    out = {}
    for ext in ("JPG", "DNG"):
        path = CAP / f"{stem}.{ext}"
        tiff = jpeg_tiff(path) if ext == "JPG" else Tiff(path.read_bytes())
        root = tiff.ifd(tiff.root)
        exif = tiff.ifd(root[34665]["value"][0])
        note = exif[37500]
        entries = tiff.ifd(note["offset"] + 8, ">")
        record = entries[0x1001]["raw"]
        info = shot_info(tiff)
        out[ext] = {
            "exif": {name: exif[tag]["value"] for tag, name in EXIF_TAGS.items() if tag in exif},
            "selector": record[0x28],
            "raw13": info["color_raw_13"],
            "display": info["color_display"],
            "wb_mode_record_0x26": record[0x26],
            "record_hex": record.hex(),
        }
        if ext == "DNG":
            out["asn"] = root[50728]["value"]
    j, d = out["JPG"], out["DNG"]
    if (j["selector"], j["raw13"], j["exif"]) != (d["selector"], d["raw13"], d["exif"]):
        raise SystemExit(f"{stem}: JPEG and DNG metadata disagree")
    e = d["exif"]
    return {
        "program": e["ExposureProgram"][0], "exposure_mode": e["ExposureMode"][0],
        "metering": e["MeteringMode"][0], "bias_ev": e["ExposureBiasValue"][0],
        "bv": e["BrightnessValue"][0], "av_recorded": e["ApertureValue"][0],
        "t": e["ExposureTime"][0], "f": e["FNumber"][0], "iso": e["ISO"][0],
        "when": e["DateTimeOriginal"], "exif_white_balance": e["WhiteBalance"][0],
        "wb_mode_record_0x26": d["wb_mode_record_0x26"], "selector": d["selector"],
        "raw13": d["raw13"], "display": d["display"], "asn": out["asn"],
        "record_hex": d["record_hex"],
    }


# ----------------------------------------------------------------- geometry

def raw_luminance(crop, black, white, neutral, origin):
    """Half-resolution WB luminance u = (R + 2G + B)/4 from whole CFA quads."""
    ox, oy = origin
    c = (crop.astype(np.float64) - black) / (white - black)
    sy, sx = oy & 1, ox & 1  # first full quad that starts on R
    c = c[sy:, sx:]
    h, w = (c.shape[0] // 2) * 2, (c.shape[1] // 2) * 2
    c = c[:h, :w]
    n = np.asarray(neutral, dtype=np.float64)
    r = c[0::2, 0::2] / n[0]
    g = 0.5 * (c[0::2, 1::2] + c[1::2, 0::2]) / n[1]
    b = c[1::2, 1::2] / n[2]
    return 0.25 * r + 0.5 * g + 0.25 * b, (sx, sy)


def homography(src, dst):
    rows = []
    for (u, v), (x, y) in zip(src, dst):
        rows.append([u, v, 1, 0, 0, 0, -x * u, -x * v, -x])
        rows.append([0, 0, 0, u, v, 1, -y * u, -y * v, -y])
    _, _, vt = np.linalg.svd(np.asarray(rows, dtype=np.float64))
    return vt[-1].reshape(3, 3)


def apply_h(H, pts):
    q = np.c_[pts, np.ones(len(pts))] @ H.T
    return q[:, :2] / q[:, 2:3]


def detect_lattice(Y):
    """Flat bright components -> 6x4 lattice by homography with outlier rejection."""
    m = ndimage.uniform_filter(Y, 15)
    sd = np.sqrt(np.maximum(ndimage.uniform_filter(Y * Y, 15) - m * m, 0))
    mask = ndimage.binary_opening((m > 0.015) & (sd < 0.07 * m + 0.0008), iterations=3)
    lab, _ = ndimage.label(mask)
    comps = []
    for k, sl in enumerate(ndimage.find_objects(lab)):
        hgt, wid = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        area = int((lab[sl] == k + 1).sum())
        if 8000 <= area <= 90000 and 0.6 < hgt / wid < 1.6 and area / (hgt * wid) >= 0.7:
            cy, cx = ndimage.center_of_mass(lab == k + 1)
            comps.append((cx, cy, area, wid, hgt))
    ma = np.median([c[2] for c in comps])
    mw = np.median([c[3] for c in comps])
    mh = np.median([c[4] for c in comps])
    comps = [c for c in comps if c[2] > 0.85 * ma and c[3] > 0.92 * mw and c[4] > 0.92 * mh]
    pts = np.array([[c[0], c[1]] for c in comps])
    vx, vy = [], []
    for p in pts:
        for q in pts - p:
            if mw < q[0] < 1.8 * mw and abs(q[1]) < 0.4 * mh:
                vx.append(q)
            if mh < q[1] < 1.8 * mh and abs(q[0]) < 0.4 * mw:
                vy.append(q)
    basis = np.array([np.median(vx, axis=0), np.median(vy, axis=0)]).T
    ij = np.linalg.solve(basis, (pts - pts[0]).T).T
    r = np.rint(ij)
    ok = np.all(np.abs(ij - r) < 0.25, axis=1)
    best = None
    for i0 in range(int(r[:, 0].min()), int(r[:, 0].max()) - 4):
        for j0 in range(int(r[:, 1].min()), int(r[:, 1].max()) - 2):
            inw = ok & (r[:, 0] >= i0) & (r[:, 0] < i0 + 6) & (r[:, 1] >= j0) & (r[:, 1] < j0 + 4)
            if best is None or inw.sum() > best[0]:
                best = (int(inw.sum()), i0, j0, inw)
    _, i0, j0, inw = best
    idx = r[inw] - [i0, j0]
    P = pts[inw]
    keep = np.ones(len(idx), bool)
    while True:
        H = homography(idx[keep], P[keep])
        res = np.linalg.norm(apply_h(H, idx) - P, axis=1)
        worst = int(np.argmax(np.where(keep, res, -1)))
        if res[worst] <= 4.0 or keep.sum() <= 12:
            break
        keep[worst] = False
    grid = np.array([[i, j] for j in range(4) for i in range(6)], dtype=float)
    return apply_h(H, grid), {"components": len(comps), "lattice_inliers": int(keep.sum()),
                              "max_residual_halfpx": float(res[keep].max())}


# ----------------------------------------------------------------- sampling

def ycbcr(rgb255):
    r, g, b = rgb255
    return np.array([0.299 * r + 0.587 * g + 0.114 * b,
                     -0.168736 * r - 0.331264 * g + 0.5 * b,
                     0.5 * r - 0.418688 * g - 0.081312 * b])


def sample(stem):
    jpeg = np.asarray(Image.open(CAP / f"{stem}.JPG").convert("RGB")).astype(np.float64)
    tiff = Tiff((CAP / f"{stem}.DNG").read_bytes())
    crop, black, white, neutral, stats = decode_raw(tiff)
    if crop.shape[:2] != jpeg.shape[:2]:
        raise SystemExit(f"{stem}: crop {crop.shape} vs jpeg {jpeg.shape}")
    ox, oy = stats["crop_origin_xy"]
    Y, (sx, sy) = raw_luminance(crop, black, white, neutral, (ox, oy))
    half_centres, geo = detect_lattice(Y)
    centres = half_centres * 2 + np.array([sx + 0.5, sy + 0.5])
    grid = centres.reshape(4, 6, 2)
    pitch = min(float(np.median(np.diff(grid[:, :, 0], axis=1))),
                float(np.median(np.diff(grid[:, :, 1], axis=0))))
    half = int(round(0.16 * pitch))
    asn = np.asarray(neutral, dtype=np.float64)
    patches = []
    for i, (cx, cy) in enumerate(centres):
        x0, x1 = int(round(cx - half)), int(round(cx + half))
        y0, y1 = int(round(cy - half)), int(round(cy + half))
        dn = np.array(cfa_means(crop, y0, y1, x0, x1, oy, ox))
        cam = (dn - black) / (white - black)
        block = jpeg[y0:y1, x0:x1]
        mean = block.mean(axis=(0, 1))
        lab = lab_from_srgb(mean / 255.0)
        L, C, h = lch_of(lab)
        patches.append({
            "label": LABELS[i], "center_xy": [float(cx), float(cy)], "roi": [x0, y0, x1, y1],
            "raw_dn": dn.tolist(), "camera_rgb_wb": (cam / asn).tolist(),
            "u": float((cam / asn) @ np.array([0.25, 0.5, 0.25])),
            "jpeg_rgb": mean.tolist(), "jpeg_std": block.reshape(-1, 3).std(axis=0).tolist(),
            "jpeg_y709": float(np.dot(mean, [0.2126, 0.7152, 0.0722])),
            "ycc": ycbcr(mean).tolist(),
            "lab": lab.tolist(), "L": float(L), "C": float(C), "h": float(h),
        })
    geo.update({"pitch_px": pitch, "roi_half_px": half, "A1_xy": centres[0].tolist(),
                "D6_xy": centres[23].tolist(), "crop_wh": stats["crop_wh"]})
    return patches, geo, {"black": black, "white": white, "asn": asn.tolist(), "Y": Y,
                          "quad_origin": (sx, sy), "jpeg": jpeg}


def orientation_checks(patches, mono):
    by = {p["label"]: p for p in patches}
    u = [by[g]["u"] for g in GREYS]
    raw_neutral = max(abs(by[g]["camera_rgb_wb"][0] / by[g]["camera_rgb_wb"][1] - 1) for g in GREYS[:5])
    out = {"raw_grey_u_descending": all(u[i] > u[i + 1] for i in range(5)),
           "raw_grey_rb_over_g_max_dev": raw_neutral}
    if not out["raw_grey_u_descending"]:
        raise SystemExit(f"bottom row is not white..black in raw: {u}")
    if mono:
        out["jpeg_max_chroma"] = max(p["C"] for p in patches)
        return out
    b_row = [by[f"C{k}"]["lab"][2] for k in range(1, 7)]
    out["third_row_b_max_is_C4_yellow"] = int(np.argmax(b_row)) == 3
    out["third_row_b_min_is_C1_blue"] = int(np.argmin(b_row)) == 0
    a1, a2 = by["A1"], by["A2"]
    out["A1_is_dark_skin"] = a1["lab"][1] > 5 and a1["lab"][2] > 3 and a1["L"] + 5 < a2["L"]
    out["grey_row_max_C"] = max(by[g]["C"] for g in GREYS)
    if not all(v for k, v in out.items() if k.startswith(("third", "A1"))):
        raise SystemExit(f"orientation check failed: {out}")
    return out


def draw_overlay(stem, jpeg, patches, path):
    im = Image.fromarray(jpeg.astype(np.uint8))
    d = ImageDraw.Draw(im)
    for p in patches:
        d.rectangle(p["roi"], outline=(255, 40, 40), width=6)
        d.text((p["roi"][0] + 6, p["roi"][1] + 6), p["label"], fill=(255, 255, 0))
    w, h = im.size
    d.ellipse([w / 2 - 12, h / 2 - 12, w / 2 + 12, h / 2 + 12], outline=(0, 255, 0), width=5)
    im.resize((1072, 712), Image.Resampling.BOX).save(path, quality=85)


# ----------------------------------------------------------------- tables

def parse_deep_tables():
    """The bytes actually linked into stage 2e (gitignored generator output)."""
    text = (ROOT / "firmware/stage2e/deep_tables.c").read_text()

    def grab(name):
        at = text.index(f"static const uint8_t {name}[]")
        body = text[at:text.index("};", at)].split("{", 1)[1]
        return bytes(int(x, 16) for x in body.replace("\n", " ").split(",") if x.strip())

    def curve(a, b):
        nodes = struct.unpack(">" + "H" * (len(a) // 2), a)
        return np.array([0, *nodes, 4095], dtype=np.float64), np.array(list(b), dtype=np.float64)

    raw = {name: grab(name) for name in ("table_0_0", "table_0_1", "table_0_2", "table_1_0", "table_1_1",
                                         "table_2_1", "table_3_0", "table_3_1", "table_4_0", "table_4_1",
                                         "table_5_1", "table_6_2", "table_7_2")}
    curves = {
        "stock_row5": curve(raw["table_0_0"], raw["table_0_1"]),
        "posi": curve(raw["table_1_0"], raw["table_1_1"]),
        "nega": curve(raw["table_0_0"], raw["table_2_1"]),
        "hc_row20": curve(raw["table_3_0"], raw["table_3_1"]),
        "chrome": curve(raw["table_4_0"], raw["table_4_1"]),
        "clsneg": curve(raw["table_0_0"], raw["table_5_1"]),
    }
    colour = {"stock": raw["table_0_2"], "07": raw["table_6_2"], "08": raw["table_7_2"]}
    # Cross-checks against independent sources.
    j3 = (ROOT / "artifacts/firmware/gxr-1.51/jlaunch3").read_bytes()
    off = lambda vma: vma - 0x200F2000 + 0xA7200  # noqa: E731
    checks = {
        "stock_A_eq_official": j3[off(0x2012F504):off(0x2012F504) + 62] == raw["table_0_0"],
        "stock_B_eq_official": j3[off(0x2012FFFC):off(0x2012FFFC) + 33] == raw["table_0_1"],
        "stock_colour_eq_official": j3[off(0x2012C5D4):off(0x2012C5D4) + 96] == raw["table_0_2"],
    }
    fit = json.loads((ROOT / "research/fuji_phase2/local/fit.json").read_text())["fits"]
    for key, name, a, b in (("chrome", "classic_chrome", "table_4_0", "table_4_1"),
                            ("clsneg", "classic_neg", "table_0_0", "table_5_1")):
        ch = fit[name]["chosen"]
        checks[f"{key}_eq_fit_json"] = (struct.pack(">31H", *ch["input31_u16"]) == raw[a]
                                         and bytes(ch["output33_u8"]) == raw[b])
    probes = json.loads((ROOT / "research/stage2d_verification/measurements.json").read_text())["probes"]
    for key, name in (("07", "probe_A"), ("08", "probe_B")):
        p = next(x for x in probes if x["name"] == name)
        checks[f"probe_{key}_eq_measurements"] = bytes.fromhex("".join(p["words_hex"])) == colour[key]
        diff = [s for s in range(24) if colour[key][4 * s:4 * s + 4] != colour["stock"][4 * s:4 * s + 4]]
        checks[f"probe_{key}_changed_sectors"] = diff
    coeffs = {k: [decode_coeff(v[i:i + 4]) for i in range(0, 96, 4)] for k, v in colour.items()}
    return curves, coeffs, checks, {k: v.hex() for k, v in raw.items()}


def hue_modifier():
    data = json.loads((ROOT / "research/color_calibration/firmware_parameters.json").read_text())
    return np.array(data["normal_sector_hue_d0"]), np.array(data["normal_sector_hue_d1"])


def apply_curve(curve, code):
    xs, ys = curve
    return float(np.interp(np.clip(code, 0, 4095), xs, ys))


def inverse_curve(curve, y):
    xs, ys = curve
    return float(np.interp(y, ys, xs))


# ----------------------------------------------------------------- colour helpers

def wb_align(patches, ref_white):
    """Von Kries on linear sRGB so the D2-D4 mean has the reference chromaticity.

    Chromaticity only, so the tone curve's lightness stays in the data.
    """
    src = np.mean([srgb_to_linear(np.array(p["jpeg_rgb"]) / 255) for p in patches if p["label"] in MID_GREYS], axis=0)
    gain = (ref_white / ref_white.mean()) / (src / src.mean())
    out = {}
    for p in patches:
        lin = srgb_to_linear(np.array(p["jpeg_rgb"]) / 255) * gain
        lab = lab_from_linear(lin)
        enc = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.clip(lin, 0, None) ** (1 / 2.4) - 0.055) * 255
        out[p["label"]] = {"lab": lab, "ycc": ycbcr(enc)}
    return out, gain


def lch(lab):
    L, C, h = lch_of(lab)
    return float(L), float(C), float(h)


def polar(v):
    return float(np.hypot(v[0], v[1])), float(math.degrees(math.atan2(v[1], v[0])) % 360)


def change(base, new):
    """Lab and CbCr change of one patch: dL, chroma ratio, hue delta (deg)."""
    Lb, Cb, hb = lch(base["lab"])
    Ln, Cn, hn = lch(new["lab"])
    mb, ab = polar(base["ycc"][1:])
    mn, an = polar(new["ycc"][1:])
    return {"dL": Ln - Lb, "C_base": Cb, "C_ratio": Cn / Cb if Cb > 0 else None,
            "dh_lab": float(wrap180(hn - hb)), "h_base": hb,
            "cc_base": mb, "cc_ratio": mn / mb if mb > 0 else None,
            "dh_cbcr": float(wrap180(an - ab)), "hcc_base": ab,
            "dE00": float(delta_e00(base["lab"], new["lab"]))}


def mean_state(states):
    return {"lab": np.mean([s["lab"] for s in states], axis=0), "ycc": np.mean([s["ycc"] for s in states], axis=0)}


def stats(xs):
    xs = np.asarray(xs, dtype=np.float64)
    return {"n": int(len(xs)), "median": float(np.median(xs)), "median_abs": float(np.median(np.abs(xs))),
            "mean_abs": float(np.mean(np.abs(xs))), "max_abs": float(np.max(np.abs(xs)))}


# ----------------------------------------------------------------- frame identification

TONE_ROW = {"posi": "01 Posi", "nega": "02 Nega", "hc_row20": "03 HC BW", "chrome": "05Chrome",
            "clsneg": "06ClsNeg", "stock_row5": "04 Std / 07 PrbA / 08 PrbB"}
OG = set(s2d.GROUP_LABELS["orange"] + s2d.GROUP_LABELS["green"])
BRM = set(s2d.GROUP_LABELS["blue"] + s2d.GROUP_LABELS["red"] + s2d.GROUP_LABELS["magenta"])


def measure_all():
    frames = {}
    for stem in STEMS:
        meta = metadata(stem)
        patches, geo, extra = sample(stem)
        orient = orientation_checks(patches, mono=meta["selector"] == 3)
        draw_overlay(stem, extra["jpeg"], patches, TMP / f"overlay_{stem}.jpg")
        frames[stem] = {"meta": meta, "geometry": geo, "orientation": orient, "patches": patches,
                        "_Y": extra["Y"], "_quad": extra["quad_origin"]}
    # Raw chromaticity of every labelled patch must agree across frames (same scene).
    ref = {p["label"]: np.array(p["camera_rgb_wb"]) for p in frames[STEMS[-1]]["patches"]}
    for fr in frames.values():
        dev = []
        for p in fr["patches"]:
            x, y = np.array(p["camera_rgb_wb"]), ref[p["label"]]
            dev.append(float(np.max(np.abs(x / x[1] - y / y[1]) / np.maximum(y / y[1], 0.05))))
        fr["orientation"]["raw_chromaticity_max_rel_dev_vs_1160"] = max(dev)
    return frames


def by_label(fr):
    return {p["label"]: p for p in fr["patches"]}


def tone_errors(fr, curve):
    by = by_label(fr)
    return [apply_curve(curve, by[g]["u"] * 4095) - by[g]["jpeg_y709"] for g in GREYS]


def identify_tones(frames, curves):
    out = {}
    for stem, fr in frames.items():
        per = {name: stats(tone_errors(fr, cv)) for name, cv in curves.items()}
        ranked = sorted(per, key=lambda k: per[k]["median_abs"])
        out[stem] = {"best": ranked[0], "best_row": TONE_ROW[ranked[0]], "second": ranked[1],
                     "best_median_abs": per[ranked[0]]["median_abs"],
                     "second_median_abs": per[ranked[1]]["median_abs"], "per_curve": per}
    return out


# ----------------------------------------------------------------- colour states

def mid_white(fr):
    return np.mean([srgb_to_linear(np.array(p["jpeg_rgb"]) / 255) for p in fr["patches"] if p["label"] in MID_GREYS], axis=0)


def clipped_labels(frames, stems):
    out = set()
    for stem in stems:
        for p in frames[stem]["patches"]:
            if min(p["jpeg_rgb"]) < 8 or max(p["jpeg_rgb"]) > 250:
                out.add(p["label"])
    return sorted(l for l in out if l not in GREYS)


def sector_levels(display):
    """Hue-slider level index (display - 1) for each sector; unmasked sectors use the neutral level."""
    level = np.full(24, 4)
    for group, sectors in s2d.MASKS.items():
        for s in sectors:
            level[s] = display[f"{group}_hue"] - 1
    return level


def design_ratios(coeffs, display, modifier=True):
    """Complex multiplier ratio probe/stock per probed sector, in the (Cb, Cr) orientation.

    Word [A, B, -B, A] acts as x' = (A x + B y)/32, y' = (-B x + A y)/32, i.e. multiplier A - iB.
    The five-colour hue modifier adds d0/d1 to the copied row (stage 2d reading); saturation 5 is k=100.
    """
    d0, d1 = hue_modifier()
    level = sector_levels(display)

    def mult(rows):
        out = []
        for s, (A, B) in enumerate(rows):
            if modifier:
                A, B = A + d0[level[s], s], B + d1[level[s], s]
            out.append(complex(A, -B) / 32)
        return np.array(out)

    ms, ma, mb = mult(coeffs["stock"]), mult(coeffs["07"]), mult(coeffs["08"])
    Z = {}
    for s in range(24):
        if s in PROBE_SECTORS["07"]:
            Z[s] = ma[s] / ms[s]
        elif s in PROBE_SECTORS["08"]:
            Z[s] = mb[s] / ms[s]
    return Z, ms


def decompose(dz, candidates, Z):
    """Best single probed sector for an observed complex change dz = z - 1."""
    fits = []
    for s in candidates:
        u = Z[s] - 1
        w = (dz * u.conjugate()).real / abs(u) ** 2
        fits.append((abs(dz - w * u), s, w))
    fits.sort()
    r, s, w = fits[0]
    return {"sector": s, "w": float(w), "resid": float(r)}


# ----------------------------------------------------------------- sections

def drift_section(frames, a_stem, b_stem):
    A, B = by_label(frames[a_stem]), by_label(frames[b_stem])
    ref_white = mid_white(frames[b_stem])
    SA, gA = wb_align(frames[a_stem]["patches"], ref_white)
    SB, _ = wb_align(frames[b_stem]["patches"], ref_white)
    greys = {g: {"jpeg_y_diff": B[g]["jpeg_y709"] - A[g]["jpeg_y709"],
                 "jpeg_rgb_diff": (np.array(B[g]["jpeg_rgb"]) - np.array(A[g]["jpeg_rgb"])).tolist(),
                 "u_ratio": B[g]["u"] / A[g]["u"]} for g in GREYS}
    de_raw = {l: float(delta_e00(A[l]["lab"], B[l]["lab"])) for l in LABELS}
    de_wb = {l: float(delta_e00(SA[l]["lab"], SB[l]["lab"])) for l in LABELS}
    ch = {l: change(SA[l], SB[l]) for l in CHROMATIC}
    u_ratio = float(np.median([greys[g]["u_ratio"] for g in GREYS]))
    return {
        "pair": [a_stem, b_stem], "greys": greys,
        "u_ratio_median": u_ratio, "u_ratio_ev": math.log2(u_ratio),
        "asn": [frames[a_stem]["meta"]["asn"], frames[b_stem]["meta"]["asn"]],
        "wb_gain_a_to_b": gA.tolist(),
        "de00_raw": {"per_patch": de_raw, **stats(list(de_raw.values()))},
        "de00_wb": {"per_patch": de_wb, **stats(list(de_wb.values()))},
        "chromatic_dh_cbcr": stats([c["dh_cbcr"] for c in ch.values()]),
        "chromatic_cc_ratio": stats([c["cc_ratio"] - 1 for c in ch.values()]),
        "chromatic_dh_lab": stats([c["dh_lab"] for c in ch.values()]),
        "chromatic_C_ratio": stats([c["C_ratio"] - 1 for c in ch.values()]),
        "chromatic_dL": stats([c["dL"] for c in ch.values()]),
        "per_patch_change": ch,
    }


def metering_section(frames, curves):
    AV = 2 * math.log2(2.5)
    TV = math.log2(80)
    SV = math.log2(500 / 3.125)
    u_assumed = 320 / 4095
    rows = []
    for stem, fr in frames.items():
        m = fr["meta"]
        Y = fr["_Y"]
        sx, sy = fr["_quad"]
        cw, ch = fr["geometry"]["crop_wh"]
        yy, xx = np.mgrid[0:Y.shape[0], 0:Y.shape[1]]
        r = np.hypot(2 * yy + sy + 0.5 - ch / 2, 2 * xx + sx + 0.5 - cw / 2)
        disc = {R: float(Y[r <= R].mean()) for R in (100, 200, 300, 400, 600)}
        rows.append({"stem": stem, "bv": m["bv"], "u_D4": by_label(fr)["D4"]["u"], "disc": disc,
                     "frame_mean_u": float(Y.mean()), "exposure_minus_meter_ev": AV + TV - SV - m["bv"]})
    hyp = {}
    for key in ["D4", 100, 200, 300, 400, 600, "frame"]:
        xs = []
        for r in rows:
            u = r["u_D4"] if key == "D4" else (r["frame_mean_u"] if key == "frame" else r["disc"][key])
            xs.append(r["bv"] - math.log2(u))
        xs = np.array(xs)
        um = 2 ** (AV + TV - SV - xs.mean())
        hyp[str(key)] = {"const": float(xs.mean()), "sd_ev": float(xs.std(ddof=1)),
                         "u_m": float(um), "ev_vs_assumed": math.log2(um / u_assumed)}
    f1152 = by_label(frames["R8051152"])["D4"]
    return {
        "apex": {"AV": AV, "TV": TV, "SV": SV, "AV_plus_TV_minus_SV": AV + TV - SV},
        "frames": rows, "bv_hypotheses": hyp,
        "R8051152": {"program": frames["R8051152"]["meta"]["program"],
                     "exposure_mode": frames["R8051152"]["meta"]["exposure_mode"],
                     "metering": frames["R8051152"]["meta"]["metering"],
                     "bias_ev": frames["R8051152"]["meta"]["bias_ev"],
                     "t": frames["R8051152"]["meta"]["t"], "bv": frames["R8051152"]["meta"]["bv"],
                     "u_D4": f1152["u"], "ev_vs_assumed": math.log2(f1152["u"] / u_assumed),
                     "jpeg_y_D4": f1152["jpeg_y709"], "jpeg_rgb_D4": f1152["jpeg_rgb"],
                     "row5_pred_D4": apply_curve(curves["stock_row5"], f1152["u"] * 4095)},
        "u_assumed": u_assumed,
        "row5_at_u_assumed": apply_curve(curves["stock_row5"], 320),
        "row5_inverse_118": inverse_curve(curves["stock_row5"], 118),
        "D4_published_Y_vs_018_ev": math.log2(0.191 / 0.18),
    }


def tone_section(frames, curves, ident):
    out = {}
    for stem, fr in frames.items():
        best = ident[stem]["best"]
        errs = tone_errors(fr, curves[best])
        stock = tone_errors(fr, curves["stock_row5"])
        by = by_label(fr)
        # Same curve applied to each WB raw channel, then Rec.709 luma (colour modes only).
        per_channel = [float(np.dot([apply_curve(curves[best], v * 4095) for v in by[g]["camera_rgb_wb"]],
                                    [0.2126, 0.7152, 0.0722])) - by[g]["jpeg_y709"] for g in GREYS]
        out[stem] = {"curve": best, "row": TONE_ROW[best], "per_channel_err": stats(per_channel),
                     "per_grey": {g: {"u": by[g]["u"], "jpeg_y": by[g]["jpeg_y709"],
                                      "pred": apply_curve(curves[best], by[g]["u"] * 4095),
                                      "stock_pred": apply_curve(curves["stock_row5"], by[g]["u"] * 4095)}
                                  for g in GREYS},
                     "err": stats(errs), "stock_err": stats(stock)}
    return out


def tone_colour_models(rgb, u, base, target, curve_t, curve_b):
    """Predict target chromatic patches from base under three tone/chroma hypotheses."""
    ref_w = np.mean([srgb_to_linear(rgb[base][g] / 255) for g in MID_GREYS], axis=0)

    def align(stem, l):
        w = np.mean([srgb_to_linear(rgb[stem][g] / 255) for g in MID_GREYS], axis=0)
        lin = srgb_to_linear(rgb[stem][l] / 255) * (ref_w / ref_w.mean()) / (w / w.mean())
        return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.clip(lin, 0, None) ** (1 / 2.4) - 0.055) * 255

    def lab_ycc(Y, cb, cr):
        r, g, b = Y + 1.402 * cr, Y - 0.344136 * cb - 0.714136 * cr, Y + 1.772 * cb
        return lab_from_srgb(np.clip(np.array([r, g, b]), 0, 255) / 255)

    rows = {}
    for l in CHROMATIC:
        rb, rt = align(base, l), align(target, l)
        yb, yt = ycbcr(rb), ycbcr(rt)
        lab_t = lab_from_srgb(np.clip(rt, 0, 255) / 255)
        k = yt[0] / yb[0]
        lin_codes = np.interp(np.clip(rb, 0, 255), curve_b[1], curve_b[0]) * (u[target][l] / u[base][l])
        pred = {"H1_cbcr_same": lab_ycc(yt[0], yb[1], yb[2]),
                "H2_cbcr_scaled_by_luma": lab_ycc(yt[0], yb[1] * k, yb[2] * k),
                "H3_curve_per_channel": lab_from_srgb(np.clip(np.interp(np.clip(lin_codes, 0, 4095), curve_t[0], curve_t[1]), 0, 255) / 255)}
        h3 = pred["H3_curve_per_channel"]
        enc_h3 = np.interp(np.clip(lin_codes, 0, 4095), curve_t[0], curve_t[1])
        z_obs, z_h3, z_b = complex(*yt[1:]), complex(*ycbcr(enc_h3)[1:]), complex(*yb[1:])
        rows[l] = {
            "de00": {k2: float(delta_e00(lab_t, v)) for k2, v in pred.items()},
            "obs_cc_ratio": abs(z_obs) / abs(z_b), "obs_dh_cbcr": math.degrees(cmath_phase(z_obs / z_b)),
            "h3_resid_dh_cbcr": math.degrees(cmath_phase(z_obs / z_h3)),
            "h3_resid_cc_ratio": abs(z_obs) / abs(z_h3),
            "h3_resid_dh_lab": float(wrap180(lch(lab_t)[2] - lch(h3)[2])),
            "h3_resid_dL": lch(lab_t)[0] - lch(h3)[0],
        }
    summary = {k2: stats([r["de00"][k2] for r in rows.values()]) for k2 in rows[CHROMATIC[0]]["de00"]}
    groups = {}
    for name, labs in (("OG", OG), ("BRM", BRM)):
        sel = [rows[l] for l in CHROMATIC if l in labs]
        groups[name] = {"h3_resid_dh_cbcr_median": float(np.median([r["h3_resid_dh_cbcr"] for r in sel])),
                        "h3_resid_dh_lab_median": float(np.median([r["h3_resid_dh_lab"] for r in sel])),
                        "h3_resid_cc_ratio_median": float(np.median([r["h3_resid_cc_ratio"] for r in sel])),
                        "obs_dh_cbcr_median": float(np.median([r["obs_dh_cbcr"] for r in sel])),
                        "h3_de00_median": float(np.median([r["de00"]["H3_curve_per_channel"] for r in sel])),
                        "n": len(sel)}
    groups["BRM_minus_OG_h3_resid_dh_cbcr"] = groups["BRM"]["h3_resid_dh_cbcr_median"] - groups["OG"]["h3_resid_dh_cbcr_median"]
    groups["BRM_minus_OG_h3_resid_dh_lab"] = groups["BRM"]["h3_resid_dh_lab_median"] - groups["OG"]["h3_resid_dh_lab_median"]
    return {"per_patch": rows, "de00_summary": summary, "groups": groups,
            "obs_cc_ratio": stats([r["obs_cc_ratio"] - 1 for r in rows.values()])}


def cmath_phase(z):
    return math.atan2(z.imag, z.real)


def colour_section(frames, curves, ident, base="R8051160"):
    rgb = {s: {p["label"]: np.array(p["jpeg_rgb"]) for p in f["patches"]} for s, f in frames.items()}
    u = {s: {p["label"]: p["u"] for p in f["patches"]} for s, f in frames.items()}
    out = {"2e": {}, "2d": {}}
    for stem in STEMS:
        cv = ident[stem]["best"]
        if cv in ("posi", "nega", "chrome", "clsneg") or stem == "R8051152":
            out["2e"][stem] = {"curve": cv, **tone_colour_models(rgb, u, base, stem, curves[cv], curves["stock_row5"])}
    m2d = json.loads((ROOT / "research/stage2d_verification/measurements.json").read_text())
    rgb2 = {k: {p["label"]: np.array(p["jpeg_srgb"]) * 255 for p in v["patches"]} for k, v in m2d["frames"].items()}
    u2 = {k: {p["label"]: p["u"] for p in v["patches"]} for k, v in m2d["frames"].items()}
    for key, cv in (("01_posi", "posi"), ("02_nega", "nega")):
        out["2d"][key] = {"curve": cv, **tone_colour_models(rgb2, u2, "04_std", key, curves[cv], curves["stock_row5"])}
    out["raw13_identical_all_2e"] = len({tuple(f["meta"]["raw13"]) for f in frames.values()}) == 1
    out["record_bytes_differing_between_2e_frames"] = sorted({
        hex(i) for f in frames.values() for i, (x, y) in enumerate(zip(bytes.fromhex(f["meta"]["record_hex"]),
                                                                       bytes.fromhex(frames["R8051160"]["meta"]["record_hex"])))
        if x != y})
    return out


# ----------------------------------------------------------------- sector probes

def raw_hue_planes(fr):
    out = {}
    for p in fr["patches"]:
        c = np.array(p["camera_rgb_wb"])
        planes = {}
        for gname, v in (("lin", c), ("gam", np.clip(c, 1e-6, None) ** (1 / 2.2))):
            r, g, b = v
            y4 = (r + 2 * g + b) / 4
            planes[f"raw_{gname}_BG_RG"] = complex(b - g, r - g)
            planes[f"raw_{gname}_CbCr"] = complex(-0.168736 * r - 0.331264 * g + 0.5 * b, 0.5 * r - 0.418688 * g - 0.081312 * b)
            planes[f"raw_{gname}_BY4_RY4"] = complex(b - y4, r - y4)
        out[p["label"]] = {k: math.degrees(cmath_phase(v)) % 360 for k, v in planes.items()}
    return out


def interp_weights(h, H0, d, model):
    t = ((h - H0) * d / 15.0) % 24
    s = int(math.floor(t)) % 24
    f = t - math.floor(t)
    w = np.zeros(24)
    if model == "hard":
        w[s] = 1.0
    else:
        w[s] += 1 - f
        w[(s + 1) % 24] += f
    return w


def equal_spacing_fit(obs, hue_key, Z, model):
    """Best chi2 for nodes equally spaced (15 deg) in the given hue measure, any origin/direction/gain."""
    best = None
    for d in (1, -1):
        for kw in np.arange(0.3, 1.21, 0.05):
            for H0 in np.arange(0, 360, 0.5):
                chi = 0.0
                for o in obs:
                    w = interp_weights(o[hue_key], H0, d, model) * kw
                    pa = sum(w[s] * (Z[s] - 1) for s in PROBE_SECTORS["07"])
                    pb = sum(w[s] * (Z[s] - 1) for s in PROBE_SECTORS["08"])
                    chi += (abs(o["dzA"] - pa) ** 2 + abs(o["dzB"] - pb) ** 2) / o["sig"] ** 2
                if best is None or chi < best["chi2"]:
                    best = {"chi2": float(chi), "H0": float(H0), "direction": d, "kw": float(kw)}
    best["n_obs"] = 4 * len(obs)
    return best


def probe_section(frames, coeffs, ident, base_mode):
    row5 = [s for s in STEMS if ident[s]["best"] == "stock_row5"]
    if base_mode == "1160":
        ref_white = mid_white(frames["R8051160"])
    else:
        ref_white = 0.5 * (mid_white(frames["R8051152"]) + mid_white(frames["R8051160"]))
    states = {s: wb_align(frames[s]["patches"], ref_white)[0] for s in row5}
    if base_mode == "1160":
        base = {l: states["R8051160"][l] for l in LABELS}
    else:
        base = {l: mean_state([states["R8051152"][l], states["R8051160"][l]]) for l in LABELS}
    display = frames["R8051160"]["meta"]["display"]
    Z, _ = design_ratios(coeffs, display)
    Z_nomod, _ = design_ratios(coeffs, display, modifier=False)
    cc = {s: {l: complex(*states[s][l]["ycc"][1:]) for l in CHROMATIC} for s in row5}
    cbase = {l: complex(*base[l]["ycc"][1:]) for l in CHROMATIC}
    sig = {l: max(0.008, abs(cc["R8051160"][l] / cc["R8051152"][l] - 1) / math.sqrt(2)) for l in CHROMATIC}
    clipped = clipped_labels(frames, row5)
    # Frames with many significant chromatic changes are the probes. The two probe rows use the
    # same six design angles, so the change direction cannot tell 07 from 08. The identity is the
    # assignment under which sector number runs monotonically with hue (sectors are contiguous).
    signature = {}
    for s in row5:
        if base_mode == "1160" and s == "R8051160":
            continue
        dzs = {l: cc[s][l] / cbase[l] - 1 for l in CHROMATIC}
        signature[s] = {"n_patches_over_6sigma": sum(1 for l in CHROMATIC if abs(dzs[l]) / sig[l] >= 6),
                        "max_dz": max(abs(v) for v in dzs.values())}
    cands = [s for s in row5 if s in signature and signature[s]["n_patches_over_6sigma"] >= 3]
    if len(cands) != 2:
        raise SystemExit(f"expected two probe frames, got {cands}: {signature}")

    def seq_inversions(pA, pB):
        items = []
        for l in CHROMATIC:
            for key, stem in (("07", pA), ("08", pB)):
                dz = cc[stem][l] / cbase[l] - 1
                if abs(dz) / sig[l] >= 3:
                    items.append((math.degrees(cmath_phase(cbase[l])) % 360, decompose(dz, PROBE_SECTORS[key], Z)["sector"]))
        items.sort()
        best = None
        for k in range(len(items)):
            sec = [x[1] for x in items[k:] + items[:k]]
            inv = sum(1 for i in range(len(sec) - 1) if sec[i + 1] < sec[i])
            best = inv if best is None else min(best, inv)
        return best

    inv_as_shot = seq_inversions(cands[0], cands[1])
    inv_swapped = seq_inversions(cands[1], cands[0])
    probeA, probeB = (cands[0], cands[1]) if inv_as_shot <= inv_swapped else (cands[1], cands[0])
    identity = {"candidates": cands, "inversions_if_first_is_07": inv_as_shot, "inversions_if_first_is_08": inv_swapped}
    rows = {}
    Lbase = {l: lch(base[l]["lab"]) for l in CHROMATIC}
    for l in CHROMATIC:
        rec = {"name": NAMES[l], "clipped": l in clipped, "sig": sig[l],
               "h_cbcr": math.degrees(cmath_phase(cbase[l])) % 360, "cc_base": abs(cbase[l]),
               "h_lab": Lbase[l][2], "C_lab": Lbase[l][1], "L": Lbase[l][0]}
        for key, stem in (("07", probeA), ("08", probeB)):
            z = cc[stem][l] / cbase[l]
            dz = z - 1
            dec = decompose(dz, PROBE_SECTORS[key], Z)
            chg = change(base[l], states[stem][l])
            s = dec["sector"]
            angZ = math.degrees(cmath_phase(Z[s]))
            rec[key] = {**dec, "dz_abs": abs(dz), "n_sigma": abs(dz) / sig[l],
                        "dir_deg": math.degrees(cmath_phase(dz)), "design_dir_deg": math.degrees(cmath_phase(Z[s] - 1)),
                        "dh_cbcr": math.degrees(cmath_phase(z)), "cc_ratio": abs(z),
                        "design_angle_deg": angZ, "design_scale": abs(Z[s]),
                        "angle_gain_cbcr": math.degrees(cmath_phase(z)) / angZ,
                        "logscale_gain_cbcr": math.log(abs(z)) / math.log(abs(Z[s])),
                        "dh_lab": chg["dh_lab"], "C_ratio_lab": chg["C_ratio"], "dL": chg["dL"], "dE00": chg["dE00"],
                        "lab_angle_per_coeff_deg": chg["dh_lab"] / angZ,
                        "lab_over_cbcr_angle": (chg["dh_lab"] / math.degrees(cmath_phase(z))
                                                if abs(math.degrees(cmath_phase(z))) > 1.5 else None)}
        rows[l] = rec
    # Primary assignment: the probe whose change is larger and over 3 sigma.
    assign = []
    for l, rec in rows.items():
        for key in ("07", "08"):
            ns = rec[key]["n_sigma"]
            # A probe effect has positive weight and points along the design direction.
            if ns >= 2 and rec[key]["w"] >= 0.05 and rec[key]["resid"] <= 0.6 * rec[key]["dz_abs"]:
                assign.append({"label": l, "probe": key, "sector": rec[key]["sector"], "w": rec[key]["w"],
                               "n_sigma": ns, "strength": "strong" if ns >= 8 else ("moderate" if ns >= 3 else "weak"),
                               "h_cbcr": rec["h_cbcr"], "h_lab": rec["h_lab"], "clipped": rec["clipped"]})
    assign.sort(key=lambda a: a["h_cbcr"])
    # Cyclic monotonicity of sector number versus hue.
    def inversions(key):
        seq = sorted([a for a in assign if a["n_sigma"] >= 3], key=lambda a: a[key])
        best = None
        for start in range(len(seq)):
            rot = seq[start:] + seq[:start]
            sec = [a["sector"] for a in rot]
            inv = sum(1 for i in range(len(sec) - 1) if sec[i + 1] < sec[i])
            if best is None or inv < best[0]:
                best = (inv, [f"{a['label']}:{a['sector']}" for a in rot])
        return best
    inv_cc, seq_cc = inversions("h_cbcr")
    inv_lab, seq_lab = inversions("h_lab")
    # Angle-versus-scale coupling: one k for all strong, unclipped patches (w free per patch).
    strong = [(l, key) for l, rec in rows.items() for key in ("07", "08")
              if rec[key]["n_sigma"] >= 8 and not rec["clipped"]]

    def chi_k(k, items):
        tot = 0.0
        for l, key in items:
            rec = rows[l][key]
            Zs = Z[rec["sector"]]
            u_ = abs(Zs) * complex(math.cos(k * cmath_phase(Zs)), math.sin(k * cmath_phase(Zs))) - 1
            dz = cc[probeA if key == "07" else probeB][l] / cbase[l] - 1
            w = (dz * u_.conjugate()).real / abs(u_) ** 2
            tot += abs(dz - w * u_) ** 2 / sig[l] ** 2
        return tot

    ks = np.arange(0.3, 2.001, 0.01)
    chis = [chi_k(k, strong) for k in ks]
    k_best = float(ks[int(np.argmin(chis))])
    rng = np.random.default_rng(20261019)
    boots = []
    for _ in range(1000):
        pick = [strong[i] for i in rng.integers(0, len(strong), len(strong))]
        boots.append(float(ks[int(np.argmin([chi_k(k, pick) for k in ks]))]))
    # Equal-spacing tests in several hue measures, and the free per-patch lower bound.
    raw_h = raw_hue_planes(frames["R8051160"])
    _, ms_stock = design_ratios(coeffs, display)
    for l in CHROMATIC:
        key = "07" if rows[l]["07"]["n_sigma"] >= rows[l]["08"]["n_sigma"] else "08"
        raw_h[l]["h_cbcr_input_est"] = (rows[l]["h_cbcr"] - math.degrees(cmath_phase(ms_stock[rows[l][key]["sector"]]))) % 360
    obs = []
    for l in CHROMATIC:
        if l in clipped:
            continue
        o = {"label": l, "dzA": cc[probeA][l] / cbase[l] - 1, "dzB": cc[probeB][l] / cbase[l] - 1, "sig": sig[l],
             "h_cbcr": rows[l]["h_cbcr"], "h_lab": rows[l]["h_lab"], **raw_h[l]}
        obs.append(o)
    free = sum((rows[o["label"]]["07"]["resid"] ** 2 + rows[o["label"]]["08"]["resid"] ** 2) / o["sig"] ** 2 for o in obs)
    spacing = {}
    for key in ["h_cbcr", "h_lab"] + sorted(raw_h[CHROMATIC[0]]):
        if key in ("h_cbcr", "h_lab") and key in raw_h[CHROMATIC[0]]:
            continue
        spacing[key] = {m: equal_spacing_fit(obs, key, Z, m) for m in ("interp", "hard")}
    return {
        "base_mode": base_mode, "row5_frames": row5, "probe_frames": {"07": probeA, "08": probeB},
        "signature": signature, "identity_test": identity, "clipped": clipped,
        "design": {str(s): {"scale": abs(z), "angle_deg": math.degrees(cmath_phase(z)),
                            "scale_no_modifier": abs(Z_nomod[s]), "angle_no_modifier": math.degrees(cmath_phase(Z_nomod[s]))}
                   for s, z in Z.items()},
        "patches": rows, "assignments": assign,
        "sector_sequence_by_cbcr_hue": seq_cc, "inversions_cbcr": inv_cc,
        "sector_sequence_by_lab_hue": seq_lab, "inversions_lab": inv_lab,
        "angle_vs_scale_k": {"best": k_best, "boot_p05_p95": [float(np.percentile(boots, 5)), float(np.percentile(boots, 95))],
                             "n_items": len(strong), "chi2_at_best": float(min(chis)), "chi2_at_1": float(chi_k(1.0, strong))},
        "equal_spacing": spacing, "free_decomposition_chi2": float(free), "n_obs_equal_spacing": 4 * len(obs),
    }


def sector_table(probe):
    """Empirical sector map from the >= 2 sigma assignments (strength tagged)."""
    assign = sorted(probe["assignments"], key=lambda a: a["h_cbcr"])
    k0 = min(range(len(assign)), key=lambda i: (assign[i]["sector"], assign[i]["h_cbcr"]))
    seq = assign[k0:] + assign[:k0]  # cyclic order starting at the lowest sector
    table = []
    for s in range(24):
        row = {"sector": s, "probe": "07" if s in PROBE_SECTORS["07"] else ("08" if s in PROBE_SECTORS["08"] else None)}
        hits = [a for a in seq if a["sector"] == s]
        if hits:
            top = max(hits, key=lambda a: a["w"])
            row.update({"patches": [{"label": a["label"], "w": round(a["w"], 2), "n_sigma": round(a["n_sigma"], 1),
                                     "strength": a["strength"], "clipped": a["clipped"],
                                     "h_cbcr": round(a["h_cbcr"], 1), "h_lab": round(a["h_lab"], 1)} for a in hits],
                        "strongest": top["label"], "strongest_w": round(top["w"], 2)})
        if s % 2 == 1:
            lo = [a for a in seq if a["sector"] == (s - 1) % 24]
            hi = [a for a in seq if a["sector"] == (s + 1) % 24]
            if lo and hi:
                a_lo, a_hi = lo[-1], hi[0]
                row["between"] = {"after": a_lo["label"], "after_h_cbcr": round(a_lo["h_cbcr"], 1), "after_h_lab": round(a_lo["h_lab"], 1),
                                  "before": a_hi["label"], "before_h_cbcr": round(a_hi["h_cbcr"], 1), "before_h_lab": round(a_hi["h_lab"], 1)}
        table.append(row)
    return table


# ----------------------------------------------------------------- main

def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, complex):
        return [x.real, x.imag]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    return x


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    LOCAL.mkdir(parents=True, exist_ok=True)
    de_test = float(delta_e00([50, 2.6772, -79.7751], [50, 0, -82.7485]))
    if abs(de_test - 2.0425) > 1e-3:
        raise SystemExit(f"CIEDE2000 self-test failed: {de_test}")
    before = capture_hashes()
    if len(before) != 18:
        raise SystemExit(f"expected 18 capture files, found {len(before)}")
    curves, coeffs, checks, rawhex = parse_deep_tables()
    if not all(v for k, v in checks.items() if k.endswith(("official", "fit_json", "measurements"))):
        raise SystemExit(f"table cross-check failed: {checks}")
    frames = measure_all()
    ident = identify_tones(frames, curves)
    probe = probe_section(frames, coeffs, ident, "1160")
    probe_mean = probe_section(frames, coeffs, ident, "mean")
    table = sector_table(probe)
    order = {}
    for stem in STEMS:
        row = ident[stem]["best_row"]
        if ident[stem]["best"] == "stock_row5":
            if stem == probe["probe_frames"]["07"]:
                row = "07 PrbA"
            elif stem == probe["probe_frames"]["08"]:
                row = "08 PrbB"
            else:
                row = "04 Std"
        m = frames[stem]["meta"]
        order[stem] = {"expected": EXPECTED[stem], "identified": row, "selector": m["selector"],
                       "program": m["program"], "metering": m["metering"], "bias_ev": m["bias_ev"],
                       "t": m["t"], "f": m["f"], "iso": m["iso"], "bv": m["bv"], "when": m["when"],
                       "wb_exif": m["exif_white_balance"], "wb_record_0x26": m["wb_mode_record_0x26"],
                       "asn": m["asn"], "tone_best": ident[stem]["best"],
                       "tone_best_median_abs": ident[stem]["best_median_abs"],
                       "tone_second": ident[stem]["second"], "tone_second_median_abs": ident[stem]["second_median_abs"]}
    drift = drift_section(frames, "R8051152", "R8051160")
    meter = metering_section(frames, curves)
    tone = tone_section(frames, curves, ident)
    colour = colour_section(frames, curves, ident)
    after = capture_hashes()
    result = {
        "capture_sha256_before": before, "capture_sha256_after": after, "unchanged": before == after,
        "table_checks": checks, "order": order,
        "frames": {s: {k: v for k, v in f.items() if not k.startswith("_")} for s, f in frames.items()},
        "tone_identification": ident, "drift": drift, "metering": meter, "tone": tone, "colour_vs_04": colour,
        "probe": probe, "probe_mean_baseline": probe_mean, "sector_table": table, "de00_self_test": de_test,
    }
    (LOCAL / "measurements.json").write_text(json.dumps(jsonable(result), indent=1) + "\n")
    (LOCAL / "tables_used.json").write_text(json.dumps({
        "note": "Bytes from firmware/stage2e/deep_tables.c (Ricoh-derived stock rows, Fujifilm-fit curves). Local only.",
        "tables_hex": rawhex, "stock_coeffs": coeffs["stock"], "probe07_coeffs": coeffs["07"], "probe08_coeffs": coeffs["08"],
    }, indent=1) + "\n")
    (LOCAL / "sha256.json").write_text(json.dumps({"before": before, "after": after}, indent=1) + "\n")
    print_summary(result)


def print_summary(r):
    print("captures unchanged:", r["unchanged"], "| table checks:", r["table_checks"])
    print("\n== order")
    for s, o in r["order"].items():
        print(f"{s} expected {o['expected']:<26} identified {o['identified']:<9} sel {o['selector']} prog {o['program']} "
              f"meter {o['metering']} EC {o['bias_ev']} t {o['t']} BV {o['bv']} WB exif/rec {o['wb_exif']}/{o['wb_record_0x26']} "
              f"tone {o['tone_best']} {o['tone_best_median_abs']:.2f} (2nd {o['tone_second']} {o['tone_second_median_abs']:.1f})")
    d = r["drift"]
    print("\n== drift", d["pair"], "u ratio", round(d["u_ratio_median"], 4), "EV", round(d["u_ratio_ev"], 3))
    for g, v in d["greys"].items():
        print(f"  {g} dY {v['jpeg_y_diff']:+.2f} dRGB {np.round(v['jpeg_rgb_diff'], 2)} u ratio {v['u_ratio']:.4f}")
    for key in ("de00_raw", "de00_wb", "chromatic_dh_cbcr", "chromatic_cc_ratio", "chromatic_dh_lab", "chromatic_C_ratio", "chromatic_dL"):
        v = d[key]
        print(f"  {key}: median {v['median']:.3f} median_abs {v['median_abs']:.3f} max_abs {v['max_abs']:.3f}")
    m = r["metering"]
    print("\n== metering", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m["R8051152"].items() if k != "jpeg_rgb_D4"})
    print("  row5(320) =", round(m["row5_at_u_assumed"], 2), "row5^-1(118) =", round(m["row5_inverse_118"], 1))
    for k, v in m["bv_hypotheses"].items():
        print(f"  spot={k:6} sd {v['sd_ev']:.3f} EV  u_m {v['u_m']:.4f} ({v['ev_vs_assumed']:+.2f} EV)")
    print("\n== tone landing")
    for s, t in r["tone"].items():
        e, se = t["err"], t["stock_err"]
        pc = t["per_channel_err"]
        print(f"  {s} {t['row']:<26} median {e['median']:+.2f} med|e| {e['median_abs']:.2f} MAD {e['mean_abs']:.2f} max {e['max_abs']:.2f} "
              f"| per-channel median {pc['median']:+.2f} MAD {pc['mean_abs']:.2f} max {pc['max_abs']:.2f} "
              f"| stock: median {se['median']:+.2f} MAD {se['mean_abs']:.2f} max {se['max_abs']:.2f}")
    c = r["colour_vs_04"]
    print("\n== colour vs 04 (tone/chroma hypotheses), raw13 identical:", c["raw13_identical_all_2e"], "record diffs", c["record_bytes_differing_between_2e_frames"])
    for era in ("2e", "2d"):
        for s, v in c[era].items():
            g = v["groups"]
            print(f"  {era} {s} {v['curve']:<10} " + " ".join(f"{k}:{x['median']:.2f}/{x['max_abs']:.2f}" for k, x in v["de00_summary"].items())
                  + f" | cc ratio med {v['obs_cc_ratio']['median']:+.3f} | H3 resid dh_cc OG {g['OG']['h3_resid_dh_cbcr_median']:+.2f} BRM {g['BRM']['h3_resid_dh_cbcr_median']:+.2f}"
                  f" lab OG {g['OG']['h3_resid_dh_lab_median']:+.2f} BRM {g['BRM']['h3_resid_dh_lab_median']:+.2f}")
    for key in ("probe", "probe_mean_baseline"):
        p = r[key]
        print(f"\n== {key} base {p['base_mode']} frames {p['probe_frames']} clipped {p['clipped']}")
        print("  signature", {s: (v["n_patches_over_6sigma"], round(v["max_dz"], 3)) for s, v in p["signature"].items()}, p["identity_test"])
        print("  k angle/scale", p["angle_vs_scale_k"], "inversions cbcr/lab", p["inversions_cbcr"], p["inversions_lab"])
        print("  seq cbcr", " ".join(p["sector_sequence_by_cbcr_hue"]))
        print("  seq lab ", " ".join(p["sector_sequence_by_lab_hue"]))
        print("  free decomposition chi2", round(p["free_decomposition_chi2"], 1), "n_obs", p["n_obs_equal_spacing"])
        for plane, v in p["equal_spacing"].items():
            print(f"  equal spacing {plane:18} interp chi2 {v['interp']['chi2']:8.1f} (H0 {v['interp']['H0']:.1f} d {v['interp']['direction']} kw {v['interp']['kw']:.2f})"
                  f"  hard chi2 {v['hard']['chi2']:8.1f}")
        if key == "probe":
            print("  label  h_cc  h_lab  | 07: s w nsig dh_cc ratio dh_lab Clab | 08: s w nsig dh_cc ratio dh_lab Clab")
            for l, rec in sorted(p["patches"].items(), key=lambda kv: kv[1]["h_cbcr"]):
                cells = []
                for k2 in ("07", "08"):
                    x = rec[k2]
                    cells.append(f"s{x['sector']:2d} w{x['w']:5.2f} {x['n_sigma']:5.1f}s {x['dh_cbcr']:+5.1f} {x['cc_ratio']:.2f} {x['dh_lab']:+5.1f} {x['C_ratio_lab']:.2f}")
                print(f"  {l}{'c' if rec['clipped'] else ' '} {rec['h_cbcr']:6.1f} {rec['h_lab']:6.1f} | {cells[0]} | {cells[1]}")
    print("\n== sector table")
    for row in r["sector_table"]:
        print("  ", {k: v for k, v in row.items()})


if __name__ == "__main__":
    main()
