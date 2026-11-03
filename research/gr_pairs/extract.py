"""Build aligned, flatness-weighted CFA-quad/JPEG pairs, without network or devices."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, LOCAL, TMP, dump, read, sha, modules, guard, stats, load
import argparse
import io as byteio
import json
import numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter, minimum_filter, maximum_filter, binary_erosion, map_coordinates
from scipy.optimize import minimize


def raw_frame(frame):
    grio, _, meas, tn = modules()
    cache = LOCAL / 'raw' / (sha(ROOT / frame['dng']) + '.npz')
    mdpath = cache.with_suffix('.json')
    if cache.exists():
        with np.load(cache, allow_pickle=False) as z:
            return dict(z), read(mdpath)
    tiff = grio.load_tiff(ROOT / frame['dng'])
    _, _, _, root, _ = tn.maker_note_bytes(tiff)
    raw, _ = meas.raw_subifd(root, tiff)
    geom = meas.dng_geometry(raw, meas.tag_map(root))
    if geom['compression'] == 7:
        work = TMP / frame['id']
        work.mkdir(parents=True, exist_ok=True)
        off, size = geom['strip_offset'], geom['strip_bytes']
        mosaic, decoder = meas.decode_mosaic(grio.lj92_binary(), tiff.data[off:off + size],
                                             (geom['width'], geom['height']), work)
    else:
        rt = load('pairs_raw_tiff', ROOT / 'research/gr_evalsets/local/vendor/gr_complete_pipeline/reference_tiff_frozen.py')
        mosaic, _ = rt.unpack_raw(rt.Tiff(tiff.data))
        decoder = {'uncompressed': True}
    x0, y0 = geom['crop_origin_xy']
    w, h = geom['crop_size_wh']
    assert geom['cfa_pattern'] == [0, 1, 1, 2] and x0 % 2 == y0 % 2 == 0
    crop = mosaic[y0:y0 + h, x0:x0 + w]
    rgb, clip = grio.camera_rgb_half(crop, geom)
    raw3 = np.stack([crop[0::2, 0::2], crop[0::2, 1::2].astype(np.uint32) + crop[1::2, 0::2],
                     crop[1::2, 1::2]], axis=-1)
    tags = {k: v['value'] for k, v in {**meas.tag_map(root), **raw}.items()}
    tags = {str(k): v for k, v in tags.items() if k in (50714, 50717, 50721, 50722, 50723, 50724,
                                                       50727, 50728, 50730, 50778, 50779, 50931, 50932)}
    md = {'geometry': geom, 'decoder': decoder, 'tags': tags, 'source_sha256': sha(ROOT / frame['dng'])}
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, rgb=rgb, clip=clip, raw3=raw3)
    dump(mdpath, md)
    return {'rgb': rgb, 'clip': clip, 'raw3': raw3}, md


def camera_jpeg(frame):
    grio, _, meas, tn = modules()
    if frame['jpg'] is None:
        tiff = grio.load_tiff(ROOT / frame['dng'])
        _, _, _, root, _ = tn.maker_note_bytes(tiff)
        candidates = []
        for entries in meas.subifds(tiff, root):
            tags = meas.tag_map(entries)
            if meas.scalar(tags.get(259)) == 7 and meas.scalar(tags.get(262)) != 32803:
                offset, size = tags[273]['value'][0], tags[279]['value'][0]
                blob = tiff.data[offset:offset + size]
                if blob.startswith(b'\xff\xd8'):
                    candidates.append(blob)
        assert len(candidates) == 1, 'No unique full-resolution camera JPEG'
        source = byteio.BytesIO(candidates[0])
    else:
        source = ROOT / frame['jpg']
    with Image.open(source) as image:
        info = {'size': list(image.size), 'sampling': image.layer,
                'orientation': image.getexif().get(274), 'embedded': frame['jpg'] is None}
        arr = np.asarray(image.convert('RGB'))
    # Decoded RGB has the libjpeg 4:2:2 chroma interpolation. Whole 2x2 means
    # share horizontal chroma pairs; the 5x5 flatness guard removes their edges.
    return grio.half(arr), (arr.reshape(arr.shape[0] // 2, 2, arr.shape[1] // 2, 2, 3).min(axis=(1, 3)) > 2).all(axis=-1) & \
           (arr.reshape(arr.shape[0] // 2, 2, arr.shape[1] // 2, 2, 3).max(axis=(1, 3)) < 253).all(axis=-1), info


def alignment(wb, jpg):
    """Check same-exposure geometry on image-wide and local edge structure."""
    raw = np.log2(np.maximum(wb @ np.array([.25, .5, .25]), 1e-5))
    j = np.log2(np.maximum(jpg @ np.array([.2126, .7152, .0722]), 2))
    raw = uniform_filter(raw, size=3)
    j = uniform_filter(j, size=3)
    gy, gx = np.gradient(raw)
    jy, jx = np.gradient(j)
    # Strong directional edges have the same positions despite different tone curves.
    mag = np.hypot(gy, gx)
    hh, ww = mag.shape
    out = []
    for by in range(4):
        for bx in range(6):
            y0, y1 = int((by + .1) * hh / 4), int((by + .9) * hh / 4)
            x0, x1 = int((bx + .1) * ww / 6), int((bx + .9) * ww / 6)
            yy, xx = np.mgrid[y0:y1:5, x0:x1:5]
            yy, xx = yy.ravel(), xx.ravel()
            m = mag[yy, xx]
            use = (m > max(.015, np.percentile(m, 65))) & (m < 1.0)
            yy, xx = yy[use], xx[use]
            if len(yy) < 50:
                continue
            aa = np.stack([gy[yy, xx], gx[yy, xx]], axis=-1)
            aa /= np.linalg.norm(aa, axis=-1)[:, None]
            def loss(shift):
                bb = np.stack([map_coordinates(v, [yy + shift[0], xx + shift[1]], order=1)
                               for v in (jy, jx)], axis=-1)
                norm = np.linalg.norm(bb, axis=-1)
                dot = (aa * bb).sum(axis=-1) / np.maximum(norm, 1e-10)
                return -float(np.mean(np.clip(dot, -1, 1)))
            initial = min((loss((dy, dx)), dy, dx) for dy in (-1., 0., 1.) for dx in (-1., 0., 1.))
            fit = minimize(loss, initial[1:], method='Powell', bounds=[(-2., 2.), (-2., 2.)],
                           options={'maxiter': 12, 'xtol': .015, 'ftol': 1e-5})
            out.append({'tile': [by, bx], 'dy': float(fit.x[0]), 'dx': float(fit.x[1]), 'score': -float(fit.fun)})
    good = [q for q in out if q['score'] > .6]
    if not good:
        return {'tiles': out, 'n': 0, 'geometry_confirmed': False}
    offsets = np.array([[q['dy'], q['dx']] for q in good])
    norms = np.linalg.norm(offsets, axis=1)
    med = np.median(offsets, axis=0)
    return {'tiles': out, 'n': len(good), 'median_offset_half': med, 'offset_length_half': stats(norms),
            'geometry_confirmed': bool(np.linalg.norm(med) < .4 and np.percentile(norms, 90) < .8),
            'resampling': False, 'unit': 'one half pixel = one 2x2 sensor quad'}


def feature(uc):
    uc = np.maximum(uc, 1e-7)
    u = uc @ np.array([.25, .5, .25])
    return np.stack([np.log2(u), np.log2(uc[..., 0] / uc[..., 1]),
                      np.log2(uc[..., 2] / uc[..., 1])], axis=-1)


def bins(lab):
    C = np.hypot(lab[..., 1], lab[..., 2])
    hue = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360
    h = (hue // 30).astype(int)
    l = np.digitize(lab[..., 0], [20, 40, 60, 80])
    c = np.digitize(C, [8, 25])
    return (h * 5 + l) * 3 + c


def extract(frame, cap=60000):
    grio, cm, _, _ = modules()
    raw, md = raw_frame(frame)
    tags = {int(k): v for k, v in md['tags'].items()}
    rgb = raw['rgb']
    jpg, jpeg_valid, ji = camera_jpeg(frame)
    assert jpg.shape == rgb.shape, (frame['id'], jpg.shape, rgb.shape)
    be = tags.get(50730, [0.])[0]
    wb = rgb / np.asarray(tags[50728], np.float32) * np.float32(2 ** be)
    radial = read(ROOT / 'research/gr4_modes/local/tone_curves.json')['radial']
    coef = radial['gr4_coef_natural_log' if frame['family'] == 'gr4' else 'gr3_coef_natural_log']
    hh, ww = rgb.shape[:2]
    yy, xx = np.mgrid[:hh, :ww]
    r2 = (((yy - (hh - 1) / 2) ** 2 + (xx - (ww - 1) / 2) ** 2) / ((hh / 2) ** 2 + (ww / 2) ** 2)).astype(np.float32)
    gain = np.exp(-sum(c * r2 ** (i + 1) for i, c in enumerate(coef))).astype(np.float32)
    uc = wb * gain[..., None]
    luma = uc @ np.array([.25, .5, .25], np.float32)
    mean = uniform_filter(luma, size=5)
    var = np.maximum(uniform_filter(luma * luma, size=5) - mean * mean, 0)
    cv = np.sqrt(var) / np.maximum(mean, .0001)
    js = np.zeros((hh, ww), np.float32)
    color_cv = np.zeros((hh, ww), np.float32)
    for c in range(3):
        v = jpg[..., c]
        jm = uniform_filter(v, size=5)
        js = np.maximum(js, np.sqrt(np.maximum(uniform_filter(v * v, size=5) - jm * jm, 0)))
        v = uc[..., c]
        vm = uniform_filter(v, size=5)
        color_cv = np.maximum(color_cv, np.sqrt(np.maximum(uniform_filter(v * v, size=5) - vm * vm, 0)) / np.maximum(vm, .001))
    clip_ok = ~maximum_filter(raw['clip'], size=5)
    raw_valid = (rgb > .00005).all(axis=-1) & (rgb < .985).all(axis=-1) & clip_ok
    # No extrapolated registration: reject textured neighborhoods and erode boundaries.
    flat = (cv < .055) & (color_cv < .10) & (js < 3.5)
    valid = raw_valid & jpeg_valid & flat
    valid[:16] = False
    valid[-16:] = False
    valid[:, :16] = False
    valid[:, -16:] = False
    valid = binary_erosion(valid, iterations=2)
    indices = np.flatnonzero(valid)
    matrix, ci = cm.dng_camera_to_xyz(tags)
    vcam = rgb.reshape(-1, 3)[indices]
    vgain = gain.ravel()[indices]
    xyz = vcam @ matrix.T * (2 ** be) * vgain[:, None]
    scene_lab = cm.xyz_lab(xyz / .5)
    cell = bins(scene_lab)
    counts = np.bincount(cell, minlength=180).reshape(12, 5, 3)
    # One deterministic quota per occupied colour cell, with evenly spaced picks.
    chosen = []
    quota = max(100, cap // max(int((counts > 0).sum()), 1))
    for b in range(180):
        ii = np.flatnonzero(cell == b)
        chosen.extend(ii[np.linspace(0, len(ii) - 1, min(len(ii), quota), dtype=int)])
    chosen = np.unique(chosen)
    if len(chosen) > cap:
        chosen = chosen[np.linspace(0, len(chosen) - 1, cap, dtype=int)]
    pick = indices[chosen]
    sy, sx = yy.ravel()[pick], xx.ravel()[pick]
    uc_sample = uc.reshape(-1, 3)[pick]
    j_sample = jpg.reshape(-1, 3)[pick]
    weight = 1 / (1 + (cv.ravel()[pick] / .025) ** 2 + (js.ravel()[pick] / 1.5) ** 2)
    # Leave 8 half pixels next to spatial tile boundaries unused during CV.
    spatial_core = ((sx % 128 >= 8) & (sx % 128 < 120) & (sy % 128 >= 8) & (sy % 128 < 120))
    folds = ((sx // 128 + 3 * (sy // 128)) % 4).astype(np.int8)
    registration = alignment(wb, jpg)
    destination = LOCAL / 'samples' / (frame['id'] + '.npz')
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destination, uc=uc_sample, features=feature(uc_sample).astype(np.float32),
                        jpeg=j_sample, lab=cm.rgb_lab(j_sample / 255).astype(np.float32),
                        scene_lab=scene_lab[chosen].astype(np.float32), weight=weight,
                        xy=np.stack([sx, sy], axis=-1).astype(np.uint16), folds=folds,
                        spatial_core=spatial_core, raw3=raw['raw3'].reshape(-1, 3)[pick],
                        r2=r2.ravel()[pick], cell=cell[chosen].astype(np.int16))
    meta = {'id': frame['id'], 'frame': frame, 'metadata': frame['metadata'], 'raw': md,
            'jpeg': ji, 'baseline_exposure': be, 'radial_gain_source': 'gr4_modes/local/tone_curves.json',
            'gr3x_radial_is_gr3_proxy': frame['family'] == 'gr3x', 'shape_half': [hh, ww],
            'counts': {'all_quads': hh * ww, 'raw_eligible': int(raw_valid.sum()),
                       'jpeg_eligible': int(jpeg_valid.sum()), 'flat_before_erosion': int(flat.sum()),
                       'usable_quads': len(indices), 'retained_model_samples': len(pick)},
            'coverage_h12_l5_c3': counts, 'scene_white_Y': .5,
            'registration': registration, 'feature_range': np.percentile(feature(uc_sample), [0, 1, 50, 99, 100], axis=0),
            'cct_approx_K': ci['cct_K_approx']}
    dump(destination.with_suffix('.json'), meta)
    print(json.dumps({'id': frame['id'], **meta['counts'], 'alignment': registration.get('median_offset_half'),
                      'geometry_confirmed': registration['geometry_confirmed']}, default=lambda x: x.tolist()), flush=True)


def main():
    guard()
    parser = argparse.ArgumentParser()
    parser.add_argument('--frame', action='append')
    parser.add_argument('--cap', type=int, default=60000)
    args = parser.parse_args()
    inventory = read(LOCAL / 'inventory.json')
    for f in inventory:
        if not args.frame or f['id'] in args.frame:
            extract(f, args.cap)


if __name__ == '__main__':
    main()
