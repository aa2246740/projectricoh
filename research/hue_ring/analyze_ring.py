#!/usr/bin/env python3
"""Hue-ring analysis: where the 24 colour-table sectors sit, and how they blend.

Usage
  python3 -I research/hue_ring/analyze_ring.py DIR            # real shots (DNG+JPG)
  python3 -I research/hue_ring/analyze_ring.py --selftest     # synthetic recovery test
  python3 -I research/hue_ring/analyze_ring.py --from-stage2e # partial model from the 2e chart

Real shots: 04 / 07 / 08 / 04 at ISO 100 and ISO 1600 of research/hue_ring/hue_ring.png
on a screen, plus one 04 A-mode spot-metered ColorChecker frame. Frames are
grouped by ISO; within a group the 04 pair is the most similar first/last pair,
and 07 vs 08 is the assignment under which sector number runs monotonically
with CbCr hue (stage 2e rule; shooting order is reported as a cross-check).

Geometry: four checkerboard corner markers (3/4/6/8 cells, TL/TR/BR/BL) give
the orientation; a homography from their inner corners maps patches.json ROIs
(inset from the patch edges) into the photo. Each ROI is checked for clipping
(JPEG and raw), moire (narrow-band FFT peaks) and edge intrusion.

Model: z = c_probe / c_04 on the JPEG CbCr plane, z - 1 = sum g w_s(h) (Zk_s - 1)
(stage 2e form). The fit gives 24 node hues, the kernel (hard / linear, with a
Gaussian blur that may scale with 1/chroma as per-pixel noise would), the gain
at a node, the angle/scale coupling k, and tests for luminance (ring) and ISO
dependence, with bootstrap 90% intervals. See sector_model.py.

Writes only research/hue_ring/local/ (gitignored) and, for the self-test,
/tmp/gxr_hue_ring_selftest/. Captures are opened read-only.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from scipy import ndimage  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
LAYOUT_JSON = HERE / "patches.json"
RING_PNG = HERE / "hue_ring.png"
STAGE2E = ROOT / "research/stage2e_verification/local/measurements.json"
TABLES2E = ROOT / "research/stage2e_verification/local/tables_used.json"
SELFTEST_TMP = Path("/tmp/gxr_hue_ring_selftest")
D4_PUBLISHED_Y = 0.191
U_M_ASSUMED = 320 / 4095


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sm = load_module("sector_model", HERE / "sector_model.py")
pp = load_module("pilplot", HERE / "pilplot.py")
_MODS = {}


def s2d():
    if "s2d" not in _MODS:
        _MODS["s2d"] = load_module("s2d", ROOT / "research/stage2d_verification/analyze.py")
    return _MODS["s2d"]


def a2e():
    if "a2e" not in _MODS:
        _MODS["a2e"] = load_module("a2e", ROOT / "research/stage2e_verification/analyze_2e.py")
    return _MODS["a2e"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ----------------------------------------------------------------- colour

def srgb_to_linear(v):
    v = np.asarray(v, dtype=np.float64)
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(v):
    v = np.asarray(v, dtype=np.float64)
    return np.where(v <= 0.0031308, 12.92 * v, 1.055 * np.clip(v, 0, None) ** (1 / 2.4) - 0.055)


_M709 = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
_WHITE = np.array([0.95047, 1.0, 1.08883])


def lab_from_srgb_codes(rgb255):
    lin = srgb_to_linear(np.clip(np.asarray(rgb255, float), 0, 255) / 255)
    t = (lin @ _M709.T) / _WHITE
    d = 6 / 29
    f = np.where(t > d ** 3, np.cbrt(t), t / (3 * d * d) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


# ----------------------------------------------------------------- layout

def load_layout():
    lay = json.loads(LAYOUT_JSON.read_text())
    pats = lay["patches"]
    ids = [p["id"] for p in pats]
    ring = np.array([p["ring"] or 0 for p in pats])
    mid = [p["id"] for p in pats if p["name"] in ("G_L40", "G_L50", "G_L60")]
    greys = [p["id"] for p in pats if p["group"] == "gray"]
    return {"raw": lay, "patches": pats, "ids": ids, "ring": ring, "markers": {m["corner"]: m for m in lay["markers"]},
            "mid_grey_ids": mid, "grey_ids": greys, "index": {p["id"]: i for i, p in enumerate(pats)}}


# ----------------------------------------------------------------- homography

def dlt(src, dst):
    src, dst = np.asarray(src, float), np.asarray(dst, float)

    def norm(p):
        c = p.mean(0)
        s = math.sqrt(2) / max(np.sqrt(((p - c) ** 2).sum(1)).mean(), 1e-9)
        return np.array([[s, 0, -s * c[0]], [0, s, -s * c[1]], [0, 0, 1]])
    Ts, Td = norm(src), norm(dst)
    a = apply_h(Ts, src)
    b = apply_h(Td, dst)
    rows = []
    for (u, v), (x, y) in zip(a, b):
        rows.append([u, v, 1, 0, 0, 0, -x * u, -x * v, -x])
        rows.append([0, 0, 0, u, v, 1, -y * u, -y * v, -y])
    _, _, vt = np.linalg.svd(np.asarray(rows))
    H = np.linalg.inv(Td) @ vt[-1].reshape(3, 3) @ Ts
    return H / H[2, 2]


def apply_h(H, pts):
    pts = np.asarray(pts, float)
    q = np.c_[pts.reshape(-1, 2), np.ones(pts.reshape(-1, 2).shape[0])] @ H.T
    return (q[:, :2] / q[:, 2:3]).reshape(pts.shape)


def local_jacobian(H, u, v, e=0.5):
    p = apply_h(H, [[u, v], [u + e, v], [u, v + e]])
    return np.c_[(p[1] - p[0]) / e, (p[2] - p[0]) / e]  # columns: d/du, d/dv


# ----------------------------------------------------------------- markers

def gray_of(rgb):
    rgb = np.asarray(rgb, dtype=np.float64)
    return (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]) / 255.0


def block_mean(a, f):
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    return a[:h, :w].reshape(h // f, f, w // f, f).mean(axis=(1, 3))


def marker_candidates(g, n=8):
    f = max(1, int(round(g.shape[1] / 1100)))
    s = ndimage.gaussian_filter(block_mean(g, f), 0.7)
    win = max(9, int(round(0.042 * s.shape[1])))
    E = ndimage.uniform_filter(np.hypot(ndimage.sobel(s, 1), ndimage.sobel(s, 0)), win)
    B = ndimage.maximum_filter(s, win)
    D = ndimage.minimum_filter(s, win)
    S = E * np.clip((B - D - 0.45) / 0.45, 0, 1) ** 2
    out = []
    yy, xx = np.ogrid[:S.shape[0], :S.shape[1]]
    for _ in range(n):
        iy, ix = np.unravel_index(int(np.argmax(S)), S.shape)
        if S[iy, ix] <= 0:
            break
        out.append({"score": float(S[iy, ix]), "xy": ((ix + 0.5) * f, (iy + 0.5) * f)})
        S[(yy - iy) ** 2 + (xx - ix) ** 2 < (2.5 * win) ** 2] = 0
    return out, win * f


def refine_marker(g, xy, size):
    x, y = xy
    r = int(1.3 * size)
    x0, x1 = max(0, int(x - r)), min(g.shape[1], int(x + r))
    y0, y1 = max(0, int(y - r)), min(g.shape[0], int(y + r))
    sub = g[y0:y1, x0:x1]
    lo, hi = np.percentile(sub, 2), np.percentile(sub, 99.5)
    m = sub > lo + 0.6 * (hi - lo)
    filled = ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=2))
    lab, n = ndimage.label(filled)
    best = None
    for k, sl in enumerate(ndimage.find_objects(lab)):
        comp = lab[sl] == k + 1
        area = int(comp.sum())
        hgt, wid = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if area < 0.25 * size * size or area > 4 * size * size:
            continue
        if not (0.5 < hgt / wid < 2) or area / (hgt * wid) < 0.6:
            continue
        cy, cx = ndimage.center_of_mass(lab == k + 1)
        d = math.hypot(cx + x0 + 0.5 - x, cy + y0 + 0.5 - y)
        if best is None or d < best[0]:
            best = (d, cx + x0 + 0.5, cy + y0 + 0.5, math.sqrt(area))
    if best is None:
        return None
    return {"xy": (best[1], best[2]), "size_px": best[3]}


def sample_bilinear(g, pts):
    pts = np.asarray(pts, float)
    return ndimage.map_coordinates(g, [pts[..., 1] - 0.5, pts[..., 0] - 0.5], order=1, mode="nearest")


def checker_corr(g, H, m, n):
    x0, y0, x1, y1 = m["checker_bbox_px"]
    cell = (x1 - x0) / n
    offs = np.array([[0, 0], [0.18, 0], [-0.18, 0], [0, 0.18], [0, -0.18]]) * cell
    jj, ii = np.meshgrid(np.arange(n), np.arange(n))
    centres = np.stack([x0 + (jj.ravel() + 0.5) * cell, y0 + (ii.ravel() + 0.5) * cell], -1)
    pts = apply_h(H, centres[:, None, :] + offs[None, :, :])
    v = sample_bilinear(g, pts).mean(1)
    p = np.where((ii.ravel() + jj.ravel()) % 2 == 0, -1.0, 1.0)
    v = v - v.mean()
    p = p - p.mean()
    den = math.sqrt((v * v).sum() * (p * p).sum())
    return float((v * p).sum() / den) if den > 0 else 0.0


ORDER = ("TL", "TR", "BR", "BL")


def saddle_refine(g, p, J, cell_screen):
    """Sub-pixel checker corner near image point p; J maps screen offsets to image offsets."""
    half = 0.36 * cell_screen
    t = np.linspace(-half, half, 15)
    du, dv = np.meshgrid(t, t)
    keep = (np.abs(du) > 0.1 * cell_screen) & (np.abs(dv) > 0.1 * cell_screen)
    T = (np.sign(du) * np.sign(dv))[keep]
    off = np.stack([du[keep], dv[keep]], -1) @ J.T
    cell_img = cell_screen * math.sqrt(abs(np.linalg.det(J)))
    rng = max(2, int(round(0.25 * cell_img)))
    shifts = np.arange(-rng, rng + 1)
    sy, sx = np.meshgrid(shifts, shifts, indexing="ij")
    sh = np.stack([sx.ravel(), sy.ravel()], -1)
    vals = sample_bilinear(g, p[None, None, :] + sh[:, None, :] + off[None, :, :])
    R = np.abs((vals * T[None, :]).sum(1)).reshape(len(shifts), len(shifts))
    a, b = np.unravel_index(int(np.argmax(R)), R.shape)
    if a in (0, len(shifts) - 1) or b in (0, len(shifts) - 1):
        return None

    def parab(m1, c0, p1):
        den = m1 - 2 * c0 + p1
        return 0.0 if den == 0 else 0.5 * (m1 - p1) / den
    dx = parab(R[a, b - 1], R[a, b], R[a, b + 1])
    dy = parab(R[a - 1, b], R[a, b], R[a + 1, b])
    contrast = float(R[a, b] / len(T))
    if contrast < 0.08:
        return None
    return np.array([p[0] + shifts[b] + dx, p[1] + shifts[a] + dy]), contrast


def locate_screen(rgb, lay):
    """Markers -> orientation -> refined homography screen->image. Raises ValueError if not a ring frame."""
    g = gray_of(rgb)
    cands, size = marker_candidates(g)
    if len(cands) < 4:
        raise ValueError("fewer than four marker candidates")
    refined = []
    for c in cands:
        r = refine_marker(g, c["xy"], size)
        if r is not None:
            refined.append({**c, **r})
    if len(refined) < 4:
        raise ValueError("marker refinement failed")
    mk = lay["markers"]
    src = np.array([mk[k]["center_px"] for k in ORDER])
    best = None
    from itertools import combinations
    for combo in combinations(range(min(len(refined), 6)), 4):
        pts = np.array([refined[i]["xy"] for i in combo])
        ctr = pts.mean(0)
        order = np.argsort(np.arctan2(pts[:, 1] - ctr[1], pts[:, 0] - ctr[0]))
        for mirror in (False, True):
            seq = order[::-1] if mirror else order
            for rot in range(4):
                idx = np.roll(seq, -rot)
                H = dlt(src, pts[idx])
                corr = {k: {n: checker_corr(g, H, mk[k], n) for n in (3, 4, 6, 8)} for k in ORDER}
                score = sum(corr[k][mk[k]["n_cells"]] for k in ORDER)
                if best is None or score > best[0]:
                    best = (score, H, corr, mirror, [refined[i] for i in combo])
    score, H, corr, mirror, used = best
    counts = {k: max(corr[k], key=lambda n: corr[k][n]) for k in ORDER}
    if score < 2.0 or any(counts[k] != mk[k]["n_cells"] for k in ORDER):
        raise ValueError(f"marker cell counts do not match: score {score:.2f}, counts {counts}")
    # refine with all inner corners
    S, D, C = [], [], []
    for k in ORDER:
        m = mk[k]
        for (u, v) in m["inner_corners_px"]:
            J = local_jacobian(H, u, v)
            res = saddle_refine(g, apply_h(H, [u, v]), J, m["cell_px"])
            if res is not None:
                S.append((u, v))
                D.append(res[0])
                C.append(res[1])
    S, D = np.array(S), np.array(D)
    keep = np.ones(len(S), bool)
    rms = float("nan")
    if len(S) >= 8:
        for _ in range(4):
            H2 = dlt(S[keep], D[keep])
            r = np.linalg.norm(apply_h(H2, S) - D, axis=1)
            med = float(np.median(r[keep]))
            new = r < max(1.5, 4 * med)
            if new.sum() < 8 or np.array_equal(new, keep):
                break
            keep = new
        H = dlt(S[keep], D[keep])
        rms = float(np.sqrt(np.mean(np.linalg.norm(apply_h(H, S[keep]) - D[keep], axis=1) ** 2)))
    # rotation of the screen in the image (deg) and scale (image px per screen px)
    J = local_jacobian(H, 1728, 1117)
    rot = math.degrees(math.atan2(J[1, 0], J[0, 0]))
    return {"H": H, "Hinv": np.linalg.inv(H), "marker_score": score, "marker_cells": counts, "mirrored": mirror,
            "corners_used": int(keep.sum()), "corners_found": int(len(S)), "corner_rms_px": rms,
            "rotation_deg": rot, "scale": float(math.sqrt(abs(np.linalg.det(J)))),
            "marker_centres_img": {k: apply_h(H, mk[k]["center_px"]).tolist() for k in ORDER}}


# ----------------------------------------------------------------- sampling

def roi_mask(geo, rect, shape):
    corners = np.array([[rect[0], rect[1]], [rect[2], rect[1]], [rect[2], rect[3]], [rect[0], rect[3]]], float)
    q = apply_h(geo["H"], corners)
    x0, x1 = max(0, int(math.floor(q[:, 0].min()))), min(shape[1], int(math.ceil(q[:, 0].max())))
    y0, y1 = max(0, int(math.floor(q[:, 1].min()))), min(shape[0], int(math.ceil(q[:, 1].max())))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    jj, ii = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
    uv = apply_h(geo["Hinv"], np.stack([jj, ii], -1))
    mask = (uv[..., 0] >= rect[0]) & (uv[..., 0] <= rect[2]) & (uv[..., 1] >= rect[1]) & (uv[..., 1] <= rect[3])
    xs, ys = np.sort(q[:, 0]), np.sort(q[:, 1])
    inner = [int(math.ceil(xs[1])), int(math.ceil(ys[1])), int(math.floor(xs[2])), int(math.floor(ys[2]))]
    return (y0, y1, x0, x1, mask, inner)


def moire_metrics(block):
    """Narrow-band periodic structure inside a flat ROI. block: (h, w, 3) RGB codes."""
    if block.shape[0] < 24 or block.shape[1] < 24:
        return None
    ycc = sm.ycbcr(block)
    h, w = block.shape[:2]
    win = np.outer(np.hanning(h), np.hanning(w))
    fy = np.fft.fftfreq(h)[:, None] * h
    fx = np.fft.fftfreq(w)[None, :] * w
    dc = (np.abs(fy) <= 2) & (np.abs(fx) <= 2)
    out = {}
    for k, name in enumerate(("Y", "Cb", "Cr")):
        x = ycc[..., k] - ycc[..., k].mean()
        F = np.abs(np.fft.fft2(x * win))
        F[dc] = 0
        pw = F ** 2
        peak = float(pw.max())
        med = float(np.median(pw[~dc]))
        out[name] = {"peak_ratio": peak / max(med, 1e-12), "peak_amp": float(8 * math.sqrt(peak) / (h * w)),
                     "ac_rms": float(x.std())}
    return out


def raw_quads(crop, black, white, neutral, origin, rect):
    """Per 2x2-quad WB gamma CbCr hue inside rect = [x0, y0, x1, y1] (crop coords)."""
    ox, oy = origin
    x0, y0, x1, y1 = rect
    sy, sx = (oy + y0) & 1, (ox + x0) & 1  # quads must start on R
    c = (crop[y0 + sy:y1, x0 + sx:x1].astype(np.float64) - black) / (white - black)
    h, w = (c.shape[0] // 2) * 2, (c.shape[1] // 2) * 2
    c = c[:h, :w]
    if h < 4 or w < 4:
        return None
    n = np.asarray(neutral, float)
    r = c[0::2, 0::2] / n[0]
    g = 0.5 * (c[0::2, 1::2] + c[1::2, 0::2]) / n[1]
    b = c[1::2, 1::2] / n[2]
    rgb = np.clip(np.stack([r, g, b], -1), 1e-6, None) ** (1 / 2.2)
    ycc = sm.ycbcr(rgb)
    z = ycc[..., 1] + 1j * ycc[..., 2]
    zm = z.mean()
    hue_sd = float(np.degrees(np.std(np.angle(z / zm)))) if abs(zm) > 0 else float("nan")
    return {"quad_hue_sd_deg": hue_sd, "quad_chroma_rel_sd": float(np.std(np.abs(z)) / max(abs(zm), 1e-9))}


def sample_frame(rgb, geo, lay, inset, raw=None, clip_hi=253, clip_lo=2):
    shape = rgb.shape
    out = []
    g = gray_of(rgb)
    for p in lay["patches"]:
        x0, y0, x1, y1 = p["bbox_px"]
        rect = [x0 + inset, y0 + inset, x1 - inset, y1 - inset]
        m = roi_mask(geo, rect, shape)
        if m is None:
            out.append({"id": p["id"], "ok": False, "reason": "roi outside frame"})
            continue
        ya, yb, xa, xb, mask, inner = m
        px = rgb[ya:yb, xa:xb][mask].astype(np.float64)
        mean = px.mean(0)
        srt = np.sort(px, axis=0)
        k = int(0.1 * len(srt))
        trim = srt[k:len(srt) - k].mean(0) if len(srt) > 20 else mean
        ycc_px = sm.ycbcr(px)
        zc = ycc_px[:, 1] + 1j * ycc_px[:, 2]
        zm = complex(*sm.ycbcr(mean)[1:])
        pix_hue_sd = float(np.degrees(np.std(np.angle(zc / zm)))) if abs(zm) > 3 else None
        clip = float(np.mean((px >= clip_hi) | (px <= clip_lo)))
        ix0, iy0, ix1, iy1 = inner
        block = rgb[iy0:iy1, ix0:ix1].astype(np.float64) if (ix1 - ix0 > 8 and iy1 - iy0 > 8) else None
        moire = moire_metrics(block) if block is not None else None
        rec = {"id": p["id"], "ok": True, "n_px": int(len(px)), "rgb": mean.tolist(), "rgb_trim": trim.tolist(),
               "rgb_sd": px.std(0).tolist(), "luma_sd": float(g[ya:yb, xa:xb][mask].std() * 255),
               "ycc": sm.ycbcr(mean).tolist(), "pix_hue_sd_deg": pix_hue_sd, "clip_frac": clip, "moire": moire,
               "inner_rect": inner}
        if raw is not None:
            crop, black, white, neutral, origin = raw
            oxr, oyr = origin
            ix0, iy0, ix1, iy1 = inner
            dn = np.array(s2d().cfa_means(crop, iy0, iy1, ix0, ix1, oyr, oxr))
            cam = (dn - black) / (white - black)
            rmax = float(crop[iy0:iy1, ix0:ix1].max())
            rec.update({"raw_dn": dn.tolist(), "cam_wb": (cam / neutral).tolist(),
                        "u": float((cam / neutral) @ np.array([0.25, 0.5, 0.25])),
                        "raw_max_frac_of_white": (rmax - black) / (white - black)})
            q = raw_quads(crop, black, white, neutral, origin, inner)
            if q:
                rec.update(q)
        out.append(rec)
    return out


def flag_patch(rec, args):
    flags = []
    if not rec.get("ok"):
        return ["no-roi"]
    if rec["clip_frac"] > 0.01 or max(rec["rgb"]) > 250 or min(rec["rgb"]) < 4:
        flags.append("jpeg-clip")
    if rec.get("raw_max_frac_of_white", 0) >= 0.98:
        flags.append("raw-clip")
    mo = rec.get("moire")
    if mo:
        for ch, v in mo.items():
            if v["peak_ratio"] > args.moire_ratio and v["peak_amp"] > args.moire_amp:
                flags.append(f"moire-{ch}")
                break
    if rec["luma_sd"] > args.edge_sd:
        flags.append("edge-or-texture")
    return flags


def gap_check(rgb, geo, lay):
    """Background samples on the gap centre lines between neighbouring patches."""
    g = gray_of(rgb)
    grid = lay["raw"]["meta"]["grid"]
    ox, oy = grid["origin_px"]
    pitch, block = grid["pitch_px"], grid["block_px"]
    pts = []
    for r in range(grid["rows"]):
        for c in range(grid["cols"] - 1):
            pts.append((ox + c * pitch + block + (pitch - block) / 2, oy + r * pitch + block / 2))
    for r in range(grid["rows"] - 1):
        for c in range(grid["cols"]):
            pts.append((ox + c * pitch + block / 2, oy + r * pitch + block + (pitch - block) / 2))
    v = sample_bilinear(g, apply_h(geo["H"], np.array(pts)))
    med = float(np.median(v))
    return {"n": len(v), "median": med, "frac_off_by_0.08": float(np.mean(np.abs(v - med) > 0.08)),
            "p95_abs_dev": float(np.percentile(np.abs(v - med), 95))}


# ----------------------------------------------------------------- metadata

EXIF_TAGS = {0x8822: "ExposureProgram", 0x9207: "MeteringMode", 0x9204: "ExposureBiasValue",
             0x9203: "BrightnessValue", 0xA402: "ExposureMode", 0xA403: "WhiteBalance", 0x829A: "ExposureTime",
             0x829D: "FNumber", 0x8827: "ISO", 0x9003: "DateTimeOriginal", 0x9291: "SubSecTimeOriginal"}


def read_meta(jpg, dng, sidecar):
    if sidecar is not None and jpg.name in sidecar:
        return dict(sidecar[jpg.name], source="sidecar")
    S = s2d()
    meta = {"source": "exif"}
    try:
        tiff = S.Tiff(dng.read_bytes()) if dng is not None else S.jpeg_tiff(jpg)
        root = tiff.ifd(tiff.root)
        exif = tiff.ifd(root[34665]["value"][0])
        e = {name: exif[tag]["value"] for tag, name in EXIF_TAGS.items() if tag in exif}

        def first(k):
            v = e.get(k)
            return v[0] if isinstance(v, list) and v else v
        meta.update({"program": first("ExposureProgram"), "metering": first("MeteringMode"),
                     "bias_ev": first("ExposureBiasValue"), "bv": first("BrightnessValue"),
                     "exposure_mode": first("ExposureMode"), "wb_exif": first("WhiteBalance"),
                     "t": first("ExposureTime"), "f": first("FNumber"), "iso": first("ISO"),
                     "when": e.get("DateTimeOriginal"), "subsec": e.get("SubSecTimeOriginal")})
        try:
            info = S.shot_info(tiff)
            note = exif[37500]
            rec = tiff.ifd(note["offset"] + 8, ">")[0x1001]["raw"]
            meta.update({"selector": rec[0x28], "wb_record_0x26": rec[0x26], "display": info["color_display"],
                         "raw13": info["color_raw_13"]})
        except Exception as ex:  # noqa: BLE001
            meta["makernote_error"] = str(ex)
        if dng is not None and 50728 in root:
            meta["asn"] = root[50728]["value"]
    except Exception as ex:  # noqa: BLE001
        meta["exif_error"] = str(ex)
    return meta


def when_seconds(meta, fallback):
    w = meta.get("when")
    if not w:
        return float(fallback)
    try:
        d, t = str(w).split(" ")
        Y, M, D = map(int, d.split(":"))
        h, m, s = map(int, t.split(":"))
        sec = time.mktime((Y, M, D, h, m, s, 0, 0, -1))
        ss = meta.get("subsec")
        if ss:
            sec += float("0." + str(ss).strip())
        return sec
    except Exception:  # noqa: BLE001
        return float(fallback)


# ----------------------------------------------------------------- tables / design

def stock_curve():
    t = json.loads(TABLES2E.read_text())["tables_hex"]
    import struct
    a = bytes.fromhex(t["table_0_0"])
    b = bytes.fromhex(t["table_0_1"])
    xs = np.array([0, *struct.unpack(">31H", a), 4095], float)
    return xs, np.array(list(b), float)


def design_Z(display=None):
    """Probe/stock ratios with the five-colour modifier (stage 2e reading). Falls back to nominal."""
    try:
        t = json.loads(TABLES2E.read_text())
        coeffs = {"stock": [tuple(x) for x in t["stock_coeffs"]], "07": [tuple(x) for x in t["probe07_coeffs"]],
                  "08": [tuple(x) for x in t["probe08_coeffs"]]}
        if display is None:
            display = json.loads(STAGE2E.read_text())["frames"]["R8051160"]["meta"]["display"]
        Z, _ = a2e().design_ratios(coeffs, display)
        return {int(s): complex(v) for s, v in Z.items()}, "tables_used.json + five-colour modifier (local)"
    except Exception as ex:  # noqa: BLE001
        return sm.nominal_design(), f"nominal 1.30 / +-6,12,18 deg (local tables unavailable: {ex})"


# ----------------------------------------------------------------- frames

def load_frame(jpg, dng, meta, lay, args):
    rgb = np.asarray(Image.open(jpg).convert("RGB"))
    rec = {"file": jpg.name, "meta": meta}
    try:
        geo = locate_screen(rgb, lay)
    except ValueError as ex:
        rec["ring"] = False
        rec["why_not_ring"] = str(ex)
        return rec
    raw = None
    if dng is not None and not args.no_raw:
        S = s2d()
        crop, black, white, neutral, stats = S.decode_raw(S.Tiff(dng.read_bytes()))
        if crop.shape[:2] == rgb.shape[:2]:
            raw = (crop, black, white, np.asarray(neutral, float), tuple(stats["crop_origin_xy"]))
        else:
            rec["raw_note"] = f"raw crop {crop.shape} != jpeg {rgb.shape}; raw metrics skipped"
    patches = sample_frame(rgb, geo, lay, args.inset, raw)
    for p in patches:
        p["flags"] = flag_patch(p, args)
    rec.update({"ring": True, "geometry": {k: v for k, v in geo.items() if k not in ("H", "Hinv")},
                "H": geo["H"].tolist(), "gap_check": gap_check(rgb, geo, lay), "patches": patches,
                "shape": list(rgb.shape)})
    return rec


def wb_align(frame, ref_white, lay):
    """Von Kries on linear sRGB so the L*40/50/60 greys have the reference chromaticity."""
    idx = lay["index"]
    lin = {p["id"]: srgb_to_linear(np.array(p["rgb"]) / 255) for p in frame["patches"] if p.get("ok")}
    src = np.mean([lin[i] for i in lay["mid_grey_ids"]], axis=0)
    gain = (ref_white / ref_white.mean()) / (src / src.mean())
    out = {}
    for i, v in lin.items():
        out[i] = linear_to_srgb(v * gain) * 255
    return out, gain


def group_frames(frames):
    groups = {}
    for f in frames:
        groups.setdefault(f["meta"].get("iso"), []).append(f)
    for g in groups.values():
        g.sort(key=lambda f: (f["seq"]))
    return groups


def chromatic_ids(lay):
    return [p["id"] for p in lay["patches"] if p["ring"] in (1, 2)]


def identify(group, lay, Z, args):
    """04 pair, 07 and 08 inside one ISO group (four frames)."""
    notes = []
    if len(group) != 4:
        notes.append(f"expected 4 ring frames, got {len(group)}")
    ids = chromatic_ids(lay)
    ref = np.mean([srgb_to_linear(np.array(next(p for p in group[0]["patches"] if p["id"] == i)["rgb"]) / 255)
                   for i in lay["mid_grey_ids"]], axis=0)
    C = []
    for f in group:
        al, gain = wb_align(f, ref, lay)
        f["_aligned"] = al
        f["wb_gain"] = gain.tolist()
        C.append(np.array([complex(*sm.ycbcr(al[i])[1:]) for i in ids]))
    n = len(group)
    D = np.full((n, n), np.inf)
    for i in range(n):
        for j in range(i + 1, n):
            D[i, j] = D[j, i] = float(np.median(np.abs(C[i] / C[j] - 1)))
    i0, j0 = np.unravel_index(int(np.argmin(D)), D.shape)
    base = sorted((int(i0), int(j0)))
    if base != [0, n - 1]:
        notes.append(f"most similar pair is {base}, not first/last; using it as the 04 pair")
    probes = [k for k in range(n) if k not in base]
    if len(probes) != 2:
        raise SystemExit(f"cannot identify probes: {notes}")
    cb = 0.5 * (C[base[0]] + C[base[1]])
    sig = np.maximum(np.abs(C[base[1]] / C[base[0]] - 1) / math.sqrt(2), args.sig_floor)
    h = sm.hue_deg(cb)
    vec = sm.probe_vectors(Z, 0.97)

    def inversions(pa, pb):
        items = []
        for key, k in (("07", pa), ("08", pb)):
            dz = C[k] / cb - 1
            secs = sm.PROBE_SECTORS[key]
            U = np.array([vec[key][s] - 1 for s in secs])
            w = (dz[:, None] * U.conj()[None, :]).real / np.abs(U)[None, :] ** 2
            res = np.abs(dz[:, None] - w * U[None, :])
            best = np.argmin(res, axis=1)
            wb = w[np.arange(len(dz)), best]
            ok = (np.abs(dz) / sig >= 3) & (wb > 0.1)
            items += [(float(h[t]), secs[best[t]]) for t in np.where(ok)[0]]
        items.sort()
        bestinv = None
        for k in range(len(items)):
            seq = [x[1] for x in items[k:] + items[:k]]
            inv = sum(1 for a in range(len(seq) - 1) if seq[a + 1] < seq[a])
            bestinv = inv if bestinv is None else min(bestinv, inv)
        return bestinv, len(items)

    inv_a, na = inversions(probes[0], probes[1])
    inv_b, nb = inversions(probes[1], probes[0])

    def fit_chi2(pa, pb):
        """Best chi2 of a monotone sector model under this 07/08 assignment."""
        ring = np.array([lay["patches"][lay["index"][i]]["ring"] for i in ids])
        o = {"h": h, "cmag": np.abs(cb), "ring": ring, "sig": np.maximum(sig * math.sqrt(2), args.sig_floor),
             "dz07": C[pa] / cb - 1, "dz08": C[pb] / cb - 1}
        ok = np.abs(cb) >= args.min_chroma
        o = subset(o, ok)
        F = sm.Fitter(o, Z, reg=args.reg)
        best = None
        for kern in ("linear", "hard"):
            r = F.fit(sm.Spec(kern, blur="const"), F.init_from_data(kern), max_nfev=150)
            best = r["chi2"] if best is None else min(best, r["chi2"])
        return best
    chi_a = fit_chi2(probes[0], probes[1])
    chi_b = fit_chi2(probes[1], probes[0])
    p07, p08 = (probes[0], probes[1]) if chi_a <= chi_b else (probes[1], probes[0])
    if (inv_a <= inv_b) != (chi_a <= chi_b):
        notes.append("sector-order inversion count disagrees with the model-fit identity; fit used")
    if (p07, p08) != (probes[0], probes[1]):
        notes.append("model fit says the later probe frame is 07; shooting order says the earlier one")
    return {"base": base, "p07": p07, "p08": p08, "pair_median_dz": D.tolist(), "notes": notes,
            "inversions": {"first_is_07": inv_a, "first_is_08": inv_b, "n_items": [na, nb]},
            "fit_chi2": {"first_is_07": chi_a, "first_is_08": chi_b,
                         "ratio_wrong_over_right": max(chi_a, chi_b) / max(min(chi_a, chi_b), 1e-9)},
            "C": C, "ids": ids}


def build_obs(group, roles, lay, args):
    ids = roles["ids"]
    C = roles["C"]
    a, b = roles["base"]
    t = [when_seconds(f["meta"], f["seq"]) for f in group]
    if t[b] == t[a]:
        t = [float(f["seq"]) for f in group]
    drift = complex(np.median((C[b] / C[a]).real), np.median((C[b] / C[a]).imag))
    resid = C[b] / (C[a] * drift) - 1
    delta = np.abs(resid) / math.sqrt(2)
    ring = np.array([lay["patches"][lay["index"][i]]["ring"] for i in ids])
    hmid = sm.hue_deg(0.5 * (C[a] + C[b]))
    # noise per frame: hue-neighbour median of delta^2 / ln 2 within a ring (chi2_2 median)
    sig_f = np.zeros(len(ids))
    for r in (1, 2):
        sel = np.where(ring == r)[0]
        hs = hmid[sel]
        for j, k in enumerate(sel):
            d = np.abs(sm.wrap180(hs - hs[j]))
            nb = sel[np.argsort(d)[:args.sig_neighbours]]
            sig_f[k] = math.sqrt(np.median(delta[nb] ** 2) / math.log(2))
    sig_f = np.maximum(sig_f, args.sig_floor)
    flags = {}
    for f in group:
        for p in f["patches"]:
            if p["id"] in ids and p.get("flags"):
                flags.setdefault(p["id"], set()).update(p["flags"])
    obs = {"labels": np.array(ids), "ring": ring, "h": hmid, "cmag": np.abs(0.5 * (C[a] + C[b])),
           "sig": None, "dz07": None, "dz08": None}
    sigs = []
    for key in ("07", "08"):
        k = roles["p" + key]
        frac = min(max((t[k] - t[a]) / (t[b] - t[a]), 0.0), 1.0) if t[b] != t[a] else 0.5
        cbase = C[a] + frac * (C[b] - C[a]) if args.base == "interp" else 0.5 * (C[a] + C[b])
        obs["dz" + key] = C[k] / cbase - 1
        sigs.append(sig_f * math.sqrt(1 + frac ** 2 + (1 - frac) ** 2))
    obs["sig"] = np.maximum(sigs[0], sigs[1])
    excl = np.array([bool(flags.get(i)) or abs(c) < args.min_chroma for i, c in zip(ids, 0.5 * (C[a] + C[b]))])
    drift_stats = {"complex_ratio_b_over_a": [drift.real, drift.imag], "scale": abs(drift),
                   "rotation_deg": math.degrees(np.angle(drift)),
                   "per_patch_hue_dev_deg_median": float(np.degrees(np.median(np.abs(np.angle(resid + 1))))),
                   "per_patch_hue_dev_deg_max": float(np.degrees(np.max(np.abs(np.angle(resid + 1))))),
                   "per_patch_chroma_dev_median": float(np.median(np.abs(np.abs(resid + 1) - 1))),
                   "sigma_frame_median": float(np.median(sig_f)), "sigma_z_median": float(np.median(obs["sig"])),
                   "times_s": t}
    return obs, excl, {int(i): sorted(v) for i, v in flags.items()}, drift_stats


def subset(obs, keep):
    return {k: (v[keep] if isinstance(v, np.ndarray) and len(v) == len(keep) else v) for k, v in obs.items()}


# ----------------------------------------------------------------- estimation suite

FAMILIES = (("linear", "zero"), ("linear", "const"), ("linear", "chroma"), ("hard", "const"), ("hard", "chroma"))


def convert_init(m, to_kernel, from_kernel):
    """Initial values for another kernel family from a fitted solution."""
    nodes = np.asarray(m["nodes"], float)
    if to_kernel != from_kernel:
        centres = sm.sector_centres(nodes, from_kernel)
        nodes = sm.fill_nodes(centres, to_kernel)
    return {"nodes": nodes, "gain": float(np.median(m["gain"])), "k": m["k"], "blur": max(m["blur"], 0.3),
            "kappa": max(m["kappa"], 5.0), "gain_sector": m["gain"]}


def run_suite(obs, Z, args, label=""):
    """Fit kernel families (cross-seeded), select, test variants, bootstrap the chosen model."""
    F = sm.Fitter(obs, Z, reg=args.reg)
    raw = {}
    specs = {f"{k}+blur={b}": sm.Spec(k, blur=b, k=args.k) for k, b in FAMILIES}

    def keep(name, r):
        if name not in raw or r["chi2"] < raw[name]["chi2"] - 1e-6:
            raw[name] = r
    for name, spec in specs.items():
        keep(name, F.fit(spec, F.init_from_data(spec.kernel)))
    # continuation in blur for the unblurred linear kernel, from the blurred solution
    for _ in range(2):
        for name, spec in specs.items():
            # seed from the best other solution of each kernel type
            seeds = {}
            for oname, other in raw.items():
                kk = other["spec"].kernel
                if oname != name and (kk not in seeds or other["chi2"] < seeds[kk]["chi2"]):
                    seeds[kk] = other
            for other in seeds.values():
                ini = convert_init(other["m"], spec.kernel, other["spec"].kernel)
                if spec.blur == "zero" and other["spec"].kernel == "linear":
                    cur = ini
                    for sblur in (1.0, 0.4):
                        rr = F.fit(spec.replace(blur=sblur), cur)
                        cur = convert_init(rr["m"], "linear", "linear")
                    ini = cur
                keep(name, F.fit(spec, ini))
    hstart = min((r for r in raw.values()), key=lambda r: r["chi2"] if r["spec"].kernel == "hard" else 1e18)
    rp = F.fit_pure_hard(sm.Spec("hard", blur=0.1, k=args.k), convert_init(hstart["m"], "hard", "hard"))
    rp2 = F.fit_pure_hard(sm.Spec("hard", blur=0.1, k=args.k),
                          convert_init(min(raw.values(), key=lambda r: r["chi2"])["m"], "hard",
                                       min(raw.values(), key=lambda r: r["chi2"])["spec"].kernel))
    rp = rp if rp["chi2"] <= rp2["chi2"] else rp2
    raw[rp["spec"].name] = rp
    fits = [sm.summarize_fit(F, r) for r in raw.values()]
    for f, (name, r) in zip(fits, raw.items()):
        f["name"] = name
    best, s2 = sm.select_models(fits)
    chosen = raw[best["name"]]
    # variants on the chosen family
    variants = []
    base_spec = chosen["spec"]
    vinit = {"nodes": chosen["m"]["nodes"], "gain": float(np.median(chosen["m"]["gain"])), "k": chosen["m"]["k"],
             "blur": max(chosen["m"]["blur"], 0.05), "kappa": max(chosen["m"]["kappa"], 1.0)}
    tests = {}
    for name, kw in (("gain_per_sector", {"gain": "sector"}), ("ring_gain", {"ring_gain": True}),
                     ("ring_shift", {"ring_shift": True}), ("geometric_mix", {"mix": "geometric"}),
                     ("k_fixed_1", {"k": 1.0})):
        if name.startswith("ring") and len(np.unique(obs["ring"])) < 2:
            continue
        sp = base_spec.replace(**kw)
        sp.name = base_spec.name + "+" + name
        r = F.fit(sp, vinit)
        sfit = sm.summarize_fit(F, r)
        d_chi = (best["chi2"] - sfit["chi2"]) / s2
        d_par = sfit["n_par"] - best["n_par"]
        sfit["delta_chi2_scaled_vs_chosen"] = d_chi
        sfit["delta_bic_scaled_vs_chosen"] = -d_chi + d_par * math.log(max(best["n_data"], 2))
        variants.append(sfit)
        raw[sp.name] = r
        tests[name] = sfit
    adopt = [v for v in variants if v["delta_bic_scaled_vs_chosen"] < -10 and not v["name"].endswith("k_fixed_1")
             and not v["name"].endswith("geometric_mix")]
    final = chosen
    final_sum = best
    if adopt:
        pick = min(adopt, key=lambda v: v["delta_bic_scaled_vs_chosen"])
        final = raw[pick["name"]]
        final_sum = pick
    boot = sm.bootstrap(F, final, B=args.bootstrap) if args.bootstrap > 0 else None
    jac = sm.jac_node_cov(F, final) if final.get("jac") is not None else None
    brackets = sm.bracket_intervals(obs["h"], final["m"]["nodes"])
    pred, W = F.predict(final["spec"], final["m"])
    return {"label": label, "fits": fits, "best_family": best["name"], "s2": s2, "variants": variants,
            "final": final_sum, "final_spec": final["spec"].as_dict(), "bootstrap": boot, "jacobian": jac,
            "brackets": brackets, "_final": final, "_F": F, "_pred": pred, "_W": W, "tests": tests}


def node_intervals(res):
    """90% node intervals: union of the patch bootstrap and the Jacobian (+-1.645 sd).
    For pure hard boundaries the Jacobian is not informative; the sample bracket is used."""
    f = res["final"]
    nodes = np.array(f["nodes_unwrapped"])
    boot, jac = res["bootstrap"], res["jacobian"]
    pure_hard = f["spec"]["kernel"] == "hard" and isinstance(f["spec"]["blur"], float)
    out = []
    for s in range(sm.N):
        lo = hi = nodes[s]
        if boot:
            blo, bhi = boot["node_ci90"][s]
            off = 360 * round((nodes[s] - (blo + bhi) / 2) / 360)
            lo, hi = min(lo, blo + off), max(hi, bhi + off)
        if jac and not pure_hard and np.isfinite(jac["node_sd"][s]):
            lo, hi = min(lo, nodes[s] - 1.645 * jac["node_sd"][s]), max(hi, nodes[s] + 1.645 * jac["node_sd"][s])
        if pure_hard:
            br = res["brackets"][s]
            lo = min(lo, br[0]) if br[0] is not None else lo
            hi = max(hi, br[1]) if br[1] is not None else hi
        out.append([float(lo), float(hi)])
    return out


def effective_blur(f, cm):
    if f["blur_mode"] == "chroma":
        return math.hypot(f["blur_deg"], f["blur_kappa"] / cm)
    return f["blur_deg"]


def kernel_verdict(res):
    f = res["final"]
    blur = effective_blur(f, float(np.median(res["_F"].obs["cmag"])))
    tail = f", chroma-scaled {f['blur_kappa']:.0f}/|c| deg" if f["blur_mode"] == "chroma" else ""
    if f["spec"]["kernel"] == "hard":
        return f"hard boundaries; ROI-mean blur {blur:.2f} deg at median |c|{tail}"
    if f["spec"]["blur"] == "zero" or blur < 0.5:
        return "linear interpolation between nodes (no measurable blur)"
    return f"linear interpolation between nodes; ROI-mean blur {blur:.2f} deg at median |c|{tail}"


def iso_compare(results):
    keys = sorted(k for k in results if k is not None)
    if len(keys) < 2:
        return {"available": False}
    lo, hi = results[keys[0]], results[keys[-1]]
    nl, nh = np.array(lo["final"]["nodes_unwrapped"]), np.array(hi["final"]["nodes_unwrapped"])
    nh = nh + 360 * np.round((nl[0] - nh[0]) / 360)
    d = nh - nl
    sd = None
    if lo["bootstrap"] and hi["bootstrap"]:
        sd = np.sqrt(np.array(lo["bootstrap"]["node_sd"]) ** 2 + np.array(hi["bootstrap"]["node_sd"]) ** 2)

    def eff_blur(r):
        return effective_blur(r["final"], float(np.median(r["_F"].obs["cmag"])))
    bl, bh = eff_blur(lo), eff_blur(hi)
    fam = {k: {f["name"]: f["delta_bic_scaled"] for f in results[k]["fits"]} for k in keys}
    hb = {k: next(f["blur_deg"] for f in results[k]["fits"] if f["name"] == "hard+blur=const") for k in keys}
    lb = {k: next(f["blur_deg"] for f in results[k]["fits"] if f["name"] == "linear+blur=const") for k in keys}
    kern_lo, kern_hi = lo["final"]["spec"]["kernel"], hi["final"]["spec"]["kernel"]
    # shape: plateau (hard) vs tent (linear), decided by the fit at each ISO
    if kern_lo == kern_hi:
        shape = "hard boundaries" if kern_lo == "hard" else "linear interpolation"
    else:
        shape = f"shape differs (ISO {keys[0]}: {kern_lo}, ISO {keys[-1]}: {kern_hi}); trust the low-noise ISO {keys[0]}"
    # blur: grows with ISO -> per-pixel noise before the lookup; constant -> intrinsic width
    if max(bl, bh) < 0.5:
        origin = "no measurable blur at either ISO"
    elif bh > 1.5 * bl + 0.3:
        origin = "blur grows with ISO: per-pixel noise reaches the lookup (not part of the table)"
    elif abs(bh - bl) <= 0.35 * max(bl, bh):
        origin = "blur is the same at both ISOs: intrinsic width of the kernel"
    else:
        origin = "blur changes with ISO but less than noise would; partly intrinsic"
    verdict = f"{shape}; ROI blur {bl:.2f} -> {bh:.2f} deg ({origin})"
    return {"available": True, "isos": keys, "node_diff_deg": d.tolist(),
            "node_diff_rms": float(np.sqrt(np.mean(d ** 2))), "node_diff_max": float(np.max(np.abs(d))),
            "node_diff_over_sd": (np.abs(d) / sd).tolist() if sd is not None else None,
            "effective_blur_deg": {str(keys[0]): bl, str(keys[-1]): bh},
            "hard_const_blur_deg": {str(k): v for k, v in hb.items()},
            "linear_const_blur_deg": {str(k): v for k, v in lb.items()},
            "gain": {str(keys[0]): lo["final"]["gain"], str(keys[-1]): hi["final"]["gain"]},
            "kernel": {str(keys[0]): kern_lo, str(keys[-1]): kern_hi}, "delta_bic_scaled": fam,
            "verdict": verdict}


def model_json(res, status, provenance, extra=None):
    f = res["final"]
    boot = res["bootstrap"] or {}
    nodes = np.array(f["nodes_unwrapped"])
    kern = f["spec"]["kernel"]
    gain_ci = boot.get("gain_ci90")
    model = {
        "schema": sm.SCHEMA, "status": status,
        "hue_coordinate": {"plane": "JPEG Cb/Cr of sRGB codes, BT.601 full range", "angle": "atan2(Cr, Cb), deg, CCW",
                           "of": "04 Std output (stock colour row) of the same scene, WB-aligned"},
        "kernel": {"type": kern, "blur_deg": f["blur_deg"], "blur_mode": f["blur_mode"], "blur_kappa": f["blur_kappa"],
                   "mix": f["spec"]["mix"],
                   "node_meaning": "peak of sector s (w_s = 1)" if kern == "linear" else "start boundary of sector s"},
        "nodes_deg": (nodes % 360).tolist(), "nodes_unwrapped_deg": nodes.tolist(),
        "sector_centres_deg": sm.sector_centres(nodes, kern).tolist(),
        "node_ci90_deg": node_intervals(res), "node_ci90_bootstrap_deg": boot.get("node_ci90"),
        "node_sd_deg": boot.get("node_sd") or (res["jacobian"] or {}).get("node_sd"),
        "node_sd_jacobian_deg": (res["jacobian"] or {}).get("node_sd"),
        "node_bracket_samples_deg": res["brackets"],
        "gain": f["gain"], "gain_ci90": gain_ci, "gain_sd": boot.get("gain_sd"),
        "gain_per_sector": f["gain_per_sector"],
        "gain_ring_ratio": f["ring_gain_ratio"], "ring2_node_shift_deg": f["ring2_shift_deg"],
        "k_coupling": f["k"], "k_ci90": boot.get("k_ci90"),
        "full_gain_test": None if not gain_ci else {
            "gain": f["gain"], "ci90": gain_ci, "w_equals_1_inside_ci": gain_ci[0] <= 1.0 <= gain_ci[1]},
        "kernel_verdict": kernel_verdict(res),
        "model_selection": {"fits": res["fits"], "chosen_family": res["best_family"], "reduced_chi2_ref": res["s2"],
                            "variants": res["variants"], "final": f["name"]},
        "bootstrap": boot, "jacobian": res["jacobian"], "provenance": provenance,
    }
    if extra:
        model.update(extra)
    return model


# ----------------------------------------------------------------- plots

def plot_weights(res, path, title, truth=None):
    F, fin = res["_F"], res["_final"]
    o, m, spec = F.obs, fin["m"], fin["spec"]
    vec = sm.probe_vectors(F.Z, m["k"])
    hg = np.linspace(0, 360, 1441)
    cm = np.full(len(hg), float(np.median(o["cmag"])))
    grid_obs = {"h": hg, "cmag": cm, "ring": np.ones(len(hg), int)}
    sig = np.broadcast_to(np.asarray(F.sigma_of(spec, m, grid_obs), float), (len(hg),))
    Wg = sm.weights(hg, m["nodes"], spec.kernel, sig) * m["gain"][None, :]
    panels = []
    for key, col in (("07", pp.SERIES[0]), ("08", pp.SERIES[1])):
        P = pp.Plot(1100, 330, (0, 360), (-0.15, 1.25), f"{title}, probe {key}: weight vs CbCr hue",
                    "CbCr hue of the 04 colour (deg)", "w")
        P.axes(range(0, 361, 30), [0, 0.25, 0.5, 0.75, 1.0])
        P.hline(1.0, pp.GRID, 1)
        for s in range(sm.N):
            P.vline(m["nodes"][s] % 360, pp.NEUTRAL if s % 2 else pp.INK2, 1, top=1.22, bottom=1.12)
            P.text(m["nodes"][s] % 360, 1.19, str(s), pp.INK2, "mm")
        secs = sm.PROBE_SECTORS[key]
        # model curve
        P.line(hg, Wg[:, list(secs)].sum(1), col, 2, break_gap=1.0)
        if truth is not None:
            tw = sm.weights(hg, truth["nodes"], truth["kernel"], truth.get("blur_plot", 1e-4)) * truth["gain"]
            P.line(hg, tw[:, list(secs)].sum(1), pp.NEUTRAL, 1, break_gap=1.0)
        # observed projected weight on the active probed sector
        Wobs = sm.weights(o["h"], m["nodes"], spec.kernel, np.broadcast_to(np.asarray(F.sigma_of(spec, m, o), float), (len(o["h"]),)))
        act = np.array(secs)[np.argmax(Wobs[:, list(secs)], axis=1)]
        U = vec[key][act] - 1
        dz = (o["dz" + key] + 1) / (1 + m["eps"][key]) - 1
        wproj = (dz * U.conj()).real / np.abs(U) ** 2
        for r, shape in ((1, "o"), (2, "s")):
            sel = o["ring"] == r
            P.points(o["h"][sel], wproj[sel], col, shape, 7)
        if "_excluded" in res:
            ex = res["_excluded"]
            P.points(ex["h"], ex["w" + key], col, "x", 7)
        items = [("model", col, "-"), ("ring 1 L*45", col, "o"), ("ring 2 L*65", col, "s")]
        if "_excluded" in res and len(res["_excluded"]["h"]):
            items.append(("excluded", col, "x"))
        if truth is not None:
            items.append(("truth", pp.NEUTRAL, "-"))
        P.legend_top(items)
        panels.append(P.im)
    pp.stack(panels, path)


def plot_iso(cmp, results, path):
    keys = cmp["isos"]
    d = np.array(cmp["node_diff_deg"])
    lim = max(3.0, float(np.max(np.abs(d))) * 1.3)
    P = pp.Plot(900, 320, (-0.5, 23.5), (-lim, lim), f"Node position ISO {keys[-1]} minus ISO {keys[0]}",
                "sector / node index", "deg")
    P.axes(range(0, 24, 2), [round(v, 1) for v in np.linspace(-lim, lim, 5)])
    P.hline(0, pp.INK2, 1)
    lo, hi = results[keys[0]]["bootstrap"], results[keys[-1]]["bootstrap"]
    if lo and hi:
        sd = np.sqrt(np.array(lo["node_sd"]) ** 2 + np.array(hi["node_sd"]) ** 2)
        for s in range(sm.N):
            a, b = d[s] - 1.645 * sd[s], d[s] + 1.645 * sd[s]
            P.d.line([(P.x(s), P.y(max(a, -lim))), (P.x(s), P.y(min(b, lim)))], fill=pp.SERIES[0], width=2)
    P.points(range(sm.N), d, pp.SERIES[0], "o", 8)
    P.save(path)


# ----------------------------------------------------------------- chart (spot metering) frame

def chart_frame(jpg, dng, meta, args):
    A = a2e()
    S = s2d()
    rgb = np.asarray(Image.open(jpg).convert("RGB")).astype(np.float64)
    tiff = S.Tiff(dng.read_bytes())
    crop, black, white, neutral, stats = S.decode_raw(tiff)
    ox, oy = stats["crop_origin_xy"]
    Y, (sx, sy) = A.raw_luminance(crop, black, white, neutral, (ox, oy))
    half_c, geo = A.detect_lattice(Y)
    centres = half_c * 2 + np.array([sx + 0.5, sy + 0.5])
    grid = centres.reshape(4, 6, 2)
    pitch = min(float(np.median(np.diff(grid[:, :, 0], axis=1))), float(np.median(np.diff(grid[:, :, 1], axis=0))))
    half = int(round(0.16 * pitch))
    rows = []
    for (cx, cy) in centres:
        x0, x1, y0, y1 = int(round(cx - half)), int(round(cx + half)), int(round(cy - half)), int(round(cy + half))
        dn = np.array(S.cfa_means(crop, y0, y1, x0, x1, oy, ox))
        cam = (dn - black) / (white - black)
        mean = rgb[y0:y1, x0:x1].reshape(-1, 3).mean(0)
        rows.append({"u": float((cam / neutral) @ np.array([0.25, 0.5, 0.25])), "rgb": mean.tolist(),
                     "y709": float(mean @ np.array([0.2126, 0.7152, 0.0722])), "xy": [float(cx), float(cy)],
                     "cam_wb": (cam / neutral).tolist()})
    # Orientation: the grey row runs white..black with descending raw u, either as the last
    # row (upright, 2e) or the first row reversed (rotated 180 deg, 2d).
    up = [rows[18 + k]["u"] for k in range(6)]
    rot = [rows[5 - k]["u"] for k in range(6)]
    if all(up[i] > up[i + 1] for i in range(5)):
        orient, d4 = "upright", rows[21]
    elif all(rot[i] > rot[i + 1] for i in range(5)):
        orient, d4 = "rotated180", rows[2]
    else:
        raise SystemExit(f"{jpg.name}: no white..black grey row found in raw u: upright {up}, rotated {rot}")
    xs, ys = stock_curve()
    t = meta.get("t")
    checks = {"ExposureProgram_is_3": meta.get("program") == 3,
              "shutter_not_1_80": t is not None and abs(t - 1 / 80) > 1e-6,
              "MeteringMode_is_spot_3": meta.get("metering") == 3, "bias_is_0": meta.get("bias_ev") == 0,
              "iso_500": meta.get("iso") == 500, "f_2_5": meta.get("f") is not None and abs(meta["f"] - 2.5) < 0.05,
              "wb_fixed": (meta.get("wb_exif") == 1) or bool(meta.get("wb_record_0x26"))}
    u = d4["u"]
    out = {"file": jpg.name, "orientation": orient, "lattice": geo, "pitch_px": pitch, "roi_half_px": half,
           "meta": {k: meta.get(k) for k in ("program", "metering", "bias_ev", "t", "f", "iso", "wb_exif",
                                              "wb_record_0x26", "when", "bv", "asn")},
           "checks": checks, "valid_metering_anchor": all(checks[k] for k in ("ExposureProgram_is_3", "shutter_not_1_80",
                                                                               "MeteringMode_is_spot_3", "bias_is_0")),
           "D4": {"u": u, "jpeg_y709": d4["y709"], "jpeg_rgb": d4["rgb"],
                  "row5_pred_at_u": float(np.interp(u * 4095, xs, ys))},
           "u_m_metered_grey": u, "u_m_ev_vs_assumed": math.log2(u / U_M_ASSUMED),
           "u_18_percent_equivalent": u * 0.18 / D4_PUBLISHED_Y,
           "u_18_ev_vs_assumed": math.log2(u * 0.18 / D4_PUBLISHED_Y / U_M_ASSUMED),
           "note": "Spot metering puts D4 (published Y 0.191) at the meter's mid grey; u_18 rescales to 18%."}
    if not out["valid_metering_anchor"]:
        out["warning"] = "not an A-mode spot reading at EC 0 (or shutter is still 1/80): do not use as u_m"
    return out


# ----------------------------------------------------------------- real-data driver

def analyse_dir(d, args):
    lay = load_layout()
    files = sorted([p for p in d.iterdir() if p.suffix.upper() in (".JPG", ".JPEG")])
    sidecar = None
    if (d / "frames.json").exists():
        sidecar = json.loads((d / "frames.json").read_text())
    hashes_before = {p.name: sha256(p) for p in sorted(d.iterdir()) if p.suffix.upper() in (".JPG", ".JPEG", ".DNG")}
    frames, others = [], []
    for seq, jpg in enumerate(files):
        dng = next((jpg.with_suffix(s) for s in (".DNG", ".dng") if jpg.with_suffix(s).exists()), None)
        meta = read_meta(jpg, dng, sidecar)
        if args.chart and jpg.name == args.chart:
            others.append((jpg, dng, meta))
            continue
        t0 = time.time()
        rec = load_frame(jpg, dng, meta, lay, args)
        rec["seq"] = seq
        rec["load_s"] = round(time.time() - t0, 2)
        if rec["ring"]:
            frames.append(rec)
        else:
            others.append((jpg, dng, meta))
        print(f"  {jpg.name}: {'ring' if rec['ring'] else 'not ring (' + rec.get('why_not_ring', '') + ')'}"
              f" iso {meta.get('iso')} {rec['load_s']} s", flush=True)
    if not frames:
        raise SystemExit("no hue-ring frames found (for the metering frame alone use --chart-only)")
    Zinfo = design_Z(frames[0]["meta"].get("display"))
    Z, zsrc = Zinfo
    groups = group_frames(frames)
    results, group_out, roles_by_iso = {}, {}, {}
    for iso, grp in sorted(groups.items(), key=lambda kv: (kv[0] is None, kv[0])):
        print(f"== ISO {iso}: {[f['file'] for f in grp]}", flush=True)
        roles = identify(grp, lay, Z, args)
        roles_by_iso[iso] = {grp[roles["base"][0]]["file"]: "04a", grp[roles["base"][1]]["file"]: "04b",
                             grp[roles["p07"]]["file"]: "07", grp[roles["p08"]]["file"]: "08"}
        obs_all, excl, flags, drift = build_obs(grp, roles, lay, args)
        obs = subset(obs_all, ~excl)
        res = run_suite(obs, Z, args, label=f"ISO {iso}")
        res["_excluded"] = excluded_points(obs_all, excl, res)
        results[iso] = res
        group_out[str(iso)] = {
            "frames": {"04a": grp[roles["base"][0]]["file"], "04b": grp[roles["base"][1]]["file"],
                       "07": grp[roles["p07"]]["file"], "08": grp[roles["p08"]]["file"]},
            "identify": {k: v for k, v in roles.items() if k not in ("C", "ids")}, "drift_04_pair": drift,
            "excluded": {int(i): flags.get(int(i), ["low chroma"]) for i in obs_all["labels"][excl]},
            "n_obs": int((~excl).sum()), "fit": {k: v for k, v in res.items() if not k.startswith("_")},
            "kernel_verdict": kernel_verdict(res),
            "wb_gains": {f["file"]: f["wb_gain"] for f in grp},
            "geometry": {f["file"]: {**f["geometry"], "gap_check": f["gap_check"]} for f in grp},
            "tone_check": tone_check(grp[roles["base"][0]], lay),
        }
        plot_weights(res, LOCAL / "plots" / f"weights_iso{iso}.png", f"ISO {iso}")
    cmp = iso_compare(results)
    if cmp.get("available"):
        plot_iso(cmp, results, LOCAL / "plots" / "iso_node_diff.png")
    chart = None
    for jpg, dng, meta in others:
        if dng is None:
            continue
        try:
            chart = chart_frame(jpg, dng, meta, args)
            break
        except SystemExit as ex:
            print(f"  {jpg.name}: not a chart frame ({ex})")
        except Exception as ex:  # noqa: BLE001
            print(f"  {jpg.name}: chart analysis failed ({ex})")
    primary_iso = min(k for k in results if k is not None) if any(k is not None for k in results) else None
    prim = results[primary_iso]
    hashes_after = {p.name: sha256(p) for p in sorted(d.iterdir()) if p.suffix.upper() in (".JPG", ".JPEG", ".DNG")}
    prov = {"input_dir": str(d), "design_Z": zsrc, "captures_sha256_before": hashes_before,
            "captures_unchanged": hashes_before == hashes_after, "args": vars(args),
            "primary_group_iso": primary_iso}
    model = model_json(prim, f"measured from hue ring (primary ISO {primary_iso})", prov, {
        "luminance_test": luminance_test(prim), "iso_comparison": cmp, "groups": group_out, "metering": chart,
        "per_iso_models": {str(k): model_json(v, f"ISO {k}", {}) for k, v in results.items() if k != primary_iso},
    })
    out = Path(args.out) if args.out else LOCAL / "ring_model.json"
    sm.save_model(out, model)
    write_patch_table(groups, roles_by_iso, lay, LOCAL / "ring_patches.json")
    print_summary(model)
    print(f"wrote {out}")
    return model


def excluded_points(obs_all, excl, res):
    if not excl.any():
        return {"h": [], "w07": [], "w08": []}
    o = subset(obs_all, excl)
    m = res["_final"]["m"]
    vec = sm.probe_vectors(res["_F"].Z, m["k"])
    W = sm.weights(o["h"], m["nodes"], res["_final"]["spec"].kernel, 1e-4)
    out = {"h": o["h"]}
    for key in ("07", "08"):
        secs = list(sm.PROBE_SECTORS[key])
        act = np.array(secs)[np.argmax(W[:, secs], axis=1)]
        U = vec[key][act] - 1
        out["w" + key] = (o["dz" + key] * U.conj()).real / np.abs(U) ** 2
    return out


def luminance_test(res):
    t = res["tests"]
    out = {}
    for name in ("ring_gain", "ring_shift"):
        v = t.get(name)
        if v:
            out[name] = {"delta_chi2_scaled": v["delta_chi2_scaled_vs_chosen"], "delta_bic_scaled": v["delta_bic_scaled_vs_chosen"],
                         "ring_gain_ratio": v["ring_gain_ratio"], "ring2_shift_deg": v["ring2_shift_deg"],
                         "significant": v["delta_bic_scaled_vs_chosen"] < -10}
    return out


def tone_check(frame, lay):
    try:
        xs, ys = stock_curve()
    except Exception:  # noqa: BLE001
        return None
    rows = []
    for p in frame["patches"]:
        if p["id"] in lay["grey_ids"] and "u" in p:
            rows.append({"id": p["id"], "u": p["u"], "jpeg_y709": float(np.dot(p["rgb"], [0.2126, 0.7152, 0.0722])),
                         "row5_pred": float(np.interp(p["u"] * 4095, xs, ys))})
    return rows or None


def write_patch_table(groups, roles_by_iso, lay, path):
    out = {"note": "Per-frame ROI means (aligned to the first 04 of each ISO group) for color_table_fit.",
           "groups": {}}
    for iso, grp in groups.items():
        g = {}
        for f in grp:
            g[f["file"]] = {"role": roles_by_iso.get(iso, {}).get(f["file"]),
                            "meta": {k: f["meta"].get(k) for k in ("iso", "t", "when", "program")},
                            "patches": [{"id": p["id"], "rgb_aligned": f.get("_aligned", {}).get(p["id"], np.array(p["rgb"])).tolist(),
                                         "u": p.get("u"), "flags": p.get("flags")} for p in f["patches"] if p.get("ok")]}
        out["groups"][str(iso)] = g
    path.write_text(json.dumps(sm.jsonable(out), indent=1) + "\n")


def print_summary(model):
    print(f"\n== {model['status']}")
    print(f"kernel: {model['kernel_verdict']}; gain {model['gain']:.3f} CI {model.get('gain_ci90')}; "
          f"k {model['k_coupling']:.3f} CI {model.get('k_ci90')}")
    ci = model.get("node_ci90_deg") or [[None, None]] * 24
    for s in range(sm.N):
        lo, hi = ci[s]
        print(f"  node {s:2d}: {model['nodes_deg'][s]:7.2f} deg  CI90 "
              f"{'' if lo is None else f'[{lo % 360:.2f}, {hi % 360:.2f}]'}")
    if model.get("iso_comparison", {}).get("available"):
        c = model["iso_comparison"]
        print(f"ISO: {c['verdict']}; node diff rms {c['node_diff_rms']:.2f} max {c['node_diff_max']:.2f}; "
              f"effective blur {c['effective_blur_deg']}")
    if model.get("luminance_test"):
        print("luminance:", model["luminance_test"])
    if model.get("metering"):
        mt = model["metering"]
        print(f"metering: D4 u {mt['D4']['u']:.4f} ({mt['u_m_ev_vs_assumed']:+.2f} EV vs 320/4095), "
              f"checks {mt['checks']}")


# ----------------------------------------------------------------- stage 2e partial model

def stage2e_obs(path):
    m = json.loads(path.read_text())
    pr = m["probe"]
    Z = {int(s): v["scale"] * complex(math.cos(math.radians(v["angle_deg"])), math.sin(math.radians(v["angle_deg"])))
         for s, v in pr["design"].items()}
    rows = []
    for l, rec in pr["patches"].items():
        dz = {k: rec[k]["dz_abs"] * complex(math.cos(math.radians(rec[k]["dir_deg"])), math.sin(math.radians(rec[k]["dir_deg"])))
              for k in ("07", "08")}
        sig = math.sqrt(2) * rec["sig"] * (2.0 if rec["clipped"] else 1.0)
        rows.append((l, rec["h_cbcr"], rec["cc_base"], sig, dz["07"], dz["08"], rec["clipped"]))
    obs = {"labels": np.array([r[0] for r in rows]), "h": np.array([r[1] for r in rows]),
           "cmag": np.array([r[2] for r in rows]), "sig": np.array([r[3] for r in rows]),
           "dz07": np.array([r[4] for r in rows]), "dz08": np.array([r[5] for r in rows]),
           "ring": np.ones(len(rows), int), "clipped": np.array([r[6] for r in rows])}
    return obs, Z, m


def from_stage2e(args):
    obs, Z, m = stage2e_obs(STAGE2E)
    print(f"stage 2e chart: {len(obs['h'])} patches, clipped {list(obs['labels'][obs['clipped']])} (sigma x2)")
    res = run_suite(obs, Z, args, label="stage2e chart")
    prov = {"source": str(STAGE2E.relative_to(ROOT)), "sha256": sha256(STAGE2E),
            "design_Z": "stage 2e probe.design (scale, angle with five-colour modifier)",
            "n_patches": int(len(obs["h"])), "args": vars(args)}
    model = model_json(res, "PARTIAL: stage 2e ColorChecker probes only (18 patches); replace with ring_model.json",
                       prov, {"observations": {"labels": obs["labels"].tolist(), "h_cbcr": obs["h"].tolist(),
                                               "clipped": obs["clipped"].tolist()}})
    out = Path(args.out) if args.out else LOCAL / "chart2e_model.json"
    sm.save_model(out, model)
    plot_weights(res, LOCAL / "plots" / "weights_stage2e_chart.png", "stage 2e chart (partial)")
    print_summary(model)
    print(f"wrote {out}")
    return model


# ----------------------------------------------------------------- self-test

TRUTH_NODES = np.array([30, 57, 76, 92, 103, 109, 120, 128, 136, 143, 156, 170, 184, 207, 232, 257, 281, 295,
                        309, 320, 331, 339, 347, 356], float)


def ring_design_cbcr(lay):
    rows = [p for p in lay["patches"] if p["ring"] in (1, 2)]
    rgb = np.array([p["srgb8"] for p in rows], float)
    ycc = sm.ycbcr(rgb)
    return rows, ycc


def synth_obs(lay, truth, iso_noise, rng, Z):
    """Estimator-level simulation: 04a, 07, 08, 04b ROI means with drift and noise."""
    rows, ycc = ring_design_cbcr(lay)
    c0 = (ycc[:, 1] + 1j * ycc[:, 2]) * 0.93 * np.exp(1j * math.radians(2.0))  # camera-ish chroma/hue offset
    P = len(c0)
    ring = np.array([p["ring"] for p in rows])
    h = sm.hue_deg(c0)
    spec = sm.Spec(truth["kernel"], blur=truth["blur_mode"], mix=truth.get("mix", "linear"),
                   ring_gain=truth.get("ring_gain_ratio", 1.0) != 1.0)
    m = {"nodes": truth["nodes"], "gain": np.full(sm.N, truth["gain"]), "blur": truth["blur"],
         "kappa": truth.get("kappa", 0.0) * iso_noise["kappa_scale"], "k": truth["k"],
         "eps": {"07": 0j, "08": 0j}, "ring_gain_ratio": truth.get("ring_gain_ratio", 1.0), "ring2_shift": 0.0}
    F = sm.Fitter({"h": h, "cmag": np.abs(c0), "ring": ring, "sig": np.ones(P)}, Z)
    pred, _ = F.predict(spec, m)
    drift = iso_noise["drift"]
    times = np.array([0.0, 1.0, 2.0, 3.0])

    def noisy(c, t):
        c = c * (1 + drift * t / 3)
        n = iso_noise["abs"] + iso_noise["rel"] * np.abs(c)
        return c + n / math.sqrt(2) * (rng.normal(size=P) + 1j * rng.normal(size=P))
    ca, c7, c8, cb = noisy(c0, 0), noisy(c0 * (1 + pred["07"]), 1), noisy(c0 * (1 + pred["08"]), 2), noisy(c0, 3)
    return rows, ring, (ca, c7, c8, cb), times


def obs_from_sim(rows, ring, frames, times, args):
    ca, c7, c8, cb = frames
    drift = complex(np.median((cb / ca).real), np.median((cb / ca).imag))
    resid = cb / (ca * drift) - 1
    delta = np.abs(resid) / math.sqrt(2)
    hmid = sm.hue_deg(0.5 * (ca + cb))
    sig_f = np.zeros(len(ca))
    for r in (1, 2):
        sel = np.where(ring == r)[0]
        hs = hmid[sel]
        for j, k in enumerate(sel):
            nb = sel[np.argsort(np.abs(sm.wrap180(hs - hs[j])))[:args.sig_neighbours]]
            sig_f[k] = math.sqrt(np.median(delta[nb] ** 2) / math.log(2))
    sig_f = np.maximum(sig_f, args.sig_floor)
    obs = {"labels": np.array([p["id"] for p in rows]), "ring": ring, "h": hmid, "cmag": np.abs(0.5 * (ca + cb))}
    sigs = []
    for key, c, t in (("07", c7, times[1]), ("08", c8, times[2])):
        frac = (t - times[0]) / (times[3] - times[0])
        obs["dz" + key] = c / (ca + frac * (cb - ca)) - 1
        sigs.append(sig_f * math.sqrt(1 + frac ** 2 + (1 - frac) ** 2))
    obs["sig"] = np.maximum(*sigs)
    return obs


def compare_truth(res, truth):
    f = res["final"]
    n_est = np.array(f["nodes_unwrapped"])
    n_true = np.asarray(truth["nodes"], float)
    d = sm.wrap180(n_est - n_true)
    boot = res["bootstrap"]
    comb = node_intervals(res)
    inside_c = []
    for (lo, hi), nt in zip(comb, n_true):
        ntc = nt + 360 * round(((lo + hi) / 2 - nt) / 360)
        inside_c.append(lo - 1e-9 <= ntc <= hi + 1e-9)
    jac = res["jacobian"]
    inside_j = None
    if jac:
        inside_j = [abs(sm.wrap180(ne - nt)) <= 1.645 * sd for ne, nt, sd in zip(n_est, n_true, jac["node_sd"])]
    inside = inside_b = None
    if boot:
        inside, inside_b = [], []
        for (lo, hi), nt, br in zip(boot["node_ci90"], n_true, res["brackets"]):
            ntc = nt + 360 * round(((lo + hi) / 2 - nt) / 360)
            inside.append(lo - 1e-9 <= ntc <= hi + 1e-9)
            blo = min(lo, br[0] if br[0] is not None else lo)
            bhi = max(hi, br[1] if br[1] is not None else hi)
            inside_b.append(blo - 1e-9 <= ntc <= bhi + 1e-9)
    cm = float(np.median(res["_F"].obs["cmag"]))
    eff_true = truth["blur"] if truth["blur_mode"] != "chroma" else math.hypot(truth["blur"], truth["kappa_eff"] / cm)
    eff_est = f["blur_deg"] if f["blur_mode"] != "chroma" else math.hypot(f["blur_deg"], f["blur_kappa"] / cm)
    return {"kernel_true": truth["kernel"], "kernel_est": f["spec"]["kernel"],
            "kernel_correct": truth["kernel"] == f["spec"]["kernel"],
            "node_err_rms_deg": float(np.sqrt(np.mean(d ** 2))), "node_err_max_deg": float(np.max(np.abs(d))),
            "node_err_deg": d.tolist(), "node_ci90_coverage": None if inside is None else float(np.mean(inside)),
            "node_ci90_or_bracket_coverage": None if inside_b is None else float(np.mean(inside_b)),
            "node_jacobian_ci90_coverage": None if inside_j is None else float(np.mean(inside_j)),
            "node_combined_ci90_coverage": float(np.mean(inside_c)),
            "node_combined_ci90_halfwidth_median": float(np.median([(hi - lo) / 2 for lo, hi in comb])),
            "gain_true": truth["gain"], "gain_est": f["gain"], "gain_ci90": boot["gain_ci90"] if boot else None,
            "k_true": truth["k"], "k_est": f["k"], "blur_true_eff_deg": eff_true, "blur_est_eff_deg": eff_est,
            "best_family": res["best_family"], "final": f["name"],
            "family_delta_bic": {x["name"]: round(x["delta_bic_scaled"], 1) for x in res["fits"]},
            "ring_gain_ratio_true": truth.get("ring_gain_ratio", 1.0),
            "ring_gain_test": res["tests"].get("ring_gain", {}).get("delta_bic_scaled_vs_chosen"),
            "ring_gain_ratio_est": res["tests"].get("ring_gain", {}).get("ring_gain_ratio")}


def selftest(args):
    lay = load_layout()
    Z, zsrc = design_Z()
    rng = np.random.default_rng(20261019)
    out_dir = LOCAL / "selftest"
    (out_dir / "plots").mkdir(parents=True, exist_ok=True)
    noise = {100: {"abs": 0.12, "rel": 0.002, "drift": complex(0.004, 0.002), "kappa_scale": 1.0},
             1600: {"abs": 0.45, "rel": 0.004, "drift": complex(0.006, -0.003), "kappa_scale": 4.0}}
    truths = {
        "linear": {"kernel": "linear", "nodes": TRUTH_NODES, "gain": 0.85, "k": 0.97, "blur": 0.0,
                   "blur_mode": "zero"},
        "hard_noise": {"kernel": "hard", "nodes": TRUTH_NODES, "gain": 0.95, "k": 0.97, "blur": 0.05,
                       "blur_mode": "chroma", "kappa": 30.0},
        "linear_noise": {"kernel": "linear", "nodes": TRUTH_NODES, "gain": 0.85, "k": 0.97, "blur": 0.05,
                         "blur_mode": "chroma", "kappa": 30.0},
        "wide": {"kernel": "linear", "nodes": TRUTH_NODES, "gain": 0.9, "k": 0.97, "blur": 4.0, "blur_mode": "const"},
        "linear_ring_gain": {"kernel": "linear", "nodes": TRUTH_NODES, "gain": 0.8, "k": 0.97, "blur": 0.0,
                             "blur_mode": "zero", "ring_gain_ratio": 1.12},
    }
    if args.quick:
        truths = {k: truths[k] for k in ("linear", "hard_noise")}
    if args.image_only:
        truths = {}
    report = {"design_Z": zsrc, "noise": {str(k): {kk: (vv if not isinstance(vv, complex) else [vv.real, vv.imag])
                                                  for kk, vv in v.items()} for k, v in noise.items()},
              "truth_nodes": TRUTH_NODES.tolist(), "estimator": {}}
    for tname, truth in truths.items():
        report["estimator"][tname] = {}
        results = {}
        for iso, nz in noise.items():
            t0 = time.time()
            rows, ring, frames, times = synth_obs(lay, truth, nz, rng, Z)
            obs = obs_from_sim(rows, ring, frames, times, args)
            res = run_suite(obs, Z, args, label=f"{tname} ISO {iso}")
            results[iso] = res
            tr = dict(truth)
            tr["kappa_eff"] = truth.get("kappa", 0.0) * nz["kappa_scale"]
            cmpt = compare_truth(res, tr)
            cmpt["seconds"] = round(time.time() - t0, 1)
            report["estimator"][tname][str(iso)] = cmpt
            plot_weights(res, out_dir / "plots" / f"selftest_{tname}_iso{iso}.png", f"self-test {tname} ISO {iso}",
                         truth={"nodes": truth["nodes"], "kernel": truth["kernel"], "gain": truth["gain"],
                                "blur_plot": max(truth["blur"], 1e-4) if truth["blur_mode"] != "chroma"
                                else tr["kappa_eff"] / float(np.median(obs["cmag"]))})
            print(f"[{tname} ISO {iso}] kernel {cmpt['kernel_est']} ({'ok' if cmpt['kernel_correct'] else 'WRONG'}) "
                  f"node rms {cmpt['node_err_rms_deg']:.2f} max {cmpt['node_err_max_deg']:.2f} deg, "
                  f"CI cover boot {cmpt['node_ci90_coverage']} jac {cmpt['node_jacobian_ci90_coverage']} "
                  f"comb {cmpt['node_combined_ci90_coverage']:.2f} (half {cmpt['node_combined_ci90_halfwidth_median']:.2f}), gain {cmpt['gain_est']:.3f}/{truth['gain']}, "
                  f"k {cmpt['k_est']:.3f}, blur {cmpt['blur_est_eff_deg']:.2f}/{cmpt['blur_true_eff_deg']:.2f}, "
                  f"{cmpt['seconds']} s", flush=True)
        report["estimator"][tname]["iso_comparison"] = {k: v for k, v in iso_compare(results).items()
                                                        if k in ("verdict", "node_diff_rms", "node_diff_max",
                                                                 "effective_blur_deg", "kernel")}
        print(f"[{tname}] ISO verdict: {report['estimator'][tname]['iso_comparison']['verdict']}", flush=True)
    if not args.no_image_test:
        report["image"] = image_selftest(lay, Z, args, rng)
    (out_dir / "selftest.json").write_text(json.dumps(sm.jsonable(report), indent=1) + "\n")
    print(f"wrote {out_dir / 'selftest.json'}")
    return report


# ---- image-level synthetic frames

def render_base(H, shape, blur_px, chunk=256):
    """Warp hue_ring.png into a camera frame by homography (screen->image), then defocus."""
    src = np.asarray(Image.open(RING_PNG).convert("RGB")).astype(np.float32) / 255
    lin = srgb_to_linear(src).astype(np.float32)
    h, w = shape
    Hi = np.linalg.inv(H)
    out = np.empty((h, w, 3), np.float32)
    bg = srgb_to_linear(np.array([0.02, 0.02, 0.02]))
    for y0 in range(0, h, chunk):
        y1 = min(h, y0 + chunk)
        jj, ii = np.meshgrid(np.arange(w) + 0.5, np.arange(y0, y1) + 0.5)
        uv = apply_h(Hi, np.stack([jj, ii], -1))
        for c in range(3):
            out[y0:y1, :, c] = ndimage.map_coordinates(lin[..., c], [uv[..., 1] - 0.5, uv[..., 0] - 0.5], order=1,
                                                       mode="constant", cval=float(bg[c]))
    for c in range(3):
        out[..., c] = ndimage.gaussian_filter(out[..., c], blur_px)
    return out


def camera_frame(base_lin, truth, Zrow, pix_noise, exposure, rng, moire=None, chunk=256):
    """Toy camera: exposure, sRGB encode, per-pixel noise, sector table on CbCr (per pixel), 8-bit."""
    h, w, _ = base_lin.shape
    zlut = None
    if Zrow is not None:
        hg = np.arange(0, 360, 0.01)
        model = {"nodes_deg": truth["nodes"], "kernel": {"type": truth["kernel"], "blur_deg": 0.0, "mix": "linear"},
                 "gain": truth["gain"], "k_coupling": truth["k"]}
        zlut = sm.model_predict_z(model, hg, np.ones(len(hg)), Zrow)
    out = np.empty((h, w, 3), np.uint8)
    for y0 in range(0, h, chunk):
        y1 = min(h, y0 + chunk)
        enc = linear_to_srgb(np.clip(base_lin[y0:y1] * exposure, 0, 1)) * 255
        if moire is not None:
            for (my0, my1, mx0, mx1, amp, period) in moire:
                a, b = max(my0, y0), min(my1, y1)
                if a >= b:
                    continue
                yy, xx = np.mgrid[a:b, mx0:mx1]
                wave = amp * np.sin(2 * math.pi * (xx + 0.3 * yy) / period)
                enc[a - y0:b - y0, mx0:mx1, 0] += wave
                enc[a - y0:b - y0, mx0:mx1, 2] -= wave
        enc = enc + rng.normal(0, pix_noise, enc.shape)
        ycc = sm.ycbcr(enc)
        c = ycc[..., 1] + 1j * ycc[..., 2]
        if zlut is not None:
            idx = np.minimum((sm.hue_deg(c) * 100).astype(np.int64), len(zlut) - 1)
            c = c * zlut[idx]
        out[y0:y1] = np.clip(np.rint(sm.rgb_from_ycc(ycc[..., 0], c.real, c.imag)), 0, 255).astype(np.uint8)
    return out


def image_selftest(lay, Z, args, rng):
    """Synthetic camera frames of hue_ring.png -> the full directory pipeline, for two truths."""
    W, Hh = (2144, 1424) if args.quick else (4288, 2848)
    s = 1.12 * W / 4288
    th = math.radians(1.3)
    A = np.array([[s * math.cos(th), -s * math.sin(th), 0], [s * math.sin(th), s * math.cos(th), 0], [0, 0, 1]])
    A[0, 2] = W / 2 - (A[0, 0] * 1728 + A[0, 1] * 1117)
    A[1, 2] = Hh / 2 - (A[1, 0] * 1728 + A[1, 1] * 1117)
    Pp = np.array([[1, 0, 0], [0, 1, 0], [1.5e-6, -1.0e-6, 1]])
    H = Pp @ A
    H = H / H[2, 2]
    t0 = time.time()
    base = render_base(H, (Hh, W), 1.6 * W / 4288)
    print(f"[image] base render {time.time() - t0:.1f} s", flush=True)
    rows7 = np.ones(sm.N, complex)
    rows8 = np.ones(sm.N, complex)
    for s_ in sm.PROBE_SECTORS["07"]:
        rows7[s_] = Z[s_]
    for s_ in sm.PROBE_SECTORS["08"]:
        rows8[s_] = Z[s_]

    def patch_box(pid, frac=0.6):
        p = lay["patches"][lay["index"][pid]]
        x0, y0, x1, y1 = p["bbox_px"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        q = apply_h(H, np.array([[cx - 90 * frac, cy - 90 * frac], [cx + 90 * frac, cy + 90 * frac]]))
        return int(q[:, 1].min()), int(q[:, 1].max()), int(q[:, 0].min()), int(q[:, 0].max())
    moire = [(*patch_box(20), 6.0, 5.0 * W / 4288), (*patch_box(100), 6.0, 7.0 * W / 4288)]
    truths = {"hard": {"kernel": "hard", "nodes": TRUTH_NODES, "gain": 1.0, "k": 0.97},
              "linear": {"kernel": "linear", "nodes": TRUTH_NODES, "gain": 0.85, "k": 0.97}}
    out = {"frame_size": [W, Hh], "true_rotation_deg": math.degrees(th), "moire_injected_ids": [20, 100],
           "pixel_noise_rgb_sd": {"100": 1.6, "1600": 5.0}, "truths": {}}
    for tname, truth in truths.items():
        d = SELFTEST_TMP / f"frames_{tname}"
        d.mkdir(parents=True, exist_ok=True)
        for p in d.iterdir():
            if p.suffix in (".png", ".jpg", ".json"):
                p.unlink()
        side = {}
        seq = 0
        for iso, noise in ((100, 1.6), (1600, 5.0)):
            for role, Zrow in (("04a", None), ("07", rows7), ("08", rows8), ("04b", None)):
                drift = 1.0 + (0.003 if role == "04b" else 0.0)
                img = camera_frame(base, truth, Zrow, noise, drift, rng, moire)
                name = f"S{seq:02d}_{role}_iso{iso}.jpg"
                Image.fromarray(img).save(d / name, quality=95, subsampling=0)
                side[name] = {"iso": iso, "program": 1, "t": 1 / 30 if iso == 100 else 1 / 500, "f": 4.0,
                              "when": f"2026:10:20 10:00:{seq * 5:02d}", "selector": 1, "role_truth": role}
                seq += 1
        (d / "frames.json").write_text(json.dumps(side, indent=1))
        print(f"[image:{tname}] wrote {seq} frames to {d} ({time.time() - t0:.1f} s)", flush=True)
        a2 = argparse.Namespace(**vars(args))
        sub = LOCAL / "selftest" / f"image_{tname}"
        (sub / "plots").mkdir(parents=True, exist_ok=True)
        a2.out = str(sub / "ring_model.json")
        a2.no_raw = True
        a2.chart = None
        saved_local = globals()["LOCAL"]
        globals()["LOCAL"] = sub
        try:
            model = analyse_dir(d, a2)
        finally:
            globals()["LOCAL"] = saved_local
        dn = sm.wrap180(np.array(model["nodes_unwrapped_deg"]) - TRUTH_NODES)
        ident_ok = all(g["frames"]["07"].split("_")[1] == "07" and g["frames"]["08"].split("_")[1] == "08"
                       for g in model["groups"].values())
        ci = model["node_ci90_deg"]
        cover = float(np.mean([lo - 1e-9 <= nt + 360 * round(((lo + hi) / 2 - nt) / 360) <= hi + 1e-9
                               for (lo, hi), nt in zip(ci, TRUTH_NODES)]))
        pi = model["per_iso_models"].get("1600", {})
        dn16 = sm.wrap180(np.array(pi["nodes_unwrapped_deg"]) - TRUTH_NODES) if pi else None
        rec = {"kernel_true": truth["kernel"], "kernel_est": model["kernel"]["type"],
               "kernel_verdict": model["kernel_verdict"], "iso_verdict": model["iso_comparison"].get("verdict"),
               "identify_07_08_correct": ident_ok,
               "identify_fit_chi2_ratio": {iso: g["identify"]["fit_chi2"]["ratio_wrong_over_right"]
                                           for iso, g in model["groups"].items()},
               "node_err_rms_deg": float(np.sqrt(np.mean(dn ** 2))), "node_err_max_deg": float(np.max(np.abs(dn))),
               "node_ci90_coverage": cover,
               "iso1600_node_err_rms_deg": None if dn16 is None else float(np.sqrt(np.mean(dn16 ** 2))),
               "iso1600_kernel": pi.get("kernel", {}).get("type") if pi else None,
               "gain_true": truth["gain"], "gain_est": model["gain"], "gain_ci90": model["gain_ci90"],
               "k_true": truth["k"], "k_est": model["k_coupling"], "k_ci90": model["k_ci90"],
               "excluded_by_group": {iso: g["excluded"] for iso, g in model["groups"].items()},
               "per_iso_effective_blur": model["iso_comparison"].get("effective_blur_deg"),
               "geometry": {iso: {f: {"corner_rms_px": v["corner_rms_px"], "corners_used": v["corners_used"],
                                      "rotation_deg": v["rotation_deg"], "gap_off_frac": v["gap_check"]["frac_off_by_0.08"]}
                                  for f, v in g["geometry"].items()} for iso, g in model["groups"].items()}}
        out["truths"][tname] = rec
        print(f"[image:{tname}] 07/08 ok {ident_ok}; kernel {rec['kernel_est']} ({rec['kernel_verdict']}); nodes rms "
              f"{rec['node_err_rms_deg']:.2f} max {rec['node_err_max_deg']:.2f} cover {cover:.2f}; gain "
              f"{rec['gain_est']:.3f}/{truth['gain']}; ISO: {rec['iso_verdict']}; excluded {rec['excluded_by_group']}",
              flush=True)
    # camera upside down: orientation from the marker cell counts
    first = SELFTEST_TMP / "frames_hard" / "S00_04a_iso100.jpg"
    rot = np.ascontiguousarray(np.asarray(Image.open(first).convert("RGB"))[::-1, ::-1])
    g_rot = locate_screen(rot, lay)
    g_up = locate_screen(np.asarray(Image.open(first).convert("RGB")), lay)
    out["rotated_copy"] = {"rotation_deg": g_rot["rotation_deg"], "marker_cells": g_rot["marker_cells"],
                           "detected_180": abs(abs(g_rot["rotation_deg"]) - 180) < 5,
                           "upright_rotation_deg": g_up["rotation_deg"], "upright_corner_rms_px": g_up["corner_rms_px"]}
    print(f"[image] rotated copy: {out['rotated_copy']}", flush=True)
    return out


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", nargs="?", help="directory with the ring DNG+JPG frames (and the chart frame)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--quick", action="store_true", help="self-test: two truths, half-size image frames")
    ap.add_argument("--no-image-test", action="store_true")
    ap.add_argument("--image-only", action="store_true", help="self-test: only the synthetic image pipeline")
    ap.add_argument("--from-stage2e", action="store_true", help="partial model from the stage 2e chart probes")
    ap.add_argument("--out", help="model JSON path (default local/ring_model.json)")
    ap.add_argument("--chart", help="file name of the spot-metered chart frame (default: auto)")
    ap.add_argument("--chart-only", help="analyse only this spot-metered chart JPG (+ DNG next to it)")
    ap.add_argument("--inset", type=float, default=40.0, help="ROI inset from patch edges, screen px")
    ap.add_argument("--bootstrap", type=int, default=100)
    ap.add_argument("--reg", type=float, default=1.0, help="weight of the log-gap smoothness prior")
    ap.add_argument("--k", default="free", help="angle/scale coupling: 'free' or a number")
    ap.add_argument("--base", choices=("interp", "mean"), default="interp",
                    help="04 base for a probe frame: time-interpolated between the two 04s, or their mean")
    ap.add_argument("--sig-floor", type=float, default=0.002)
    ap.add_argument("--sig-neighbours", type=int, default=9)
    ap.add_argument("--min-chroma", type=float, default=5.0)
    ap.add_argument("--moire-ratio", type=float, default=40.0)
    ap.add_argument("--moire-amp", type=float, default=1.2)
    ap.add_argument("--edge-sd", type=float, default=12.0, help="ROI luma sd (codes) above which an edge intrudes")
    ap.add_argument("--no-raw", action="store_true")
    args = ap.parse_args()
    if args.k != "free":
        args.k = float(args.k)
    LOCAL.mkdir(parents=True, exist_ok=True)
    (LOCAL / "plots").mkdir(exist_ok=True)
    if args.chart_only:
        jpg = Path(args.chart_only)
        dng = next((jpg.with_suffix(x) for x in (".DNG", ".dng") if jpg.with_suffix(x).exists()), None)
        if dng is None:
            raise SystemExit("the metering check needs the DNG next to the JPG")
        before = {p.name: sha256(p) for p in (jpg, dng)}
        res = chart_frame(jpg, dng, read_meta(jpg, dng, None), args)
        res["sha256_before"] = before
        res["unchanged"] = before == {p.name: sha256(p) for p in (jpg, dng)}
        out = Path(args.out) if args.out else LOCAL / "metering.json"
        out.write_text(json.dumps(sm.jsonable(res), indent=1) + "\n")
        print(json.dumps(sm.jsonable({k: res[k] for k in ("file", "orientation", "checks", "valid_metering_anchor",
                                                         "D4", "u_m_ev_vs_assumed", "u_18_percent_equivalent")}), indent=1))
        if "warning" in res:
            print("WARNING:", res["warning"])
        print(f"wrote {out}")
    elif args.selftest:
        selftest(args)
    elif args.from_stage2e:
        from_stage2e(args)
    elif args.dir:
        analyse_dir(Path(args.dir), args)
    else:
        ap.error("give DIR, --selftest or --from-stage2e")


if __name__ == "__main__":
    main()
