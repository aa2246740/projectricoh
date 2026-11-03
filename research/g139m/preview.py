"""Computer prediction: MOUNT street frames under the g139 MOUNT table vs the g139m table (50mm rows).

Reuses research/recipe_iso_unit_drift (read-only): its MOUNT UnitModel, the
ISO 200 04 calibration from mount_calib_r1 and the DNG sampler of
score_frames.py. Rows are decoded from the two package DATs directly.

  preview.py [stem ...]          default: R8051530..R8051537 plus 1562, 1627, 1680, 1685

Per frame (recipe = the one identified in the drift study's frame_scores.json):
  - grid metrics (the drift study's 40x28 flat-block grid, local samples):
    model vs camera JPEG under g139 (model check), and g139 -> g139m change in
    median L, chroma and hue, plus each table's offset from the same frame's
    04 prediction;
  - a dense 300x200 rendering of camera JPEG | predicted g139 | predicted g139m.
Writes research/g139m/preview.json and captures/g139m-preview/*.jpg.
All numbers are computer predictions; the camera JPEG column is the only measurement.
/usr/bin/python3 -I -B.
"""
from pathlib import Path
import os
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DRIFT = ROOT / 'research/recipe_iso_unit_drift'
OUT = ROOT / 'captures/g139m-preview'
WORK = HERE / 'local/preview'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g139m/preview')
TMP.mkdir(parents=True, exist_ok=True); WORK.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(DRIFT))
import drift_common as dc  # noqa: E402
dc.LOCAL, dc.TMP = WORK, TMP
os.environ['TMPDIR'] = str(TMP)
import mount_model as mm  # noqa: E402
mm.s.HERE, mm.s.LOCAL = HERE, WORK
import score_frames as sf  # noqa: E402  (builds the g137 MOUNT model on import; g137 MOUNT rows == g139, checked in REPORT)
import json  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

G139 = 'firmware/package_v38_g139/local/SD_ROOT/GXRCE.DAT'
G139M = 'firmware/package_v38_g139m/local/SD_ROOT/GXRCE.DAT'
SCORES = json.loads((DRIFT / 'local/frame_scores.json').read_text())
RECIPE = {'R8051537': '08'}   # 07 and 08 tie on the grid; the shooting order says 08 (drift REPORT 3.2)
NAMES = {'01': 'GR Pos', '02': 'GR Neg', '03': 'HC BW', '04': 'Std', '05': 'F-CC', '06': 'F-CN', '07': 'L-Chr', '08': 'L-Viv'}


def tables(path):
    mods = mm.g137_modules(path)
    name = next(n for n in mods if n.lower().startswith('l08'))
    return mm.entries448(mods[name])


BEFORE, AFTER = tables(G139), tables(G139M)
M = sf.M


def predict(entries, slot, x):
    M.base.entries = entries
    return sf.predict(slot, x)


def lab(rgb):
    return M.fs.lab_from_codes(np.asarray(rgb, float))


def stats(L):
    c = np.hypot(L[:, 1], L[:, 2]); h = np.degrees(np.arctan2(L[:, 2], L[:, 1]))
    return float(np.median(L[:, 0])), float(np.median(c)), h, c


def grid_metrics(stem, slot):
    a = np.load(DRIFT / 'local/samples' / (stem + '.npz'))
    x, jpeg = a['x'], a['jpeg']
    pb, pa = predict(BEFORE, slot, x), predict(AFTER, slot, x)
    p4 = predict(BEFORE, '04', x)
    Lj, Lb, La, L4 = lab(jpeg), lab(pb), lab(pa), lab(p4)
    Lmj, Cj, _, _ = stats(Lj); Lmb, Cb, hb, cb = stats(Lb); Lma, Ca, ha, ca = stats(La); Lm4, C4, _, _ = stats(L4)
    chromatic = (cb > 8) & (ca > 8)
    dh = (ha - hb + 180) % 360 - 180
    return dict(points=int(len(x)),
                model_check=dict(de00_median_g139_vs_camera=float(np.median(M.de(pb, jpeg))),
                                 L_camera=Lmj, L_pred_g139=Lmb),
                L_g139=Lmb, L_g139m=Lma, L_change=float(np.median(La[:, 0] - Lb[:, 0])),
                L_vs_04_g139=float(np.median(Lb[:, 0] - L4[:, 0])), L_vs_04_g139m=float(np.median(La[:, 0] - L4[:, 0])),
                chroma_g139=Cb, chroma_g139m=Ca, chroma_change=float(np.median(ca - cb)),
                hue_change_deg_median=float(np.median(dh[chromatic])) if chromatic.any() else None,
                hue_change_deg_p90_abs=float(np.percentile(np.abs(dh[chromatic]), 90)) if chromatic.any() else None,
                de00_g139_to_g139m=float(np.median(M.de(pb, pa))))


