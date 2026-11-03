"""Q2: is the GR III Positive/Negative look the same transform as the GR IV one?

GR IV: dense chart, same RAW developed in-camera as Standard / Positive / Negative (8,685 regions per page).
GR III: bastibe Target.DNG developed in-camera as Standard / Positive / Negative (one ColorChecker scene).
Both give a measured Standard->Style function on the same body; we compare the two functions where colours overlap.
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import cKDTree
from scipy.linalg import cho_factor, cho_solve
from scipy.spatial.distance import cdist
from PIL import ImageDraw, ImageFont

DENSE = {'positive': ROOT / 'research/gr4_dense_returns_r1/local/target/paired_measurements.npz',
         'negative': ROOT / 'research/gr4_nega_returns_r1/local/target/paired_measurements.npz'}
GR3 = ROOT / 'research/gr_pairs/local/samples'
GR3JPG = ROOT / 'artifacts/downloads/bastibe-gr3/downloads'
SCALE = np.array([20., 30., 30.])
FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'
ZH = {'positive': '正片', 'negative': '负片'}


class Function:
    """Piecewise-linear measured function with the same no-extrapolation rule as gr4_lut_ceiling/style.py."""
    def __init__(self, x, y):
        xx, inv = np.unique(np.round(x, 9), axis=0, return_inverse=True)
        cnt = np.bincount(inv)
        yy = np.column_stack([np.bincount(inv, weights=y[:, k]) / cnt for k in range(y.shape[1])])
        self.f = LinearNDInterpolator(xx, yy); self.tree = cKDTree(xx)

    def __call__(self, x):
        y = self.f(x); d = self.tree.query(x)[0]
        return y, np.isfinite(y).all(1) & (d <= 1.)


def gr4(style):
    d = np.load(DENSE[style])
    a, b = d['standard_rgb'] * 255., d[f'{style}_rgb'] * 255.  # stored as encoded sRGB 0..1
    return a, b, d['band'], d['standard'], d[style]


def gr3(style):
    s = np.load(GR3 / 'bastibe_standard.npz'); t = np.load(GR3 / f'bastibe_{style}.npz')
    ks = {tuple(v): i for i, v in enumerate(s['xy'])}
    pairs = [(ks[tuple(v)], j) for j, v in enumerate(t['xy']) if tuple(v) in ks]
    i, j = np.array(pairs).T
    cell = s['cell'][i]
    a, b = s['jpeg'][i].astype(float), t['jpeg'][j].astype(float)
    # one sample per grid cell (median), so neighbouring pixels are not counted as independent colours
    uc = np.unique(cell)
    A = np.array([np.median(a[cell == c], 0) for c in uc]); B = np.array([np.median(b[cell == c], 0) for c in uc])
    ok = (A > 3).all(1) & (A < 252).all(1) & (B > 3).all(1) & (B < 252).all(1)
    return A[ok], B[ok]


def rbf_lut(x, y, n=33, width=48., ridge=.03):
    xx, inv = np.unique(np.round(x, 3), axis=0, return_inverse=True)
    cnt = np.bincount(inv); yy = np.column_stack([np.bincount(inv, weights=y[:, k]) / cnt for k in range(3)])
    K = np.exp(-cdist(xx, xx, 'sqeuclidean') / (2 * width ** 2))
    alpha = cho_solve(cho_factor(K + ridge * np.eye(len(xx)), lower=True), yy - xx)
    g = np.stack(np.meshgrid(*([np.linspace(0, 255, n)] * 3), indexing='ij'), -1).reshape(-1, 3)
    out = np.empty_like(g)
    for s in range(0, len(g), 4096):
        q = g[s:s + 4096]
        out[s:s + 4096] = q + np.exp(-cdist(q, xx, 'sqeuclidean') / (2 * width ** 2)) @ alpha
    return np.clip(out, 0, 255).reshape(n, n, n, 3)


def family(labs):
    L, C, h = lch(labs)
    names = np.full(len(L), '其他', dtype=object)
    names[C < 8] = '中性'
    col = C >= 8
    for lo, hi, nm in ((330, 360, '红'), (0, 40, '红'), (40, 75, '橙/肤色'), (75, 105, '黄'), (105, 170, '绿'),
                       (170, 230, '青'), (230, 300, '蓝'), (300, 330, '紫/品红')):
        names[col & (h >= lo) & (h < hi)] = nm
    return names


def moves(std, sty):
    Ls, Cs, hs = lch(std); Lt, Ct, ht = lch(sty)
    col = (Cs >= 8) & (Ct >= 8)
    return dict(dL=float(np.median(Lt - Ls)),
                dC_pct=float(100 * np.median(Ct[col] / Cs[col] - 1)) if col.sum() > 2 else None,
                dh=float(np.median((ht[col] - hs[col] + 180) % 360 - 180)) if col.sum() > 2 else None)


def main():
    out = {}
    (LOCAL / 'gr3_vs_gr4').mkdir(parents=True, exist_ok=True)
    for style in ('positive', 'negative'):
        s4, t4, band, ls4, lt4 = gr4(style)
        s3, t3 = gr3(style)
        ls3, lt3 = lab(s3), lab(t3)
        f4 = Function(ls4 / SCALE, lt4); f3 = Function(ls3 / SCALE, lt3)
        # (a) GR IV function applied to GR III Standard colours, inside GR IV measured support
        p, ok = f4(ls3 / SCALE)
        e_a = de(p[ok], lt3[ok]); b_a = de(ls3[ok], lt3[ok])
        # (b) GR III function applied to GR IV dense Standard colours, inside GR III measured support
        q, ok2 = f3(ls4 / SCALE)
        e_b = de(q[ok2], lt4[ok2]); b_b = de(ls4[ok2], lt4[ok2])
        # reference: GR IV against itself (band hold-out), so "same look" has a noise floor to compare with
        e_self, b_self = [], []
        for g in np.unique(band):
            ff = Function(ls4[band != g] / SCALE, lt4[band != g])
            pp, oo = ff(ls4[band == g] / SCALE)
            e_self.extend(de(pp[oo], lt4[band == g][oo])); b_self.extend(de(ls4[band == g][oo], lt4[band == g][oo]))
        fam3 = family(ls3)
        per = {}
        for nm in ['中性', '红', '橙/肤色', '黄', '绿', '青', '蓝', '紫/品红']:
            m = fam3 == nm
            mm = m & ok
            per[nm] = dict(n_gr3=int(m.sum()), n_supported=int(mm.sum()),
                           gr3_move=moves(ls3[m], lt3[m]) if m.sum() > 2 else None,
                           gr4_move_same_colours=moves(ls3[mm], p[mm]) if mm.sum() > 2 else None,
                           dE_gr4fn_vs_gr3=float(np.median(de(p[mm], lt3[mm]))) if mm.sum() else None)
        fam4 = family(ls4)
        per4 = {nm: moves(ls4[fam4 == nm], lt4[fam4 == nm]) for nm in ['中性', '红', '橙/肤色', '黄', '绿', '青', '蓝', '紫/品红'] if (fam4 == nm).sum() > 5}
        Lp = lambda v: [float(np.percentile(v[:, 0], q)) for q in (5, 50, 95)]
        out[style] = dict(
            gr4_fn_on_gr3=dict(supported=int(ok.sum()), of=len(ok), **score(e_a, b_a)),
            gr3_fn_on_gr4=dict(supported=int(ok2.sum()), of=len(ok2), **score(e_b, b_b)),
            gr4_self_band_holdout=score(e_self, b_self),
            gr3_overall_move=moves(ls3, lt3), gr4_overall_move=moves(ls4, lt4),
            gr3_neutral_L_curve=dict(std=Lp(ls3[fam3 == '中性']), style=Lp(lt3[fam3 == '中性'])),
            per_family_gr3_colours=per, gr4_dense_per_family=per4)
        print(style, json.dumps({k: (v if not isinstance(v, dict) or 'S_median' not in v else dict(S=v['S_median'], e=v['error']['median'], b=v['baseline']['median'], n=v['error']['n'])) for k, v in out[style].items() if k.startswith(('gr4_fn', 'gr3_fn', 'gr4_self', 'gr3_overall', 'gr4_overall'))}, ensure_ascii=False), flush=True)
        for nm, v in per.items():
            print('  ', nm, v['n_gr3'], v['n_supported'], v['gr3_move'], v['gr4_move_same_colours'], v['dE_gr4fn_vs_gr3'], flush=True)
        print('  GR IV dense per family', per4, flush=True)
        # Full-range sRGB Standard->Style LUT from the GR IV dense data (identity-regularised outside support)
        lut = rbf_lut(s4, t4)
        np.savez_compressed(LOCAL / f'gr3_vs_gr4/gr4_std_to_{style}_rgb33.npz', nodes=lut)
        std_img = jpg(GR3JPG / 'bastibe_gr3_standard/standard.JPG')
        real = jpg(GR3JPG / f'bastibe_gr3_{style}/{style}.JPG')
        sim = lut_apply(lut, std_img.reshape(-1, 3)).reshape(std_img.shape).astype(np.uint8)
        f = ImageFont.truetype(FONT, 46)
        tiles = []
        for img, txt in ((std_img, 'GR III 标准（真机）'), (real, f'GR III {ZH[style]}（真机）'),
                         (sim, f'GR IV {ZH[style]}变换套在 GR III 标准上')):
            im = Image.fromarray(img).crop((600, 1100, 4800, 4000)).resize((1400, 967), Image.LANCZOS)
            dr = ImageDraw.Draw(im); bb = dr.textbbox((0, 0), txt, font=f)
            dr.rectangle([0, 0, bb[2] + 30, bb[3] + 20], fill=(0, 0, 0)); dr.text((14, 6), txt, font=f, fill=(255, 255, 255))
            tiles.append(im)
        board = Image.new('RGB', (1400 * 3 + 20, 967), (255, 255, 255))
        for k, t in enumerate(tiles):
            board.paste(t, (k * 1410, 0))
        board.save(CAPS / f'board_GR3_vs_GR4_{style}.jpg', quality=90)
    dump(LOCAL / 'q2_gr3_vs_gr4.json', out)


if __name__ == '__main__':
    main()
