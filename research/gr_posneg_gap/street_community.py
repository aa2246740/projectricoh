"""Q3b: apply the community-style recreations to today's 04 frame and compare with the GR IV model frame.

Both outputs come from the same R8051533 pixels, so no alignment is involved. Our in-camera 01/02 number comes
from compare.py (aligned frames) and is shown alongside.
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from gr3_vs_gr4 import gr4, gr3, rbf_lut
from community import sliders
from PIL import ImageDraw, ImageFont

SRC = ROOT / 'captures/street-g137-20261031/jpg'
FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'


def small(a, k=4):
    h, w = a.shape[0] // k * k, a.shape[1] // k * k
    return a[:h, :w].reshape(h // k, k, w // k, k, -1).mean((1, 3))


def slider_apply(ls4, lt4, img_lab):
    """Re-fit the slider proxy on GR IV dense, then apply the same global ops to an image (Lab)."""
    knots = np.linspace(0, 100, 21); c = (knots[:-1] + knots[1:]) / 2; v = []
    for lo, hi in zip(knots[:-1], knots[1:]):
        m = (ls4[:, 0] >= lo) & (ls4[:, 0] < hi)
        v.append(np.median(lt4[m, 0] - ls4[m, 0]) if m.sum() > 5 else np.nan)
    v = np.array(v); g = np.isfinite(v)
    _, par = sliders(ls4, lt4)
    out = img_lab.copy(); out[:, 0] = np.interp(img_lab[:, 0], c[g], np.maximum.accumulate(c[g] + v[g]))
    z = (img_lab[:, 1] + 1j * img_lab[:, 2]) * par['gain'] * np.exp(1j * np.radians(par['hue_deg']))
    out[:, 1], out[:, 2] = z.real, z.imag
    return out


def main():
    std = jpg(SRC / 'R8051533.JPG')
    q1 = json.loads((LOCAL / 'q1_street_gap.json').read_text())
    res = {}
    for slot, style, name in (('01', 'positive', 'pos'), ('02', 'negative', 'neg')):
        s4, t4, band, ls4, lt4 = gr4(style)
        s3, t3 = gr3(style)
        chart = lut_apply(rbf_lut(s3, t3), std.reshape(-1, 3)).reshape(std.shape)
        chart = np.clip(chart, 0, 255).astype(np.uint8)
        Image.fromarray(chart).save(CAPS / f'R8051533_04_community_chartfit_{name}.jpg', quality=92)
        model = jpg(CAPS / f'R8051533_04_to_GRIV_{name}_model17.jpg')
        sm_std, sm_chart, sm_model = (lab(small(x.astype(float)).reshape(-1, 3)) for x in (std, chart, model))
        sl = slider_apply(ls4, lt4, sm_std)
        base = de(sm_std, sm_model)
        res[slot] = dict(chart_fit_GR3=score(de(sm_chart, sm_model), base), sliders=score(de(sl, sm_model), base),
                         ours_in_camera_aligned=q1[slot]['scene_score_vs_model'])
        print(slot, {k: (round(v['error']['median'], 2), round(100 * v['S_median'], 1)) for k, v in res[slot].items()}, flush=True)
        # board: ours | community chart-fit | GR IV model
        f = ImageFont.truetype(FONT, 34)
        tiles = []
        for path_or_img, txt in ((Image.open(SRC / f"{q1[slot]['frame']}.JPG"), f'① 我们的 {slot}（机内实拍）'),
                                 (Image.fromarray(chart), '② 社区做法：一张色卡拟合的 LUT（电脑）'),
                                 (Image.fromarray(model), '③ GR IV 应有（我们的密集模型，电脑预测）')):
            im = path_or_img.resize((1430, 950), Image.LANCZOS)
            d = ImageDraw.Draw(im); bb = d.textbbox((0, 0), txt, font=f)
            d.rectangle([0, 0, bb[2] + 24, bb[3] + 18], fill=(0, 0, 0)); d.text((12, 6), txt, font=f, fill=(255, 255, 255))
            tiles.append(im)
        board = Image.new('RGB', (1430 * 3 + 20, 950), (255, 255, 255))
        for k, t in enumerate(tiles):
            board.paste(t, (k * 1440, 0))
        board.save(CAPS / f'board_{slot}_ours_vs_community_vs_GRIV.jpg', quality=90)
    dump(LOCAL / 'q3_street_community.json', res)


if __name__ == '__main__':
    main()
