"""Measure ROI distributions, same-CFA textures and clipping without changing old runs."""
import argparse
import csv
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from scipy import ndimage
from PIL import Image
import session_runtime as s
from repair_mount_metadata import apply as mount_adapter


def spectrum(block, mask, minimum_frequency=.1):
    if block.ndim == 2:
        block = block[..., None]
    h, w = mask.shape
    yy, xx = np.indices((h, w))
    A = np.stack([np.ones_like(xx), xx / max(w, 1), yy / max(h, 1)], -1)
    coef = np.linalg.lstsq(A[mask], block[mask], rcond=None)[0]
    residual = np.where(mask[..., None], block - A @ coef, 0.)
    win = np.outer(np.hanning(h), np.hanning(w)) * mask
    fft = abs(np.fft.fft2(residual * win[..., None], axes=(0, 1)))
    fy, fx = np.fft.fftfreq(h)[:, None], np.fft.fftfreq(w)[None, :]
    high = np.hypot(fx, fy) >= minimum_frequency
    power = np.where(high[..., None], fft**2, -1.)
    peak_at = np.unravel_index(np.argmax(power), power.shape)
    peak = float(power[peak_at])
    amp = 2 * np.sqrt(max(peak, 0)) / max(float(win.sum()), 1.)
    ratio = peak / max(float(np.median((fft[high])**2)), 1e-8)
    correlations = {}
    for lag in (1, 2, 4, 8):
        values = []
        for dy, dx in ((0, lag), (lag, 0)):
            if h <= dy or w <= dx:
                continue
            a = residual[:h-dy or None, :w-dx or None]
            b = residual[dy:, dx:]
            keep = mask[:h-dy or None, :w-dx or None] & mask[dy:, dx:]
            if keep.sum() < 20:
                continue
            aa, bb = a[keep], b[keep]
            den = np.sqrt(np.sum(aa*aa, axis=0) * np.sum(bb*bb, axis=0))
            values.extend((np.sum(aa*bb, axis=0) / np.maximum(den, 1e-9)).tolist())
        correlations[str(lag)] = max(values, key=abs) if values else None
    quadrants = []
    for y0, y1 in ((0, h//2), (h//2, h)):
        for x0, x1 in ((0, w//2), (w//2, w)):
            keep = mask[y0:y1, x0:x1]
            if keep.sum() >= 8:
                quadrants.append(residual[y0:y1, x0:x1][keep].mean(axis=0))
    qrange = np.ptp(quadrants, axis=0).tolist() if len(quadrants) >= 2 else None
    return {'amplitude': amp, 'peak_ratio': ratio,
        'frequency_xy': [float(np.fft.fftfreq(w)[peak_at[1]]), float(np.fft.fftfreq(h)[peak_at[0]])],
        'peak_channel': int(peak_at[2]), 'autocorrelation_lags': correlations,
        'detrended_quadrant_mean_range': qrange}


def estimators(values):
    lo, hi = np.quantile(values, (.1, .9), axis=0)
    trimmed = [values[:, c][(values[:, c] >= lo[c]) & (values[:, c] <= hi[c])] for c in range(values.shape[1])]
    return {'mean': values.mean(axis=0).tolist(),
            'trimmed_mean': [float(v.mean()) for v in trimmed],
            'median': [float(np.median(v)) for v in trimmed]}


def clip_stats(values):
    low, high = values <= 2, values >= 253
    counts = np.count_nonzero(low | high, axis=1)
    any_clip = float(np.mean(counts > 0))
    all_dark, all_bright = float(np.mean(low.all(1))), float(np.mean(high.all(1)))
    multiple = float(np.mean(counts >= 2))
    if any_clip <= .01:
        category = 'not-flagged'
    elif all_dark > .01:
        category = 'all-channel-dark'
    elif all_bright > .01:
        category = 'all-channel-bright'
    elif multiple > .01:
        category = 'multiple-channel-color'
    else:
        category = 'single-channel-color'
    return {'category': category, 'any_fraction': any_clip,
        'low_fractions': low.mean(0).tolist(), 'high_fractions': high.mean(0).tolist(),
        'all_dark_fraction': all_dark, 'all_bright_fraction': all_bright,
        'multiple_channel_fraction': multiple,
        'unclipped_channel_mask': ((low | high).mean(0) <= .01).tolist()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='moire-review-v1')
    args = ap.parse_args()
    out = (s.LOCAL / args.out).resolve()
    assert out.is_relative_to(s.LOCAL) and not out.exists()
    analyzer, chain, p = s.setup(s.LOCAL / 'extraction', freeze=False)
    mount_adapter(analyzer, chain)
    p.add(Path(__file__))
    out.mkdir()
    source = s.LOCAL / 'analysis-final'
    paths = sorted((source / 'frames').glob('*.json'))
    nrows = 0
    with (out / 'roi_metrics.jsonl').open('w') as stream:
        for path in paths:
            frame = json.loads(p.add(path).read_text())
            assert int(frame['frame'][1:]) % 10000 >= 1261
            if frame['kind'] != 'screen':
                continue
            for filename in frame['paths'].values():
                p.add(filename)
            with Image.open(frame['paths']['jpeg']) as im:
                rgb = np.asarray(im.convert('RGB'))
            ds = chain.dng.DngScene(Path(frame['paths']['dng']), Path(frame['paths']['jpeg']), jpeg_rgb=rgb, verify=False)
            # Reuse the already-verified map; do not repeat or silently change registration.
            registration = frame['raw_jpeg_registration']
            offset = registration.get('after_offset', registration)['offset_applied_xy']
            ds.map = chain.dng.RawMap(ds.dng, ds.jpeg_info['size_wh'], ds.jpeg_info['orientation'], offset)
            assert ds.map.unit
            cy, cx, _, _ = ds.dng.crop_window()
            H = np.array(frame['geometry']['H']); geo = {'H': H, 'Hinv': np.linalg.inv(H)}
            for q in frame['patches']:
                ya, yb, xa, xb, mask, _ = chain.ar.roi_mask(geo, q['chart_roi_bbox'], rgb.shape)
                block = np.asarray(rgb[ya:yb, xa:xb], float)
                values = block[mask]
                yy, xx = np.indices(mask.shape)
                ry, rx = ds.map.pixels(yy + ya, xx + xa)
                raw = ds.dng.normalised_at(ry + cy, rx + cx)
                cfa = ds.dng.cfa_at(ry + cy, rx + cx)
                raw_est = []
                for color in range(3):
                    raw_est.append(estimators(raw[mask & (cfa == color), None]))
                raw_planes = []
                for py in range(2):
                    for px in range(2):
                        plane, keep = raw[py::2, px::2] * 4095, mask[py::2, px::2]
                        if keep.sum() < 30:
                            continue
                        metric = spectrum(plane, keep, .2)
                        metric.update(color=int(cfa[py, px]), phase_yx=[py, px], mean_DN=float(plane[keep].mean()),
                                      relative_amplitude=metric['amplitude']/max(float(plane[keep].mean()), 1.))
                        raw_planes.append(metric)
                jpg_est = estimators(values)
                assert np.max(np.abs(np.array([v['median'][0] for v in raw_est])-q['raw_rgb'])) < 1e-9
                assert np.max(np.abs(np.array([v['mean'][0] for v in raw_est])-q['raw']['mean_cam'])) < 1e-9
                # Shift the whole original mask by +-2 stored JPEG pixels, with a guard margin inside the tile.
                shifted_means = []
                for dy, dx in ((-2,-2),(-2,0),(-2,2),(0,-2),(0,0),(0,2),(2,-2),(2,0),(2,2)):
                    translated = np.asarray(rgb[ya+dy:yb+dy, xa+dx:xb+dx], float)
                    assert translated.shape == block.shape
                    shifted_means.append(translated[mask].mean(0))
                row = {'frame': frame['frame'], 'group': frame['capture_group'], 'slot': frame.get('slot'),
                    'page': frame['page'], 'patch_id': q['patch_id'], 'sample_key': q['sample_key'],
                    'class': q['class'], 'shutter_s': frame['meta']['t'], 'asn': frame['meta']['asn'],
                    'nominal_lab_d65': q['nominal_lab_d65'], 'original_flags': q['flags'],
                    'jpeg': jpg_est, 'jpeg_spatial': spectrum(block, mask),
                    'jpeg_shifted_means': np.asarray(shifted_means).tolist(),
                    'raw': {key: [raw_est[c][key][0] for c in range(3)] for key in ('mean','trimmed_mean','median')},
                    'raw_planes': raw_planes, 'clipping': clip_stats(values),
                    'verified_RAW_offset_xy': offset,
                    'raw_saturation_fraction': q['raw']['clip_frac'], 'jpeg_pixel_count': int(mask.sum())}
                assert np.max(np.abs(np.array(jpg_est['median']) - q['jpeg_rgb'])) < 1e-9
                assert abs(row['jpeg_spatial']['amplitude'] - q['quality']['moire_amplitude_codes']) < 1e-8
                stream.write(json.dumps(s.plain(row), ensure_ascii=False, allow_nan=False) + '\n')
                nrows += 1
            print(f"{frame['frame']} {frame['capture_group']} P{frame['page']} n=116", flush=True)
    s.dump(out / 'sampling_provenance.json', p.finish())
    s.dump(out / 'sampling_summary.json', {'frames': nrows//116, 'patches': nrows,
        'raw_plane_units': '12-bit normalized DN; separate R/G1/G2/B; no CFA checkerboard FFT',
        'registration': 'reused exact previously verified RawMap offset; no new alignment'})
    print(json.dumps({'patches': nrows, 'out': str(out)}), flush=True)


if __name__ == '__main__':
    main()
