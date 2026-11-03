"""Q4a: on today's street frames, how much of our 01/02 gap is tone (brightness curve) vs colour?

Counterfactuals applied to our in-camera JPEG (aligned 1/4 grid), all scored against the GR IV model frame:
  L_offset : add one constant to L (matched on mid-grey)            -> 'just brighten it'
  L_curve  : monotone 1-D curve on L fitted on this frame             -> best a global tone curve can do
  L_curve+hue24 : plus per-hue chroma gain and hue rotation (24 sectors) fitted on this frame
These are in-sample upper bounds on one frame (电脑预测, optimistic), not camera results.
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from scipy import ndimage


def prep(slot):
    d = dict(np.load(LOCAL / f'render/aligned_{slot}.npz'))
    ok = np.isfinite(d['std']).all(-1)
    sm = {k: ndimage.gaussian_filter(np.nan_to_num(d[k]), (1.2, 1.2, 0)) for k in ('actual', 'std', 'pred')}
    L = {k: lab(v.reshape(-1, 3)).reshape(v.shape) for k, v in sm.items()}
    g = np.maximum(*(np.hypot(ndimage.sobel(L[k][..., 0], 0), ndimage.sobel(L[k][..., 0], 1)) for k in ('actual', 'std')))
    ok &= g < np.percentile(g[ok], 60)
    ok &= ndimage.binary_erosion(np.isfinite(d['std']).all(-1), iterations=6)
    ok &= np.abs(L['actual'][..., 0] - L['pred'][..., 0]) < 25
    return L['std'][ok], L['actual'][ok], L['pred'][ok]


def curve(x, y, knots=np.linspace(0, 100, 21)):
    # binned median offsets, forced monotone, linear interpolation
    v = []
    for lo, hi in zip(knots[:-1], knots[1:]):
        m = (x >= lo) & (x < hi)
        v.append(np.median(y[m] - x[m]) if m.sum() > 50 else np.nan)
    v = np.array(v); c = (knots[:-1] + knots[1:]) / 2
    good = np.isfinite(v)
    yk = np.maximum.accumulate(c[good] + v[good])  # keep the curve monotone
    return np.interp(x, c[good], yk)


def hue24(src, dst):
    out = src.copy()
    _, Cs, hs = lch(src); _, Cd, hd = lch(dst)
    sec = (hs // 15).astype(int) % 24
    col = (Cs > 6) & (Cd > 6)
    for k in range(24):
        m = sec == k
        mm = m & col
        if mm.sum() < 50:
            continue
        gain = np.median(Cd[mm] / Cs[mm]); rot = np.radians(np.median((hd[mm] - hs[mm] + 180) % 360 - 180))
        z = (src[m, 1] + 1j * src[m, 2]) * gain * np.exp(1j * rot)
        out[m, 1], out[m, 2] = z.real, z.imag
    return out


def main():
    res = {}
    for slot in ('01', '02'):
        std, ours, model = prep(slot)
        base = de(std, model)
        rows = dict(as_shot=de(ours, model))
        neutral = lch(ours)[1] < 8
        off = np.median(model[neutral, 0] - ours[neutral, 0])
        a = ours.copy(); a[:, 0] += off; rows['L_offset'] = de(a, model)
        b = ours.copy(); b[:, 0] = curve(ours[:, 0], model[:, 0]); rows['L_curve'] = de(b, model)
        c = hue24(b, model); rows['L_curve+hue24'] = de(c, model)
        res[slot] = dict(L_offset_value=float(off), **{k: score(v, base) for k, v in rows.items()})
        print(slot, 'offset', round(float(off), 2), {k: (round(v['error']['median'], 2), round(100 * v['S_median'], 1)) for k, v in res[slot].items() if isinstance(v, dict)}, flush=True)
    dump(LOCAL / 'q4_street_whatif.json', res)


if __name__ == '__main__':
    main()
