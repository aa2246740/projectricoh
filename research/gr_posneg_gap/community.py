"""Q3: how well can community-style recreations match the GR IV dense target (Standard -> Positive/Negative)?

No licensed community GR Positive/Negative .cube was available (see REPORT). We therefore score the two
recreation *methods* found online, built from data we already hold, on the same GR IV dense pages:
  chart_fit  : LUT fitted from one in-camera ColorChecker shot (bastibe / ColorReps method; GR III Target.DNG).
  sliders    : best global tone curve + one global saturation + one global hue shift (what a slider-only
               preset can express; fitted in-sample on GR IV, so optimistic for hand-tuned presets).
  dense_lut  : our GR IV dense software LUT (RBF), band hold-out (each of the 4 dense bands left out in turn).
Also any .cube files placed in local/cubes/ (data only, parsed, never executed) are scored as Standard -> style.
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from gr3_vs_gr4 import gr4, gr3, rbf_lut, family

FAMS = ['中性', '红', '橙/肤色', '黄', '绿', '青', '蓝', '紫/品红']


def sliders(ls, lt):
    """In-sample best: monotone L curve (21 knots) + global chroma gain + global hue rotation."""
    knots = np.linspace(0, 100, 21); c = (knots[:-1] + knots[1:]) / 2; v = []
    for lo, hi in zip(knots[:-1], knots[1:]):
        m = (ls[:, 0] >= lo) & (ls[:, 0] < hi)
        v.append(np.median(lt[m, 0] - ls[m, 0]) if m.sum() > 5 else np.nan)
    v = np.array(v); g = np.isfinite(v)
    out = ls.copy(); out[:, 0] = np.interp(ls[:, 0], c[g], np.maximum.accumulate(c[g] + v[g]))
    _, Cs, hs = lch(ls); _, Ct, ht = lch(lt); col = (Cs > 8) & (Ct > 8)
    gain = np.median(Ct[col] / Cs[col]); rot = np.radians(np.median((ht[col] - hs[col] + 180) % 360 - 180))
    z = (ls[:, 1] + 1j * ls[:, 2]) * gain * np.exp(1j * rot)
    out[:, 1], out[:, 2] = z.real, z.imag
    return out, dict(gain=float(gain), hue_deg=float(np.degrees(rot)))


def by_family(pred, lt, ls):
    fam = family(ls); out = {}
    for nm in FAMS:
        m = fam == nm
        if m.sum() > 10:
            out[nm] = dict(n=int(m.sum()), **score(de(pred[m], lt[m]), de(ls[m], lt[m])))
    return out


def main():
    res = {}
    cubes = sorted((LOCAL / 'cubes').glob('**/*.cube')) if (LOCAL / 'cubes').exists() else []
    for style in ('positive', 'negative'):
        s4, t4, band, ls4, lt4 = gr4(style)
        base = de(ls4, lt4)
        s3, t3 = gr3(style)
        routes = {}
        # chart fit from GR III ColorChecker, applied to GR IV Standard pixels
        lut3 = rbf_lut(s3, t3)
        p = lab(lut_apply(lut3, s4).astype(float)); routes['chart_fit_GR3'] = p
        # slider-only preset, in-sample
        p, par = sliders(ls4, lt4); routes['sliders_in_sample'] = p
        # dense LUT, band hold-out
        p = np.zeros_like(ls4)
        for g in np.unique(band):
            m = band == g
            lut = rbf_lut(s4[~m], t4[~m])
            p[m] = lab(lut_apply(lut, s4[m]).astype(float))
        routes['dense_LUT_band_holdout'] = p
        for c in cubes:
            if style[:3] not in c.name.lower():
                continue
            nodes, lo, hi = cube_read(c)
            x = (s4 / 255 - lo) / (hi - lo) * 255
            routes['cube:' + c.name] = lab(np.clip(lut_apply(nodes, x) * 255, 0, 255))  # float nodes in 0..1
        res[style] = {}
        for k, p in routes.items():
            res[style][k] = dict(all=score(de(p, lt4), base), family=by_family(p, lt4, ls4))
            if k == 'sliders_in_sample':
                res[style][k]['parameters'] = par
            r = res[style][k]['all']
            print(style, k, 'S', round(100 * r['S_median'], 1), 'dE', round(r['error']['median'], 3), 'base', round(r['baseline']['median'], 3),
                  {nm: round(100 * v['S_median'], 0) for nm, v in res[style][k]['family'].items()}, flush=True)
    dump(LOCAL / 'q3_community_methods.json', res)


if __name__ == '__main__':
    main()
