#!/usr/bin/env python3
"""GR IV Hi-contrast B&W: curve, channel mix, grain and spatial processing.

Writes local/hcbw.json. Run after tone.py:
    python3 -I research/gr4_modes/hcbw.py

Frames: hdf_hc (body B, same scene as hdf_std), hc_bw (body A), and the
public GR IV / GR III Monotone frames for the mix cross-check. Contributor
arrays stay in local/.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'color_references'))
import core  # noqa: E402
import gr4io  # noqa: E402
import colour_math as cm  # noqa: E402

LOCAL = HERE / 'local'
PUBLIC_CACHE = '/tmp/gr4modes_work/cache'
STAGE2D = HERE.parent / 'stage2d_verification'


def load(key, cdir=None):
    pair = gr4io.load_pair(None, None, cache_name=key, cache_dir=cdir)
    return pair, core.blocks(pair)


def neutral_curve(b, coef, lo=4, hi=240):
    wb = b['wb']
    jl = b['jpeg'][..., 1]
    spread = (wb.max(-1) - wb.min(-1)) / np.maximum(wb.mean(-1), 1e-6)
    lu = np.log(np.clip(b['u'], 1e-6, None))
    luc = core.correct_u(lu, b['r2'], coef)
    flat = (b['u_cv'] < 0.06) & (jl > lo) & (jl < hi)
    neu = flat & (spread < 0.1)
    f = core.curve_fn(core.forward_curve(luc, jl, neu, step=0.05, min_count=30))
    return f, flat, luc - lu


def fit_mix(pair, b, coef):
    """Least squares for w in  u_eq = w . c'  where u_eq = f_neutral^-1(J)."""
    f, flat, lgain = neutral_curve(b, coef)
    inv = core.inverse_fn(f)
    jl = b['jpeg'][..., 1]
    ueq = np.exp(inv(jl) - lgain)
    ok = flat & np.isfinite(ueq)
    x = b['wb'][ok]
    y = ueq[ok]
    w, *_ = np.linalg.lstsq(x / y[:, None], np.ones(len(y)), rcond=None)
    rel = (x @ w) / y - 1
    hh, ww = jl.shape
    yy, xx = np.mgrid[0:hh, 0:ww]
    parts = []
    for part in (xx < ww / 2, xx >= ww / 2, yy < hh / 2, yy >= hh / 2):
        s = ok & part
        parts.append(np.linalg.lstsq(b['wb'][s] / ueq[s][:, None], np.ones(s.sum()), rcond=None)[0])
    m = b['cam_to_xyz']
    n = np.asarray(pair['neutral'], float)
    to_c = np.linalg.inv(m @ np.diag(n)) @ cm.cat(cm.D65, cm.D50) @ cm.SRGB_XYZ
    ws = w @ to_c
    wy = m[1, :] * n
    return {'w_cam_wb': (w / w.sum()).tolist(), 'w_sum': float(w.sum()),
            'half_image_std': np.std(parts, axis=0).tolist(),
            'rel_resid_rms': float(np.sqrt(np.mean(rel ** 2))), 'n_blocks': int(ok.sum()),
            'w_linear_srgb': (ws / ws.sum()).tolist(),
            'xyzY_in_cam_wb': (wy / wy.sum()).tolist(), 'cct_K': b['cct'],
            'neutral_support_u_c': [float(np.exp(f.support[0])), float(np.exp(f.support[1]))]}


def gxr_mix():
    """GXR true-B&W mix from the stage2d chart (R8051150): u_eq = row20^-1(J)."""
    meas = json.loads((STAGE2D / 'measurements.json').read_text())
    rows = json.loads((STAGE2D / 'local' / 'official_rows.json').read_text())
    a = [int(rows['tone_row20_A_hex'][i:i + 4], 16) for i in range(0, 124, 4)]
    bb = [int(rows['tone_row20_B_hex'][i:i + 2], 16) for i in range(0, 66, 2)]
    x20 = np.array([0] + a + [4095], float)
    y20 = np.array(bb, float)
    keep = np.concatenate([[True], np.diff(y20) > 0])
    xs, ys, labels = [], [], []
    for p in meas['frames']['03_hcbw']['patches']:
        j = float(np.mean(p['jpeg_srgb']) * 255)
        if not 12 < j < 235:
            continue
        xs.append(np.array(p['camera_rgb_wb']) * 4095)
        ys.append(np.interp(j, y20[keep], x20[keep]))
        labels.append(p['label'])
    x = np.array(xs)
    y = np.array(ys)
    w, *_ = np.linalg.lstsq(x / y[:, None], np.ones(len(y)), rcond=None)
    out = {'w_cam_wb': (w / w.sum()).tolist(), 'rel_resid': ((x @ w) / y - 1).tolist(), 'labels': labels,
           'note': 'GXR WB camera RGB, 22 chart patches with 12 < J < 235; JPEG inverted through official row 20'}
    # GXR DNG colour tags (read-only) for the linear-sRGB expression.
    from tiff_makernote import Tiff
    dng = HERE.parents[1] / 'captures/a12-50/2026-10-19/stage2d-colorchecker/R8051150.DNG'
    t = Tiff(dng.read_bytes())
    root, _ = t.ifd(t.root)
    tags = {e['tag']: e['value'] for e in root}
    m, info = cm.dng_camera_to_xyz(tags)
    n = np.array(tags[50728], float)
    to_c = np.linalg.inv(m @ np.diag(n)) @ cm.cat(cm.D65, cm.D50) @ cm.SRGB_XYZ
    ws = w @ to_c
    out['w_linear_srgb'] = (ws / ws.sum()).tolist()
    out['gxr_to_c_from_linsrgb'] = to_c.tolist()
    out['gxr_dng_baseline_exposure'] = tags.get(50730)
    out['gxr_cct_K'] = float(info['cct_K_approx'])
    return out


