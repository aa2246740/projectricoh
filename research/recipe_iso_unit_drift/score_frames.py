"""Per-frame recipe identification and design-vs-camera residual for MOUNT DNG+JPG pairs (g137 rows, ISO200 04 calibration)."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from mount_model import *
import hashlib
DNG = load('drift_dng', 'research/color_table_fit/dng_scene.py')
SESSION = load('drift_session', 'research/chart_session_20261024/session_runtime.py')
SESSION.patch_tiff(DNG.analyze_capture().Tiff)
CAL = json.loads((ROOT / 'research/mount_calib_r1/local/folds/full/calibration.json').read_text())
M, MODS, NAME = mount_model()
SLOTS = ('04', '01', '02', '03', '05', '06', '07', '08')
CAP = ROOT / 'captures/street-g137-20261031'


def predict(slot, x):
    if slot == '03':  # Standard 03: zero colour row; output is the matrix Y row only
        r = M.mm.MatrixRow.from_bytes(M.base.entries['03']['written'][3][:28])
        y = r.apply(M.pre('03', x))[0]
        return np.clip(np.repeat(y[:, None], 3, axis=1), 0, 255)
    return M.predict(slot, x)


def lab(rgb):
    return M.fs.lab_from_codes(np.asarray(rgb, float))


def sample(stem):
    jpg, dngpath = CAP / 'jpg' / (stem + '.JPG'), CAP / 'dng' / (stem + '.DNG')
    d = DNG.Dng(dngpath)
    t = DNG.analyze_capture().Tiff(d.data)
    root = t.ifd(t.root); exif = t.ifd(root[34665]['value'][0])
    rec = t.ifd(exif[37500]['offset'] + 8, '>')[0x1001]['raw']
    meta = dict(frame=stem, iso=exif[34855]['value'][0], t=exif[33434]['value'][0], iso_code=rec[0x27], selector=rec[0x28],
                raw13=list(rec[0x31:0x34] + rec[0x78:0x82]), asn=list(d.as_shot_neutral))
    with Image.open(jpg) as im:
        rgb = np.asarray(im.convert('RGB')); orientation = im.getexif().get(274, 1)
    h, w = rgb.shape[:2]
    mapping = DNG.RawMap(d, (w, h), orientation)
    ver = DNG.verify_mapping(d, rgb, mapping)
    if ver and ver.get('ok') and max(abs(v) for v in ver['suggested_integer_offset_xy']) <= 8:
        mapping = DNG.RawMap(d, (w, h), orientation, ver['suggested_integer_offset_xy'])
    xx, yy = np.meshgrid(np.linspace(48, w - 49, 40).astype(int), np.linspace(48, h - 49, 28).astype(int))
    centers = np.column_stack([xx.ravel(), yy.ravel()])
    dx, dy = np.meshgrid(np.arange(-6, 6), np.arange(-6, 6))
    xs = centers[:, 0, None] + dx.ravel()[None, :]; ys = centers[:, 1, None] + dy.ravel()[None, :]
    blocks = rgb[ys, xs].astype(float); observed, jsd = blocks.mean(1), blocks.std(1)
    cy, cx = mapping.pixels(ys, xs); y0, x0, _, _ = d.crop_window()
    px = d.normalised_at(cy + y0, cx + x0); cfa = d.cfa_at(cy + y0, cx + x0)
    raw = np.column_stack([np.sum(np.where(cfa == k, px, 0), 1) / np.sum(cfa == k, 1) for k in range(3)])
    rawsd = np.column_stack([np.sqrt(np.sum(np.where(cfa == k, (px - raw[:, k, None]) ** 2, 0), 1) / np.sum(cfa == k, 1)) for k in range(3)])
    rawmax = np.column_stack([np.max(np.where(cfa == k, px, -1), 1) for k in range(3)])
    rawwb = raw / d.as_shot_neutral
    # noise grows with ISO: flatness thresholds scale with sqrt(ISO/200)
    k = np.sqrt(max(meta['iso'], 200) / 200)
    valid = ((rawmax < .98).all(1) & (raw > .0005).all(1) & (observed > 3).all(1) & (observed < 252).all(1)
             & (jsd.max(1) < 10 * k) & (rawsd.max(1) < .025 * k))
    centre = (np.abs(centers[:, 0] - w / 2) < w * .35) & (np.abs(centers[:, 1] - h / 2) < h * .35)
    x = calibrate.apply_calibration(rawwb, CAL)
    meta.update(mapping_ok=bool(ver and ver.get('ok')), n_valid=int(valid.sum()), n_centre=int((valid & centre).sum()))
    return meta, dict(x=x[valid], jpeg=observed[valid], centre=centre[valid], raw_wb=rawwb[valid], centers=centers[valid], size=np.array([w, h]))


def score(stem):
    meta, a = sample(stem)
    x, jpeg = a['x'], a['jpeg']
    Lj = lab(jpeg)
    res = {}
    for slot in SLOTS:
        p = predict(slot, x); Lp = lab(p); de = M.de(p, jpeg)
        res[slot] = dict(de_p50=float(np.median(de)), de_p90=float(np.percentile(de, 90)),
                         dL_med=float(np.median(Lj[:, 0] - Lp[:, 0])),
                         dC_med=float(np.median(np.hypot(*Lj[:, 1:].T) - np.hypot(*Lp[:, 1:].T))))
    colour = list(SLOTS) if meta['selector'] != 3 else ['03']  # g137 03 is Standard identity (selector 1), so rank all eight
    rank = sorted(colour, key=lambda s: res[s]['de_p50'])
    out = dict(meta=meta, scores=res, best=rank[0], second=rank[1] if len(rank) > 1 else None,
               margin=(res[rank[1]]['de_p50'] - res[rank[0]]['de_p50']) if len(rank) > 1 else None)
    np.savez_compressed(LOCAL / 'samples' / (stem + '.npz'), **a)
    return out


if __name__ == '__main__':
    (LOCAL / 'samples').mkdir(parents=True, exist_ok=True)
    stems = sys.argv[1:] or sorted(p.stem for p in (CAP / 'dng').glob('*.DNG'))
    allr = {}
    for st in stems:
        r = score(st); allr[st] = r
        sc = r['scores']
        print(st, 'ISO', r['meta']['iso'], 'code', r['meta']['iso_code'], 'sel', r['meta']['selector'], 'n', r['meta']['n_valid'],
              'best', r['best'], round(sc[r['best']]['de_p50'], 2), 'dL', round(sc[r['best']]['dL_med'], 2),
              '| 2nd', r['second'], 'margin', None if r['margin'] is None else round(r['margin'], 2),
              '| 04', round(sc['04']['de_p50'], 2), round(sc['04']['dL_med'], 2), flush=True)
    dump(LOCAL / 'frame_scores.json', allr)
