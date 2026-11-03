"""Q4b: priority re-weighting of a camera-table-like fit (proxy) on the GR IV dense Standard->style data.

Proxy of what GXR tables can express: monotone global L curve (11 knots), luminance depending on colour
direction (2 coefficients, like the Y-row), and 24 hue sectors with chroma gain + hue rotation (linear
interpolation between sector centres). No per-hue lightness, no 3-D freedom. Fitted in Lab, band hold-out.
The absolute % of this proxy is not the real ISP result (real tables: 57-66%); use the *difference*
between uniform and priority weights.
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from scipy.optimize import least_squares
from gr3_vs_gr4 import gr4, family

K = np.linspace(0, 100, 11)


def forward(p, ls):
    L, C, h = lch(ls)
    off = np.concatenate([[0], p[:10]])
    Lo = np.interp(L, K, K + off) + p[10] * ls[:, 1] / 50 + p[11] * ls[:, 2] / 50
    g = p[12:36]; r = p[36:60]
    pos = h / 15 - .5; i0 = np.floor(pos).astype(int) % 24; i1 = (i0 + 1) % 24; f = pos - np.floor(pos)
    gain = np.exp((1 - f) * g[i0] + f * g[i1]); rot = np.radians((1 - f) * r[i0] + f * r[i1])
    z = (ls[:, 1] + 1j * ls[:, 2]) * gain * np.exp(1j * rot)
    if len(p) > 60:  # hypothetical per-hue lightness (not available in GXR tables), scaled by chroma
        q = p[60:84]; Lo = Lo + ((1 - f) * q[i0] + f * q[i1]) * np.minimum(C, 40) / 40
    return np.stack([Lo, z.real, z.imag], 1)


def fit(ls, lt, w, n=60):
    def res(p):
        e = (forward(p, ls) - lt) * np.sqrt(w)[:, None]
        reg = np.concatenate([p[12:36] * 2, p[36:60] * .05, np.minimum(0, np.diff(np.concatenate([[0], p[:10]])) + 10) * 10])
        return np.concatenate([e.ravel(), reg])
    return least_squares(res, np.zeros(n), method='trf', max_nfev=400).x


def weights(ls, mode):
    L, C, h = lch(ls)
    w = np.ones(len(L))
    if mode == 'priority':
        sky = (h >= 220) & (h < 285) & (C >= 8) & (L > 45)
        skin = (h >= 30) & (h < 75) & (C >= 8) & (C < 45) & (L > 40)
        green = (h >= 100) & (h < 170) & (C >= 8)
        w[sky | skin | green] = 4.
    return w


def main():
    res = {}
    for style in ('positive', 'negative'):
        _, _, band, ls, lt = gr4(style)
        base = de(ls, lt)
        L, C, h = lch(ls)
        groups = dict(sky=(h >= 220) & (h < 285) & (C >= 8) & (L > 45), skin=(h >= 30) & (h < 75) & (C >= 8) & (C < 45) & (L > 40),
                      green=(h >= 100) & (h < 170) & (C >= 8))
        groups['other'] = ~(groups['sky'] | groups['skin'] | groups['green'])
        res[style] = {}
        for mode in ('uniform', 'priority', 'uniform+hue_lightness'):
            pred = np.zeros_like(ls)
            for g in np.unique(band):
                m = band == g
                p = fit(ls[~m], lt[~m], weights(ls[~m], mode), 84 if 'hue_lightness' in mode else 60)
                pred[m] = forward(p, ls[m])
            e = de(pred, lt)
            res[style][mode] = dict(all=score(e, base), **{k: score(e[v], base[v]) for k, v in groups.items()})
            print(style, mode, {k: round(100 * v['S_median'], 1) for k, v in res[style][mode].items()}, flush=True)
    dump(LOCAL / 'q4_priority_proxy.json', res)


if __name__ == '__main__':
    main()
