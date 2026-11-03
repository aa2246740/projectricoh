#!/usr/bin/env python3
"""Other/ is only a fixed-model Standard cross-check; it never trains a target."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from target import DenseTarget, feature
import argparse
import imagecodecs


def run(stem):
    m = rt.model()
    rb, a, _ = rt.readback_modules()
    d = DenseTarget()
    source = rt.INPUT / 'Other' / (stem + '.DNG')
    jpeg = source.with_suffix('.JPG')
    t = rb.n.Tiff(source.read_bytes())
    g = t.geometry()
    md = a.metadata(jpeg, 'standard', 'camera')
    expected = dict(high_low_key=0, contrast=0, contrast_highlight=0, contrast_shadow=0,
                    saturation=0, hue=0, sharpness=0, shading=0, clarity=0)
    assert all(md['control'].get(k) == v for k, v in expected.items())
    assert md['image_tone'] == 256
    segments = t.segments(t.raw)
    assert len(segments) == 1
    seg = segments[0]
    blob = t.data[seg['offset']:seg['offset']+seg['capacity']]
    mosaic = imagecodecs.ljpeg_decode(blob).reshape(g['height'], g['width'])
    x0, y0 = g['crop_xy']
    w, h = g['crop_wh']
    crop = mosaic[y0:y0+h, x0:x0+w]
    raw = crop.astype(np.float32)
    black = g['black']
    white = g['white']
    rgb = np.stack([(raw[0::2, 0::2]-black[0])/(white-black[0]),
        .5*((raw[0::2, 1::2]-black[1])/(white-black[1])+(raw[1::2, 0::2]-black[2])/(white-black[2])),
        (raw[1::2, 1::2]-black[3])/(white-black[3])], axis=-1)
    raw_clip = crop.reshape(h//2, 2, w//2, 2).max(axis=(1, 3)) >= white
    def orient(value):
        code = g['orientation']
        if code == 1: return value
        if code == 2: return value[:, ::-1]
        if code == 3: return value[::-1, ::-1]
        if code == 4: return value[::-1]
        if code == 5: return value.swapaxes(0, 1)
        if code == 6: return np.rot90(value, 3)
        if code == 7: return value.swapaxes(0, 1)[::-1, ::-1]
        if code == 8: return np.rot90(value)
        raise ValueError('unsupported orientation')
    rgb, raw_clip = orient(rgb), orient(raw_clip)
    image = np.asarray(a.load_jpeg(jpeg), float)
    h, w = image.shape[:2]
    assert rgb.shape[:2] == (h//2, w//2)
    quality = rt.read('target/quality.json')
    gains = np.median([v['modes']['standard']['radial']['gain_ev'] for v in quality.values()], axis=0)
    radii = next(iter(quality.values()))['modes']['standard']['radial']['radius']
    chosen = []
    for y in np.linspace(40, h-40, 28).astype(int):
        for x in np.linspace(40, w-40, 40).astype(int):
            x, y = x//2*2, y//2*2
            jj = image[y-16:y+16, x-16:x+16]
            rr = rgb[y//2-8:y//2+8, x//2-8:x//2+8]
            if raw_clip[y//2-8:y//2+8, x//2-8:x//2+8].any():
                continue
            if jj.min() <= 2 or jj.max() >= 253 or jj.std(axis=(0, 1)).max() >= 3:
                continue
            mean = rr.mean(axis=(0, 1))
            if mean.min() <= .001 or (rr.std(axis=(0, 1))/np.maximum(mean, 1e-8)).max() >= .06:
                continue
            radius = np.hypot(x-w/2, y-h/2)/np.hypot(w/2, h/2)
            wb = mean/np.array(g['neutral']) * 2**np.interp(radius, radii, gains)
            chosen.append(dict(x=x, y=y, raw_wb=wb, jpeg=jj.mean(axis=(0, 1))))
    if not chosen:
        rt.dump(f'natural/{stem}.json', dict(stem=stem, flat_unclipped_positions=0,
            supported=0, insufficient_flat_regions=True, new_dense_standard_de00=rt.stats([]),
            target_training=False, candidate_fitting=False))
        print(stem, 'no eligible flat samples', flush=True)
        return
    wb = np.array([q['raw_wb'] for q in chosen])
    ff = feature(wb)
    prediction = d.function(ff)[:, :3]
    distance = d.tree.query(ff)[0]
    valid = np.isfinite(prediction).all(axis=1) & (distance <= 1.)
    actual = m.fs.lab_from_codes(np.array([q['jpeg'] for q in chosen]))
    error = m.fs.delta_e00(prediction[valid], actual[valid])
    from predict import Renderer
    frozen = Renderer().render(wb*np.array(d.info.get('template_neutral', g['neutral'])), g['neutral'], 'standard')
    frozen_error = m.fs.delta_e00(m.fs.lab_from_codes(frozen*255), actual)
    result = dict(stem=stem, natural_standard_crosscheck_only=True, target_training=False,
        candidate_fitting=False, input_dng_sha256=rt.sha(source), input_jpeg_sha256=rt.sha(jpeg),
        grid_positions=1120, flat_unclipped_positions=len(chosen), supported=int(valid.sum()),
        unsupported=int((~valid).sum()), new_dense_standard_de00=rt.stats(error),
        insufficient_flat_regions=len(chosen) < 8,
        predicted_minus_observed_L_median=float(np.median(prediction[valid, 0]-actual[valid, 0])) if valid.any() else None,
        frozen_GRIII_standard_de00_all_flat=rt.stats(frozen_error),
        metadata=md, raw_neutral=g['neutral'], source_baseline_exposure=g['baseline_exposure'],
        orientation=g['orientation'], RAW_and_JPEG_orientation_applied_equally=True,
        exposure_or_WB_refit=False, radial_gain_source='median of four observed dense Standard profiles',
        limitation='template WB and helper natural-scene WB/ISO may select different camera processing; no claim of scene-matched Positive validation')
    result['points'] = [dict(x=q['x'], y=q['y'], raw_wb=q['raw_wb'], observed_rgb=q['jpeg'],
        predicted_lab=prediction[i] if valid[i] else None, observed_lab=actual[i], supported=bool(valid[i]))
        for i, q in enumerate(chosen)]
    rt.dump(f'natural/{stem}.json', result)
    print(stem, len(chosen), int(valid.sum()), result['new_dense_standard_de00'].get('median'), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stem', required=True)
    run(ap.parse_args().stem)
