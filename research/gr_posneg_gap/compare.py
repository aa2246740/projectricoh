"""Q1b: region-by-region gap between our in-camera 01/02 and the GR IV software model, plus visual boards."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from scipy import ndimage
from PIL import ImageDraw, ImageFont

FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'
NAMES = {'01': 'GR 正片', '02': 'GR 负片'}


def font(size):
    return ImageFont.truetype(FONT, size)


def hue_diff(h1, h2):
    return (h1 - h2 + 180) % 360 - 180


def regions(L, C, h, H):
    rows = np.arange(H)[:, None] * np.ones((1, L.shape[1]))
    top = rows < H * 0.30
    return {
        '天空/亮白背景': top & (L > 78) & (C < 14),
        '偏蓝区（路面/玻璃/路牌）': (h > 215) & (h < 300) & (C > 15),
        '绿植': (h > 95) & (h < 175) & (C > 12),
        '暖色（黄/橙）': (h >= 40) & (h <= 95) & (C > 12),
        '红色': ((h < 40) | (h > 330)) & (C > 15),
        '中性灰（路面等）': (C < 8) & (L > 25) & (L < 78),
        '高光 L>80': L > 80,
        '阴影 L<25': L < 25,
    }


def describe(std, act, pred, mask):
    """Medians of per-pixel differences inside mask. All Lab D65."""
    Ls, Cs, hs = lch(std[mask]); La, Ca, ha = lch(act[mask]); Lp, Cp, hp = lch(pred[mask])
    w = np.minimum(Ca, Cp) > 6  # hue only where both have colour
    out = dict(n=int(mask.sum()),
               dE00_ours_vs_model=float(np.median(de(act[mask], pred[mask]))),
               dE00_04_vs_model=float(np.median(de(std[mask], pred[mask]))),
               L=dict(std=float(np.median(Ls)), ours=float(np.median(La)), model=float(np.median(Lp))),
               C=dict(std=float(np.median(Cs)), ours=float(np.median(Ca)), model=float(np.median(Cp))),
               hue_ours_minus_model=float(np.median(hue_diff(ha[w], hp[w]))) if w.sum() > 20 else None,
               hue_model_minus_std=float(np.median(hue_diff(hp[w], hs[w]))) if w.sum() > 20 else None,
               hue_ours_minus_std=float(np.median(hue_diff(ha[w], hs[w]))) if w.sum() > 20 else None,
               a_b=dict(std=np.median(std[mask][:, 1:], 0).tolist(), ours=np.median(act[mask][:, 1:], 0).tolist(),
                        model=np.median(pred[mask][:, 1:], 0).tolist()),
               mean_rgb=dict(std=rgb(np.median(std[mask], 0)[None])[0].tolist(),
                             ours=rgb(np.median(act[mask], 0)[None])[0].tolist(),
                             model=rgb(np.median(pred[mask], 0)[None])[0].tolist()))
    out['dS_ours_minus_model_pct'] = 100 * (out['C']['ours'] / max(out['C']['model'], 1e-6) - 1)
    return out


def tone(std, act, pred, ok):
    Ls = std[..., 0][ok]; La = act[..., 0][ok]; Lp = pred[..., 0][ok]
    bins = np.arange(0, 101, 10); rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (Ls >= lo) & (Ls < hi)
        if m.sum() > 200:
            rows.append(dict(L04=[lo, hi], n=int(m.sum()), ours=float(np.median(La[m])), model=float(np.median(Lp[m])),
                             std=float(np.median(Ls[m]))))
    pc = lambda v: [float(np.percentile(v, q)) for q in (5, 25, 50, 75, 95)]
    return dict(bins=rows, L_percentiles_5_25_50_75_95=dict(std=pc(Ls), ours=pc(La), model=pc(Lp)),
                spread_p95_minus_p5=dict(std=pc(Ls)[4] - pc(Ls)[0], ours=pc(La)[4] - pc(La)[0], model=pc(Lp)[4] - pc(Lp)[0]))


def label(img, text, size=34):
    im = Image.fromarray(img) if isinstance(img, np.ndarray) else img
    d = ImageDraw.Draw(im)
    f = font(size)
    box = d.textbbox((0, 0), text, font=f)
    d.rectangle([0, 0, box[2] + 24, box[3] + 18], fill=(0, 0, 0))
    d.text((12, 6), text, font=f, fill=(255, 255, 255))
    return im


def full_board(slot, frame):
    src = ROOT / 'captures/street-g137-20261031/jpg'
    model = 'pos' if slot == '01' else 'neg'
    a = Image.open(src / 'R8051533.JPG').resize((1430, 950), Image.LANCZOS)
    b = Image.open(src / f'{frame}.JPG').resize((1430, 950), Image.LANCZOS)
    c = Image.open(CAPS / f'R8051533_04_to_GRIV_{model}_model17.jpg').resize((1430, 950), Image.LANCZOS)
    tiles = [label(a, '① GXR 04 标准（机内，模型输入）'), label(b, f'② 我们的 {slot} {NAMES[slot]}（机内实拍）'),
             label(c, f'③ GR IV 原生{NAMES[slot][3:]}应有的样子（电脑预测）')]
    W = sum(t.width for t in tiles) + 20
    board = Image.new('RGB', (W, 950), (255, 255, 255)); x = 0
    for t in tiles:
        board.paste(t, (x, 0)); x += t.width + 10
    board.save(CAPS / f'board_{slot}_full_side_by_side.jpg', quality=90)
    # Stacked portrait version for phones: ② over ③
    pb = Image.new('RGB', (1430, 950 * 2 + 10), (255, 255, 255))
    pb.paste(tiles[1], (0, 0)); pb.paste(tiles[2], (0, 960))
    pb.save(CAPS / f'phone_{slot}_ours_vs_GRIV.jpg', quality=90)


def swatch_board(slot, reg):
    rows = [(k, v) for k, v in reg.items() if v['n'] > 300]
    cell, lw = 150, 330
    im = Image.new('RGB', (lw + 3 * cell + 40 + 560, 90 + len(rows) * (cell + 12)), (250, 250, 250))
    d = ImageDraw.Draw(im); f = font(28); fs = font(24)
    for i, t in enumerate(['04 标准', f'我们的{slot}', 'GR IV 应有']):
        d.text((lw + i * (cell + 10) + 10, 30), t, font=f, fill=(0, 0, 0))
    d.text((lw + 3 * (cell + 10) + 20, 30), '差在哪（我们 - GR IV）', font=f, fill=(0, 0, 0))
    for r, (k, v) in enumerate(rows):
        y = 90 + r * (cell + 12)
        d.text((10, y + cell // 2 - 30), k, font=f, fill=(0, 0, 0))
        d.text((10, y + cell // 2 + 8), f'色差 {v["dE00_ours_vs_model"]:.1f}', font=fs, fill=(90, 90, 90))
        for i, key in enumerate(('std', 'ours', 'model')):
            c = tuple(int(np.clip(z, 0, 255)) for z in v['mean_rgb'][key])
            d.rectangle([lw + i * (cell + 10), y, lw + i * (cell + 10) + cell, y + cell], fill=c)
        dl = v['L']['ours'] - v['L']['model']; dc = v['dS_ours_minus_model_pct']; dh = v['hue_ours_minus_model']
        da, db = (np.array(v['a_b']['ours']) - np.array(v['a_b']['model'])).tolist()
        txt = [f'亮度 {dl:+.1f}', f'饱和度 {dc:+.0f}%' if v['C']['model'] >= 8 else f'彩度 {v["C"]["ours"] - v["C"]["model"]:+.1f}']
        tint = [w for w, c in ((('偏品红' if da > 0 else '偏绿'), abs(da)), (('偏黄' if db > 0 else '偏蓝'), abs(db))) if c >= 1.5]
        txt.append((f'色相 {dh:+.0f}°  ' if dh is not None and v['C']['model'] >= 8 else '') + ('，'.join(tint) or '色调接近'))
        for j, t in enumerate(txt):
            d.text((lw + 3 * (cell + 10) + 20, y + 10 + j * 40), t, font=f, fill=(0, 0, 0))
    im.save(CAPS / f'board_{slot}_region_swatches.jpg', quality=92)


def crop_board(slot, d, ok):
    """Crop strips (aligned, 1/4 scale) of greenery / red / road / sign: 04 | ours | model."""
    src = ROOT / 'captures/street-g137-20261031/jpg'
    al = json.loads((LOCAL / 'render/alignment.json').read_text())['frames'][slot]
    act = jpg(src / f"{al['frame']}.JPG").astype(float)
    full = {'std': jpg(src / 'R8051533.JPG').astype(float),
            'pred': jpg(CAPS / f"R8051533_04_to_GRIV_{'pos' if slot == '01' else 'neg'}_model17.jpg").astype(float)}
    H, W = act.shape[:2]
    crops = {'01': [(0.45, 0.80, 0.22, 0.45), (0.05, 0.40, 0.48, 0.70)],
             '02': [(0.45, 0.85, 0.12, 0.38), (0.05, 0.45, 0.30, 0.55)]}[slot]  # (x0, x1, y0, y1)
    tiles = []
    for (x0, x1, y0, y1) in crops:
        ys, xs = slice(int(y0 * H), int(y1 * H)), slice(int(x0 * W), int(x1 * W))
        k = 4  # alignment was solved on the 1/4 grid: in = s*out + t  ->  full-res t*4
        def warped(img):
            sub = []
            for c in range(3):
                sub.append(ndimage.affine_transform(img[..., c], [al['scale']] * 2, output_shape=(ys.stop - ys.start, xs.stop - xs.start),
                           offset=[al['scale'] * ys.start + k * al['ty'] + (al['scale'] - 1) * 1.5, al['scale'] * xs.start + k * al['tx'] + (al['scale'] - 1) * 1.5],
                           order=1, cval=255))
            return np.stack(sub, -1)
        row = [Image.fromarray(np.clip(v, 0, 255).astype(np.uint8)) for v in (warped(full['std']), act[ys, xs], warped(full['pred']))]
        row = [r.resize((760, int(760 * r.height / r.width)), Image.LANCZOS) for r in row]
        names = ['04 标准', f'我们的 {slot}', 'GR IV 应有（电脑预测）']
        tiles.append([label(r, n, 26) for r, n in zip(row, names)])
    w = 3 * 760 + 20; h = sum(r[0].height for r in tiles) + 10 * len(tiles)
    im = Image.new('RGB', (w, h), (255, 255, 255)); y = 0
    for row in tiles:
        x = 0
        for t in row:
            im.paste(t, (x, y)); x += t.width + 10
        y += row[0].height + 10
    im.save(CAPS / f'board_{slot}_crops_aligned.jpg', quality=92)


def main():
    align = json.loads((LOCAL / 'render/alignment.json').read_text())
    result = {}
    for slot in ('01', '02'):
        d = dict(np.load(LOCAL / f'render/aligned_{slot}.npz'))
        ok = np.isfinite(d['std']).all(-1)
        sm = {k: ndimage.gaussian_filter(np.nan_to_num(d[k]), (1.2, 1.2, 0)) for k in ('actual', 'std', 'pred')}
        L = {k: lab(v.reshape(-1, 3)).reshape(v.shape) for k, v in sm.items()}
        # exclude edges/parallax: strong local structure in either image, or large luminance disagreement
        def grad(x):
            return np.hypot(ndimage.sobel(x, 0), ndimage.sobel(x, 1))
        g = np.maximum(grad(L['actual'][..., 0]), grad(L['std'][..., 0]))
        ok &= g < np.percentile(g[ok], 60)
        ok &= ndimage.binary_erosion(np.isfinite(d['std']).all(-1), iterations=6)
        ok &= np.abs(L['actual'][..., 0] - L['pred'][..., 0]) < 25
        Ls, Cs, hs = lch(L['std'])
        reg = {k: m & ok for k, m in regions(Ls, Cs, hs, Ls.shape[0]).items()}
        stats_r = {k: describe(L['std'], L['actual'], L['pred'], m) for k, m in reg.items() if m.sum() > 50}
        whole = describe(L['std'], L['actual'], L['pred'], ok)
        e_ours = de(L['actual'][ok], L['pred'][ok]); e_04 = de(L['std'][ok], L['pred'][ok])
        result[slot] = dict(frame=align['frames'][slot]['frame'], usable_pixels=int(ok.sum()),
                            whole=whole, scene_score_vs_model=score(e_ours, e_04),
                            tone=tone(L['std'], L['actual'], L['pred'], ok), regions=stats_r,
                            alignment=align['frames'][slot])
        swatch_board(slot, stats_r)
        crop_board(slot, d, ok)
        full_board(slot, align['frames'][slot]['frame'])
        print(slot, json.dumps(dict(S=result[slot]['scene_score_vs_model']['S_median'],
                                    whole=whole['dE00_ours_vs_model']), ensure_ascii=False), flush=True)
        for k, v in stats_r.items():
            print(' ', k, v['n'], 'dE', round(v['dE00_ours_vs_model'], 2), 'L', [round(v['L'][z], 1) for z in ('std', 'ours', 'model')],
                  'C', [round(v['C'][z], 1) for z in ('std', 'ours', 'model')],
                  'h', v['hue_ours_minus_model'] and round(v['hue_ours_minus_model'], 1),
                  'hM-04', v['hue_model_minus_std'] and round(v['hue_model_minus_std'], 1),
                  'hO-04', v['hue_ours_minus_std'] and round(v['hue_ours_minus_std'], 1), flush=True)
        print('  tone', json.dumps(result[slot]['tone']['spread_p95_minus_p5']), flush=True)
    dump(LOCAL / 'q1_street_gap.json', result)


if __name__ == '__main__':
    main()
