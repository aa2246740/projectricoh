#!/usr/bin/env python3
"""Block statistics, radial gain and tone-curve fitting for GR IV pairs.

All functions are pure; inputs come from gr4io.load_pair caches.

Block = k x k half-resolution pixels (default k = 4, i.e. 8 x 8 sensor
pixels). Statistics on blocks keep sharpening, grain and JPEG noise out of
the means, but the means are only used where the RAW block is flat, so the
nonlinear JPEG curve does not mix two levels inside one block.

u    see gr4io: 2**BE * (R/nR + 2G/nG + B/nB) / 4 on normalised camera RGB.
u_c  u * g(r): u after the radial gain g that the camera applies before its
     tone curve (lens-shading compensation). g(0) = 1 by definition, so u_c
     equals u at the image centre.
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'color_references'))

import gr4io  # noqa: E402
import colour_math as cm  # noqa: E402

LUMA709 = np.array([0.2126, 0.7152, 0.0722], np.float32)


def _blk(a, k):
    h, w = a.shape[:2]
    h -= h % k
    w -= w % k
    a = a[:h, :w]
    return a.reshape(h // k, k, w // k, k, *a.shape[2:])


def blocks(pair, k=4):
    """Return per-block arrays. pair is a gr4io.load_pair result."""
    rgb = pair['rgb']
    n = np.asarray(pair['neutral'], np.float32)
    be = float(pair['baseline_exposure'])
    scale = np.float32(2.0 ** be)
    wb = rgb / n * scale
    u = (wb[..., 0] + 2 * wb[..., 1] + wb[..., 2]) / 4
    jpg = pair['jpeg_half']
    jl = jpg @ LUMA709
    bw = _blk(wb, k)
    bu = _blk(u, k)
    bj = _blk(jpg, k)
    bjl = _blk(jl, k)
    out = {
        'wb': bw.mean(axis=(1, 3)),
        'u': bu.mean(axis=(1, 3)),
        'u_cv': bu.std(axis=(1, 3)) / np.maximum(bu.mean(axis=(1, 3)), 1e-6),
        'jpeg': bj.mean(axis=(1, 3)),
        'jl': bjl.mean(axis=(1, 3)),
        'jl_std': bjl.std(axis=(1, 3)),
        'k': k,
    }
    hh, ww = out['u'].shape
    yy, xx = np.mgrid[0:hh, 0:ww]
    out['r2'] = (((yy - (hh - 1) / 2) ** 2 + (xx - (ww - 1) / 2) ** 2) /
                 ((hh / 2) ** 2 + (ww / 2) ** 2)).astype(np.float32)
    # Scene colorimetry: camera RGB (unbalanced) -> XYZ D50 by the DNG
    # ColorMatrix model (colour_math.dng_camera_to_xyz). The AsShotNeutral
    # maps to D50 with Y = 1, so XYZ is on the same scale as u (u of a
    # neutral equals its Y up to the 2**BE factor applied here too).
    tags = gr4io.dng_tags_for_colour(pair)
    m, info = cm.dng_camera_to_xyz(tags)
    cam = _blk(rgb, k).mean(axis=(1, 3))
    out['xyz'] = (cam @ np.asarray(m, np.float32).T) * scale
    out['cam_to_xyz'] = np.asarray(m)
    out['cct'] = float(info['cct_K_approx'])
    return out


def scene_lab(xyz, white_y=1.0):
    """CIE Lab (D50) of scene XYZ; white_y sets which Y is L* = 100."""
    return cm.xyz_lab(np.clip(xyz, 0, None) / white_y)


def jpeg_lab(jpeg_255):
    """Encoded sRGB 0..255 -> Lab D50 (sRGB D65 primaries, Bradford to D50)."""
    return cm.rgb_lab(np.clip(jpeg_255 / 255.0, 0, 1))


def radial_gain_ev(coef, r2):
    """Gain in EV applied by the camera at normalised radius^2 (corner = 1)."""
    return -(coef[0] * r2 + coef[1] * r2 ** 2 + coef[2] * r2 ** 3) / np.log(2)


def fit_tone_radial(lu, jl, sel, r2, iters=6, min_count=20, fix_radial=None):
    """Joint fit: jl = f(lu + G(r2)), G polynomial in r2 (3 terms), f monotone.

    Uses the inverse form lu = f^-1(jl) - G(r2), estimating f^-1 as the
    median lu per integer JPEG code. Returns radial coefficients (natural-log
    units; gain in EV = radial_gain_ev) and the inverse table.
    """
    cs = np.arange(256)
    corr = np.zeros_like(lu)
    coef = np.zeros(3)
    if fix_radial is not None:
        coef = np.asarray(fix_radial, float)
        corr = coef[0] * r2 + coef[1] * r2 ** 2 + coef[2] * r2 ** 3
        iters = 1
    jb = np.clip(np.round(jl).astype(int), 0, 255)
    resid = np.array([0.0])
    use = sel
    for _ in range(iters):
        luc = lu - corr
        inv = np.full(256, np.nan)
        for c in range(256):
            s = sel & (jb == c)
            if s.sum() >= min_count:
                inv[c] = np.median(luc[s])
        good = np.isfinite(inv)
        invf = np.interp(cs, cs[good], inv[good])
        use = sel & good[jb]
        rr = lu - np.interp(jl, cs, invf)
        if fix_radial is None:
            x = np.array([np.ones(use.sum()), r2[use], r2[use] ** 2, r2[use] ** 3]).T
            b, *_ = np.linalg.lstsq(x, rr[use], rcond=None)
            coef = b[1:]
            corr = coef[0] * r2 + coef[1] * r2 ** 2 + coef[2] * r2 ** 3
            resid = rr[use] - x @ b
        else:
            resid = rr[use] - corr[use]
    return {'radial_coef': coef, 'inverse_lu_by_code': inv, 'good_codes': good,
            'resid_ev_std': float(np.std(resid) / np.log(2)), 'n': int(use.sum())}


def correct_u(lu, r2, coef):
    """log u_c = log u - G(r2), i.e. multiply u by the camera's radial gain."""
    return lu - (coef[0] * r2 + coef[1] * r2 ** 2 + coef[2] * r2 ** 3)