def dense(stem, cols=300, rows=200, half=4):
    """score_frames.sample() on a dense grid, without the flatness filter."""
    jpg, dngpath = sf.CAP / 'jpg' / (stem + '.JPG'), sf.CAP / 'dng' / (stem + '.DNG')
    d = sf.DNG.Dng(dngpath)
    with Image.open(jpg) as im:
        rgb = np.asarray(im.convert('RGB')); orientation = im.getexif().get(274, 1)
    h, w = rgb.shape[:2]
    mapping = sf.DNG.RawMap(d, (w, h), orientation)
    ver = sf.DNG.verify_mapping(d, rgb, mapping)
    if ver and ver.get('ok') and max(abs(v) for v in ver['suggested_integer_offset_xy']) <= 8:
        mapping = sf.DNG.RawMap(d, (w, h), orientation, ver['suggested_integer_offset_xy'])
    if h > w:
        cols, rows = rows, cols
    xx, yy = np.meshgrid(np.linspace(half, w - half - 1, cols).astype(int), np.linspace(half, h - half - 1, rows).astype(int))
    centers = np.column_stack([xx.ravel(), yy.ravel()])
    dx, dy = np.meshgrid(np.arange(-half, half), np.arange(-half, half))
    xs = centers[:, 0, None] + dx.ravel()[None, :]; ys = centers[:, 1, None] + dy.ravel()[None, :]
    observed = rgb[ys, xs].astype(float).mean(1)
    cy, cx = mapping.pixels(ys, xs); y0, x0, _, _ = d.crop_window()
    px = d.normalised_at(cy + y0, cx + x0); cfa = d.cfa_at(cy + y0, cx + x0)
    raw = np.column_stack([np.sum(np.where(cfa == k, px, 0), 1) / np.maximum(np.sum(cfa == k, 1), 1) for k in range(3)])
    x = sf.calibrate.apply_calibration(np.maximum(raw, 1e-6) / d.as_shot_neutral, sf.CAL)
    return observed.reshape(rows, cols, 3), x, (rows, cols)


def panel(stem, slot):
    observed, x, shape = dense(stem)
    before = np.clip(predict(BEFORE, slot, x), 0, 255).reshape(*shape, 3)
    after = np.clip(predict(AFTER, slot, x), 0, 255).reshape(*shape, 3)
    tiles = [observed, before, after]
    labels = [f'{stem[-4:]} {slot} {NAMES[slot]}: camera (g137 = g139)', 'pred g139 MOUNT table', 'pred g139m (50mm rows)']
    gap, top = 6, 18
    out = Image.new('RGB', (3 * shape[1] + 2 * gap, shape[0] + top), (24, 24, 24))
    draw = ImageDraw.Draw(out)
    for i, (t, label) in enumerate(zip(tiles, labels)):
        out.paste(Image.fromarray(np.round(t).astype(np.uint8)), (i * (shape[1] + gap), top))
        draw.text((i * (shape[1] + gap) + 4, 3), label, fill=(235, 235, 235))
    return out


def main():
    stems = sys.argv[1:] or [f'R805{n}' for n in (1530, 1531, 1532, 1533, 1534, 1535, 1536, 1537, 1562, 1627, 1680, 1685)]
    OUT.mkdir(parents=True, exist_ok=True)
    result, sheet = {}, []
    for stem in stems:
        slot = RECIPE.get(stem, SCORES[stem]['best'])
        meta = SCORES[stem]['meta']
        result[stem] = dict(recipe=slot, iso=meta['iso'], **grid_metrics(stem, slot))
        img = panel(stem, slot)
        img.save(OUT / f'{stem}-{slot}.jpg', quality=90)
        if stem in ('R8051530', 'R8051531', 'R8051532', 'R8051533', 'R8051534', 'R8051535', 'R8051536', 'R8051537'):
            sheet.append(img)
        r = result[stem]
        print(stem, slot, 'ISO', meta['iso'], 'model dE', round(r['model_check']['de00_median_g139_vs_camera'], 2),
              'L', round(r['L_g139'], 1), '->', round(r['L_g139m'], 1), 'vs04', round(r['L_vs_04_g139'], 1), '->',
              round(r['L_vs_04_g139m'], 1), 'C', round(r['chroma_g139'], 1), '->', round(r['chroma_g139m'], 1),
              'hue', r['hue_change_deg_median'] and round(r['hue_change_deg_median'], 1), flush=True)
    if sheet:
        width = max(i.width for i in sheet)
        full = Image.new('RGB', (width, sum(i.height + 4 for i in sheet)), (24, 24, 24))
        y = 0
        for i in sheet:
            full.paste(i, (0, y)); y += i.height + 4
        full.save(OUT / 'sheet_1530_1537.jpg', quality=88)
    (HERE / 'preview.json').write_text(json.dumps(dict(
        note='computer prediction (MOUNT UnitModel of research/recipe_iso_unit_drift, ISO 200 04 calibration, '
             '50mm response kernel); camera = measured g137 JPEG; g137 MOUNT rows == g139', frames=result),
        indent=1, default=float) + '\n')


if __name__ == '__main__':
    main()