def mix_effect_on_chart(gr_w_srgb, gxr):
    """EV difference GR-IV-style grey vs GXR grey on the GXR chart patches."""
    meas = json.loads((STAGE2D / 'measurements.json').read_text())
    to_c = np.array(gxr['gxr_to_c_from_linsrgb'])
    from_c = np.linalg.inv(to_c)          # c' -> linear sRGB
    wg = np.array(gxr['w_cam_wb'])
    out = {}
    for p in meas['frames']['03_hcbw']['patches']:
        c = np.array(p['camera_rgb_wb'])
        lin = from_c @ c
        l_gr = float(np.dot(gr_w_srgb, lin))
        l_gxr = float(np.dot(wg, c))
        out[p['label']] = float(np.log2(max(l_gr, 1e-6) / max(l_gxr, 1e-6)))
    return out


def grain_stats(pair, coef, w_mix, f_curve, step_levels):
    """Half-res: e = J - f(log u_c) inside 8x8 half-res tiles.

    e is split into the part explained by the RAW-driven high-pass (gain beta:
    sharpening > 0, noise reduction < 0) and the remainder, which is noise the
    RAW does not contain: grain, or JPEG error.
    """
    rgb = pair['rgb']
    n = np.asarray(pair['neutral'], np.float32)
    wb = rgb / n * np.float32(2.0 ** float(pair['baseline_exposure']))
    lmix = wb @ np.asarray(w_mix, np.float32)
    hh, ww = lmix.shape
    yy, xx = np.mgrid[0:hh, 0:ww]
    r2 = (((yy - (hh - 1) / 2) ** 2 + (xx - (ww - 1) / 2) ** 2) / ((hh / 2) ** 2 + (ww / 2) ** 2)).astype(np.float32)
    luc = core.correct_u(np.log(np.clip(lmix, 1e-6, None)), r2, coef)
    j = pair['jpeg_half'][..., 1] if pair['jpeg_half'].ndim == 3 else pair['jpeg_half']
    jp = f_curve(luc)
    e = j - jp
    t = 8
    hh -= hh % t
    ww -= ww % t
    def tiles(a):
        return a[:hh, :ww].reshape(hh // t, t, ww // t, t)
    tj, tp, te, tl = tiles(j), tiles(jp), tiles(e), tiles(luc)
    mp = tp.mean(axis=(1, 3), keepdims=True)
    hp = tp - mp
    me = te.mean(axis=(1, 3), keepdims=True)
    ec = te - me
    s_hp = hp.std(axis=(1, 3))
    s_e = ec.std(axis=(1, 3))
    beta = (hp * ec).mean(axis=(1, 3)) / np.maximum((hp ** 2).mean(axis=(1, 3)), 1e-9)
    s_rem = np.sqrt(np.maximum(s_e ** 2 - beta ** 2 * s_hp ** 2, 0))
    lev = tl.mean(axis=(1, 3))
    lstd = tl.std(axis=(1, 3))
    jm = tj.mean(axis=(1, 3))
    ok = np.isfinite(s_e) & np.isfinite(mp[:, 0, :, 0]) & (lstd < 0.06) & (jm > 3) & (jm < 245)
    rows = []
    for lo, hi in zip(step_levels[:-1], step_levels[1:]):
        s = ok & (jm >= lo) & (jm < hi)
        if s.sum() < 40:
            continue
        rows.append({'jpeg_lo': float(lo), 'jpeg_hi': float(hi), 'n_tiles': int(s.sum()),
                     'raw_driven_std': float(np.median(s_hp[s])),
                     'jpeg_resid_std': float(np.median(s_e[s])),
                     'beta_median': float(np.median(beta[s])),
                     'unexplained_std': float(np.median(s_rem[s]))})
    return rows


def grain_acf(jpg_path, pair, lo, hi, tile=64):
    """Full-res JPEG G: std and autocorrelation of (J - gaussian6(J)) in flat tiles."""
    from PIL import Image
    j = np.asarray(Image.open(jpg_path).convert('RGB'), np.float32)[..., 1]
    u = gr4io.u_of(pair['rgb'], pair['neutral'], float(pair['baseline_exposure']))
    lu = np.log(np.clip(u, 1e-5, None))
    m = ndimage.uniform_filter(lu, 16)
    v = ndimage.uniform_filter(lu ** 2, 16) - m ** 2
    flat = np.repeat(np.repeat(np.sqrt(np.maximum(v, 0)) < 0.04, 2, 0), 2, 1)[:j.shape[0], :j.shape[1]]
    h = j - ndimage.gaussian_filter(j, 6)
    acs, stds = [], []
    for y in range(0, j.shape[0] - tile, tile):
        for x in range(0, j.shape[1] - tile, tile):
            if not flat[y:y + tile, x:x + tile].all():
                continue
            if not lo <= j[y:y + tile, x:x + tile].mean() <= hi:
                continue
            t = h[y:y + tile, x:x + tile]
            t = t - t.mean()
            f = np.fft.fft2(t)
            ac = np.real(np.fft.ifft2(f * np.conj(f)))
            acs.append(np.fft.fftshift(ac / ac[0, 0]))
            stds.append(float(t.std()))
    if not acs:
        return {'tiles': 0}, h
    ac = np.mean(acs, 0)
    c = tile // 2
    return {'tiles': len(acs), 'hp_std_median': float(np.median(stds)),
            'acf_x_lag0_5': ac[c, c:c + 6].tolist(), 'acf_y_lag0_5': ac[c:c + 6, c].tolist(),
            'j_range': [lo, hi]}, h


def spatial_regression(b, coef, w_mix, f_curve, mask=None):
    lmix = b['wb'] @ np.asarray(w_mix, np.float32)
    lu = np.log(np.clip(lmix, 1e-6, None))
    luc = core.correct_u(lu, b['r2'], coef)
    jl = b['jpeg'][..., 1]
    inv = core.inverse_fn(f_curve)
    ueq = inv(jl)
    flat = (b['u_cv'] < 0.06) & (jl > 4) & (jl < 240) & np.isfinite(ueq)
    if mask is not None:
        flat &= mask
    r = (luc - ueq)[flat]
    cols, names = [np.ones(flat.sum())], ['const']
    for s in (4, 16, 48, 128):
        cols.append((ndimage.gaussian_filter(luc, s) - luc)[flat])
        names.append(f'surround_sigma{s}_minus_self')
    x = np.array(cols).T
    out = {'resid_ev_std': float(r.std() / np.log(2)), 'n': int(flat.sum()), 'single': {}}
    for i in range(1, len(names)):
        bcoef, *_ = np.linalg.lstsq(x[:, [0, i]], r, rcond=None)
        pred = x[:, [0, i]] @ bcoef
        out['single'][names[i]] = {'slope': float(bcoef[1]), 'r2': float(1 - np.mean((r - pred) ** 2) / r.var())}
    bcoef, *_ = np.linalg.lstsq(x, r, rcond=None)
    pred = x @ bcoef
    out['all'] = {'coef': dict(zip(names, map(float, bcoef))), 'r2': float(1 - np.mean((r - pred) ** 2) / r.var())}
    return out


def main():
    tone = json.loads((LOCAL / 'tone_curves.json').read_text())
    coef4 = np.array(tone['radial']['gr4_coef_natural_log'])
    coef3 = np.array(tone['radial']['gr3_coef_natural_log'])
    out = {'frames': {}}
    mixes = {}
    for key, cdir, coef in [('hdf_hc', None, coef4), ('hc_bw', None, coef4),
                            ('gruser_G4000053', PUBLIC_CACHE, coef4), ('gruser_GR002813', PUBLIC_CACHE, coef3)]:
        pair, b = load(key, cdir)
        mixes[key] = fit_mix(pair, b, coef)
        print(key, 'mix', np.round(mixes[key]['w_cam_wb'], 3), 'lin sRGB', np.round(mixes[key]['w_linear_srgb'], 3),
              'rms', round(mixes[key]['rel_resid_rms'], 3), flush=True)
    out['mix'] = mixes
    w_mix = np.mean([mixes[k]['w_cam_wb'] for k in ('hdf_hc', 'hc_bw', 'gruser_G4000053')], axis=0)
    w_srgb = np.mean([mixes[k]['w_linear_srgb'] for k in ('hdf_hc', 'hc_bw', 'gruser_G4000053')], axis=0)
    out['mix_used'] = {'w_cam_wb': w_mix.tolist(), 'w_linear_srgb': w_srgb.tolist()}
    gx = gxr_mix()
    out['gxr_mix'] = gx
    out['gr4_minus_gxr_grey_ev_on_gxr_chart'] = mix_effect_on_chart(w_srgb, gx)
    print('GXR mix', np.round(gx['w_cam_wb'], 3), 'lin sRGB', np.round(gx.get('w_linear_srgb', []), 3))
    # HC curve on L = mix (all flat blocks), radial corrected.
    levels = np.array([0, 3, 8, 15, 25, 40, 60, 85, 110, 140, 170, 200, 225, 245])
    curves = {}
    for key in ('hdf_hc', 'hc_bw'):
        pair, b = load(key)
        lmix = b['wb'] @ w_mix.astype(np.float32)
        luc = core.correct_u(np.log(np.clip(lmix, 1e-6, None)), b['r2'], coef4)
        jl = b['jpeg'][..., 1]
        flat = (b['u_cv'] < 0.06) & (lmix > 2e-4)
        rows = core.forward_curve(luc, jl, flat, step=0.04, min_count=30)
        curves[key] = rows
        f = core.curve_fn(rows)
        rec = {'curve_mix': rows,
               'jpeg_max_observed': float(pair['jpeg_half'][..., 1].max()),
               'jpeg_p9999': float(np.percentile(pair['jpeg_half'][..., 1], 99.99)),
               'frac_zero_halfres': float(np.mean(pair['jpeg_half'][..., 1] < 0.5)),
               'spatial': spatial_regression(b, coef4, w_mix, f)}
        rec['grain'] = grain_stats(pair, coef4, w_mix, f, levels)
        out['frames'][key] = rec
        print(key, 'support', np.exp(f.support), 'Jmax', rec['jpeg_max_observed'], flush=True)
    # Same grain statistic on colour frames (JPEG G channel against u) for contrast.
    for key in ('hdf_std', 'hdf_pos', 'hdf_neg', 'positive', 'negative'):
        pair, b = load(key)
        lu = np.log(np.clip(b['u'], 1e-6, None))
        luc = core.correct_u(lu, b['r2'], coef4)
        wb = b['wb']
        spread = (wb.max(-1) - wb.min(-1)) / np.maximum(wb.mean(-1), 1e-6)
        jl = b['jpeg'][..., 1]
        sel = (b['u_cv'] < 0.06) & (spread < 0.15)
        f = core.curve_fn(core.forward_curve(luc, jl, sel, step=0.04, min_count=30))
        out['frames'][key] = {'grain': grain_stats(pair, coef4, [0.25, 0.5, 0.25], f, levels),
                              'spatial': spatial_regression(b, coef4, [0.25, 0.5, 0.25], f, mask=spread < 0.15)}
        print(key, 'grain/spatial done', flush=True)
    # Full-resolution grain texture: ACF in three level ranges, and whether the
    # pattern is position-locked (same high-pass at the same pixel in A and B).
    caps = HERE.parents[1] / 'captures/contrib/2026-10-19'
    jpgs = {'hc_bw': caps / 'gr4-modes/hc_bw.JPG', 'hdf_hc': caps / 'gr4hdf-set/R0003007_bw.JPG',
            'hdf_std': caps / 'gr4hdf-set/R0003009_standard.JPG', 'hdf_neg': caps / 'gr4hdf-set/R0003006_negative.JPG'}
    acf = {}
    highpass = {}
    for key, path in jpgs.items():
        pair = gr4io.load_pair(None, None, cache_name=key)
        acf[key] = {}
        for lo, hi in ((25, 90), (90, 180), (200, 240)):
            res, h = grain_acf(path, pair, lo, hi)
            acf[key][f'{lo}-{hi}'] = res
        highpass[key] = h
    out['grain_acf_fullres'] = acf
    from PIL import Image
    ja = np.asarray(Image.open(jpgs['hc_bw']).convert('L'), np.float32)
    jb = np.asarray(Image.open(jpgs['hdf_hc']).convert('L'), np.float32)
    s = (ja > 60) & (ja < 200) & (jb > 60) & (jb < 200)
    out['grain_fixed_pattern_corr_A_vs_B'] = {'pixels': int(s.sum()),
                                               'corr': float(np.corrcoef(highpass['hc_bw'][s], highpass['hdf_hc'][s])[0, 1])}
    print('fixed-pattern corr', out['grain_fixed_pattern_corr_A_vs_B'])
    (LOCAL / 'hcbw.json').write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