def forward_curve(luc, jl, sel, step=0.04, min_count=30, lo=None, hi=None):
    """Median JPEG luma in log-u bins (natural log step). Returns rows."""
    v = luc[sel]
    j = jl[sel]
    lo = np.floor(v.min() / step) * step if lo is None else lo
    hi = np.ceil(v.max() / step) * step if hi is None else hi
    edges = np.arange(lo, hi + step, step)
    rows = []
    idx = np.digitize(v, edges) - 1
    order = np.argsort(idx, kind='stable')
    idx_s = idx[order]
    v_s = v[order]
    j_s = j[order]
    bounds = np.searchsorted(idx_s, np.arange(len(edges)))
    for b in range(len(edges) - 1):
        a, z = bounds[b], bounds[b + 1]
        if z - a < min_count:
            continue
        jj = j_s[a:z]
        rows.append({'lu': float(np.median(v_s[a:z])), 'u': float(np.exp(np.median(v_s[a:z]))),
                     'j50': float(np.median(jj)), 'j25': float(np.percentile(jj, 25)),
                     'j75': float(np.percentile(jj, 75)), 'n': int(z - a)})
    return rows


def monotone(y):
    """Pool-adjacent-violators, non-decreasing, equal weights."""
    vals, wts, cnt = [], [], []
    for v in map(float, y):
        vals.append(v)
        wts.append(1.0)
        cnt.append(1)
        while len(vals) > 1 and vals[-2] > vals[-1]:
            w = wts[-2] + wts[-1]
            v2 = (vals[-2] * wts[-2] + vals[-1] * wts[-1]) / w
            c = cnt[-2] + cnt[-1]
            vals[-2:] = [v2]
            wts[-2:] = [w]
            cnt[-2:] = [c]
    out = []
    for v, c in zip(vals, cnt):
        out += [v] * c
    return np.array(out)


def curve_fn(rows):
    """Monotone interpolant JPEG = f(log u) from forward rows; NaN outside."""
    x = np.array([r['lu'] for r in rows])
    y = monotone([r['j50'] for r in rows])

    def f(lu):
        return np.interp(lu, x, y, left=np.nan, right=np.nan)
    f.support = (float(x.min()), float(x.max()))
    f.x = x
    f.y = y
    return f


def inverse_fn(f):
    """log u = f^-1(J) on the strictly increasing part of f."""
    x, y = f.x, f.y
    keep = np.concatenate([[True], np.diff(y) > 1e-6])
    xs, ys = x[keep], y[keep]

    def g(j):
        return np.interp(j, ys, xs, left=np.nan, right=np.nan)
    g.range = (float(ys.min()), float(ys.max()))
    return g


def hue_deg(lab):
    return np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360


def chroma(lab):
    return np.hypot(lab[..., 1], lab[..., 2])


def wrap180(d):
    return (d + 180) % 360 - 180
