#!/usr/bin/env python3
"""Positive / Negative colour: GR IV against Standard, against RAW, and GR III.

Scene colour per block: camera RGB -> XYZ (D50) by the DNG ColorMatrix model
(colour_math.dng_camera_to_xyz, AsShotNeutral -> D50 white), times 2**BE and
the camera's radial gain, so it is on the u_c scale. Scene L* uses white_y =
U_MID / 0.184, i.e. a metered mid-grey (GR IV Standard 118 point, u_c = U_MID)
gets L* = 50.

Two comparisons:
  vs Standard (same scene, body B): bins by scene hue (15 deg), scene chroma
    and scene L*; in each bin, median JPEG Lab of the mode and of Standard.
    Frames are hand-held and not registered; matching is through the RAW.
  vs RAW (any frame): per block, scene a*b* is recomputed at the JPEG L*
    (scale XYZ so that L*_scene = L*_jpeg), then C_jpeg / C_scene and
    h_jpeg - h_scene. This removes the tone curve from the chroma ratio.

Writes local/colour.json.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'color_references'))
import core  # noqa: E402
import gr4io  # noqa: E402
import colour_math as cm  # noqa: E402

LOCAL = HERE / 'local'
PUBLIC_CACHE = '/tmp/gr4modes_work/cache'
U_MID = 0.086
WHITE_Y = U_MID / 0.184
HUE_EDGES = np.arange(0, 361, 15)
L_LAYERS = [(0, 35), (35, 60), (60, 80), (80, 101)]
C_CLASSES = [(6, 12), (12, 25), (25, 200)]


def frame(key, coef, cdir=None):
    pair = gr4io.load_pair(None, None, cache_name=key, cache_dir=cdir)
    b = core.blocks(pair)
    lu = np.log(np.clip(b['u'], 1e-6, None))
    gain = np.exp(core.correct_u(lu, b['r2'], coef) - lu)
    xyz = b['xyz'] * gain[..., None]
    scene = core.scene_lab(xyz, WHITE_Y)
    jlab = core.jpeg_lab(b['jpeg'])
    jp = b['jpeg']
    ok = (b['u_cv'] < 0.06) & (jp.min(-1) > 2) & (jp.max(-1) < 253) & (b['u'] > 1e-3)
    return {'scene': scene, 'xyz': xyz, 'jlab': jlab, 'ok': ok, 'u_c': b['u'] * gain}


def lightness_matched_scene(xyz, l_target):
    """Scale scene XYZ so that its L* equals l_target; return Lab."""
    fy = (np.asarray(l_target) + 16) / 116
    y_t = np.where(fy > 6 / 29, fy ** 3, 3 * (6 / 29) ** 2 * (fy - 4 / 29))
    y = np.maximum(xyz[..., 1], 1e-9)
    return cm.xyz_lab(np.clip(xyz * (y_t / y)[..., None], 0, None))


def vs_raw(fr, cmin=8):
    """Per hue bin and L* layer: median C_jpeg/C_scene(L-matched), hue shift."""
    sc = fr['scene']
    ok = fr['ok'] & (core.chroma(sc) > cmin)
    lm = lightness_matched_scene(fr['xyz'][ok], fr['jlab'][ok][:, 0])
    cs = core.chroma(lm)
    cj = core.chroma(fr['jlab'][ok])
    hs = core.hue_deg(sc[ok])
    dh = core.wrap180(core.hue_deg(fr['jlab'][ok]) - core.hue_deg(lm))
    ratio = cj / np.maximum(cs, 1e-6)
    lj = fr['jlab'][ok][:, 0]
    out = []
    for h0, h1 in zip(HUE_EDGES[:-1], HUE_EDGES[1:]):
        sh = (hs >= h0) & (hs < h1)
        rec = {'hue': [int(h0), int(h1)], 'n': int(sh.sum())}
        if sh.sum() >= 30:
            rec.update({'chroma_ratio': float(np.median(ratio[sh])), 'hue_shift': float(np.median(dh[sh])),
                        'ratio_iqr': [float(np.percentile(ratio[sh], 25)), float(np.percentile(ratio[sh], 75))],
                        'scene_C_median': float(np.median(core.chroma(sc[ok][sh]))),
                        'jpeg_L_median': float(np.median(lj[sh]))})
            layers = {}
            for l0, l1 in L_LAYERS:
                s = sh & (lj >= l0) & (lj < l1)
                if s.sum() >= 30:
                    layers[f'{l0}-{l1}'] = {'n': int(s.sum()), 'chroma_ratio': float(np.median(ratio[s])),
                                            'hue_shift': float(np.median(dh[s]))}
            rec['by_jpeg_L'] = layers
        out.append(rec)
    return out


def bin_index(scene):
    h = core.hue_deg(scene)
    c = core.chroma(scene)
    hb = np.digitize(h, HUE_EDGES) - 1
    cb = np.full(h.shape, -1)
    for i, (c0, c1) in enumerate(C_CLASSES):
        cb[(c >= c0) & (c < c1)] = i
    lb = np.full(h.shape, -1)
    for i, (l0, l1) in enumerate(L_LAYERS):
        lb[(scene[..., 0] >= l0) & (scene[..., 0] < l1)] = i
    return hb, cb, lb


def vs_standard(std, mode, min_n=25):
    """RAW-matched bins: mode JPEG vs Standard JPEG."""
    res = []
    hs, cs, ls = bin_index(std['scene'])
    hm, cmo, lmo = bin_index(mode['scene'])
    for hb in range(len(HUE_EDGES) - 1):
        for cb in range(len(C_CLASSES)):
            for lb in range(len(L_LAYERS)):
                a = std['ok'] & (hs == hb) & (cs == cb) & (ls == lb)
                m = mode['ok'] & (hm == hb) & (cmo == cb) & (lmo == lb)
                if a.sum() < min_n or m.sum() < min_n:
                    continue
                ja = np.median(std['jlab'][a], axis=0)
                jm = np.median(mode['jlab'][m], axis=0)
                sa = np.median(std['scene'][a], axis=0)
                sm = np.median(mode['scene'][m], axis=0)
                res.append({'hue_bin': int(hb), 'c_class': int(cb), 'l_layer': int(lb),
                            'n_std': int(a.sum()), 'n_mode': int(m.sum()),
                            'scene_std': sa.tolist(), 'scene_mode': sm.tolist(),
                            'jpeg_std': ja.tolist(), 'jpeg_mode': jm.tolist(),
                            'chroma_ratio': float(core.chroma(jm) / max(core.chroma(ja), 1e-6)),
                            'hue_shift': float(core.wrap180(core.hue_deg(jm) - core.hue_deg(ja))),
                            'dL': float(jm[0] - ja[0])})
    return res


def summarise_bins(rows):
    """Collapse to hue bins: n-weighted medians over chroma classes / L layers."""
    out = []
    for hb in range(len(HUE_EDGES) - 1):
        rr = [r for r in rows if r['hue_bin'] == hb and core.chroma(np.array(r['jpeg_std'])) > 4]
        if not rr:
            continue
        w = np.array([min(r['n_std'], r['n_mode']) for r in rr], float)
        def wmed(v):
            v = np.asarray(v, float)
            o = np.argsort(v)
            cw = np.cumsum(w[o])
            return float(v[o][np.searchsorted(cw, cw[-1] / 2)])
        out.append({'hue': [int(HUE_EDGES[hb]), int(HUE_EDGES[hb + 1])], 'bins': len(rr), 'blocks': int(w.sum()),
                    'chroma_ratio': wmed([r['chroma_ratio'] for r in rr]),
                    'hue_shift': wmed([r['hue_shift'] for r in rr]),
                    'dL': wmed([r['dL'] for r in rr]),
                    'ratio_range': [float(min(r['chroma_ratio'] for r in rr)), float(max(r['chroma_ratio'] for r in rr))],
                    'by_layer': {f'{L_LAYERS[lb][0]}-{L_LAYERS[lb][1]}': {
                        'chroma_ratio': float(np.median([r['chroma_ratio'] for r in rr if r['l_layer'] == lb])),
                        'hue_shift': float(np.median([r['hue_shift'] for r in rr if r['l_layer'] == lb])),
                        'bins': sum(r['l_layer'] == lb for r in rr)}
                        for lb in range(len(L_LAYERS)) if any(r['l_layer'] == lb for r in rr)}})
    return out


def grey_axis(std, mode, cmax=4.0):
    """Near-neutral scene blocks: JPEG a*, b* against scene L*, mode and Standard."""
    out = []
    for name, fr in (('standard', std), ('mode', mode)):
        if fr is None:
            continue
        s = fr['ok'] & (core.chroma(fr['scene']) < cmax)
        L = fr['scene'][..., 0][s]
        lab = fr['jlab'][s]
        rows = []
        for l0 in range(0, 100, 5):
            t = (L >= l0) & (L < l0 + 5)
            if t.sum() < 40:
                continue
            rows.append({'scene_L': [l0, l0 + 5], 'n': int(t.sum()), 'jpeg_L': float(np.median(lab[t, 0])),
                         'a': float(np.median(lab[t, 1])), 'b': float(np.median(lab[t, 2])),
                         'scene_a': float(np.median(fr['scene'][..., 1][s][t])),
                         'scene_b': float(np.median(fr['scene'][..., 2][s][t]))})
        # Toning at the scene neutral: per L* band, fit JPEG ab = G . scene ab + c
        # on blocks with scene C < 10; c is the JPEG colour a neutral would get.
        s2 = fr['ok'] & (core.chroma(fr['scene']) < 10)
        L2 = fr['scene'][..., 0][s2]
        sab = fr['scene'][..., 1:][s2]
        jab = fr['jlab'][..., 1:][s2]
        jl2 = fr['jlab'][..., 0][s2]
        icpt = []
        for l0 in range(0, 100, 10):
            t = (L2 >= l0) & (L2 < l0 + 10)
            if t.sum() < 80 or np.ptp(sab[t], axis=0).min() < 3:
                continue
            x = np.column_stack([sab[t], np.ones(t.sum())])
            coef, *_ = np.linalg.lstsq(x, jab[t], rcond=None)
            icpt.append({'scene_L': [l0, l0 + 10], 'n': int(t.sum()), 'jpeg_L': float(np.median(jl2[t])),
                         'a0': float(coef[2, 0]), 'b0': float(coef[2, 1]),
                         'gain_aa': float(coef[0, 0]), 'gain_bb': float(coef[1, 1])})
        out.append({'frame': name, 'rows': rows, 'neutral_intercept': icpt})
    return out


def gr3_chart_groups():
    """GR III bastibe chart, same RAW: per-patch mode vs Standard from the
    existing measurement table (research/color_references/gr3_chart_targets.csv)."""
    import csv
    path = HERE.parent / 'color_references' / 'gr3_chart_targets.csv'
    rows = list(csv.DictReader(path.open()))
    by = {}
    for r in rows:
        by.setdefault(r['patch'], {})[r['mode']] = r
    out = []
    for patch, d in by.items():
        if not all(m in d for m in ('standard', 'positive', 'negative')):
            continue
        lab = {m: np.array([float(d[m]['target_L']), float(d[m]['target_a']), float(d[m]['target_b'])]) for m in d}
        cam = np.array([float(d['standard'][k]) for k in ('camera_R', 'camera_G', 'camera_B')])
        rec = {'patch': patch, 'group': d['standard']['group'], 'std_lab': lab['standard'].tolist(),
               'std_hue': float(core.hue_deg(lab['standard'])), 'std_C': float(core.chroma(lab['standard']))}
        for m in ('positive', 'negative'):
            rec[m] = {'chroma_ratio': float(core.chroma(lab[m]) / max(core.chroma(lab['standard']), 1e-6)),
                      'hue_shift': float(core.wrap180(core.hue_deg(lab[m]) - core.hue_deg(lab['standard']))),
                      'dL': float(lab[m][0] - lab['standard'][0])}
        out.append(rec)
    return out


def main():
    tone = json.loads((LOCAL / 'tone_curves.json').read_text())
    c4 = np.array(tone['radial']['gr4_coef_natural_log'])
    c3 = np.array(tone['radial']['gr3_coef_natural_log'])
    fr = {k: frame(k, c4) for k in ('hdf_std', 'hdf_pos', 'hdf_neg', 'positive', 'negative')}
    fr3 = {k: frame(k, c3, PUBLIC_CACHE) for k in ('gr3chart_std', 'gr3chart_pos', 'gr3chart_neg')}
    out = {'definitions': __doc__, 'U_MID': U_MID}
    out['vs_standard_B'] = {}
    for mode in ('pos', 'neg'):
        rows = vs_standard(fr['hdf_std'], fr[f'hdf_{mode}'])
        out['vs_standard_B'][mode] = {'bins': rows, 'by_hue': summarise_bins(rows)}
    out['vs_standard_gr3_chart_image'] = {}
    for mode in ('pos', 'neg'):
        rows = vs_standard(fr3['gr3chart_std'], fr3[f'gr3chart_{mode}'])
        out['vs_standard_gr3_chart_image'][mode] = {'by_hue': summarise_bins(rows)}
    out['vs_raw'] = {k: vs_raw(v) for k, v in {**fr, **fr3}.items()}
    out['grey_axis'] = {
        'B_negative': grey_axis(fr['hdf_std'], fr['hdf_neg']),
        'B_positive': grey_axis(fr['hdf_std'], fr['hdf_pos']),
        'A_negative': grey_axis(None, fr['negative']),
        'A_positive': grey_axis(None, fr['positive']),
        'gr3_chart_negative': grey_axis(fr3['gr3chart_std'], fr3['gr3chart_neg']),
    }
    table = gr3_chart_groups()
    # Scene hue of each GR III patch (same DNG model and WHITE_Y as above),
    # then the GR IV body-B mode-vs-Standard bins at that scene hue.
    import csv
    pair3 = gr4io.load_pair(None, None, cache_name='gr3chart_std', cache_dir=PUBLIC_CACHE)
    m3, _ = cm.dng_camera_to_xyz(gr4io.dng_tags_for_colour(pair3))
    be3 = 2.0 ** float(pair3['baseline_exposure'])
    cam = {r['patch']: np.array([float(r['camera_R']), float(r['camera_G']), float(r['camera_B'])])
           for r in csv.DictReader((HERE.parent / 'color_references' / 'gr3_chart_targets.csv').open())
           if r['mode'] == 'standard'}
    for rec in table:
        lab = core.scene_lab((m3 @ cam[rec['patch']]) * be3, WHITE_Y)
        rec['scene_lab_dng'] = lab.tolist()
        rec['scene_hue'] = float(core.hue_deg(lab))
        hb = int(np.digitize(rec['scene_hue'], HUE_EDGES) - 1)
        for mode in ('pos', 'neg'):
            rows = [r for r in out['vs_standard_B'][mode]['bins'] if r['hue_bin'] == hb]
            if rows:
                w = np.array([min(r['n_std'], r['n_mode']) for r in rows], float)
                rec[f'gr4_B_{mode}'] = {'bins': len(rows), 'blocks': int(w.sum()),
                                        'chroma_ratio': float(np.average([r['chroma_ratio'] for r in rows], weights=w)),
                                        'hue_shift': float(np.average([r['hue_shift'] for r in rows], weights=w))}
    out['gr3_patch_table'] = table
    (LOCAL / 'colour.json').write_text(json.dumps(out, indent=1))
    print('written')


if __name__ == '__main__':
    main()
