#!/usr/bin/env python3
"""Offline CFA -> JPEG patch analysis; NumPy + Pillow, no RAW converter defaults."""
import csv
import hashlib
import json
from pathlib import Path
import platform
import struct

import numpy as np
from PIL import Image, __version__ as pillow_version

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAP = ROOT / 'captures/a12-50'
RAW_TO_DISPLAY = {v: i for i, v in enumerate([0, 7, 6, 1, 2, 3, 4, 5, 8, 9])}
PARAMS = ['contrast', 'sharpness', 'vividness'] + [c + '_saturation' for c in
          ['orange', 'green', 'blue', 'red', 'magenta']] + [c + '_hue' for c in
          ['orange', 'green', 'blue', 'red', 'magenta']]


def save(name, data):
    (HERE / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


class Tiff:
    """Read-only classic TIFF reader, including Ricoh absolute-offset MakerNotes."""
    TYPES = {1: ('B', 1), 2: (None, 1), 3: ('H', 2), 4: ('I', 4), 5: ('II', 8),
             6: ('b', 1), 7: (None, 1), 8: ('h', 2), 9: ('i', 4), 10: ('ii', 8),
             11: ('f', 4), 12: ('d', 8)}

    def __init__(self, data):
        self.data = data
        assert data[:2] in [b'II', b'MM']
        self.endian = '<' if data[:2] == b'II' else '>'
        assert struct.unpack_from(self.endian + 'H', data, 2)[0] == 42
        self.root = struct.unpack_from(self.endian + 'I', data, 4)[0]

    def ifd(self, offset, endian=None):
        e = endian or self.endian
        count = struct.unpack_from(e + 'H', self.data, offset)[0]
        assert 0 <= offset < len(self.data) and offset + 2 + 12 * count + 4 <= len(self.data)
        result = {}
        for i in range(count):
            p = offset + 2 + i * 12
            tag, typ, n = struct.unpack_from(e + 'HHI', self.data, p)
            if typ not in self.TYPES:
                continue
            fmt, size = self.TYPES[typ]
            length = n * size
            o = p + 8 if length <= 4 else struct.unpack_from(e + 'I', self.data, p + 8)[0]
            assert o + length <= len(self.data), (tag, o, length)
            raw = self.data[o:o + length]
            if typ == 2:
                value = raw.rstrip(b'\0 ').decode('ascii', errors='replace')
            elif fmt is None:
                value = raw
            elif typ in [5, 10]:
                a = struct.unpack(e + fmt * n, raw)
                value = [a[j] / a[j + 1] for j in range(0, len(a), 2)]
            else:
                value = list(struct.unpack(e + fmt * n, raw))
            result[tag] = {'offset': o, 'raw': raw, 'value': value, 'type': typ, 'count': n}
        return result


def jpeg_tiff(path):
    data = path.read_bytes()
    assert data[:2] == b'\xff\xd8'
    p = 2
    while p + 4 <= len(data):
        assert data[p] == 255
        marker = data[p + 1]
        if marker in [0xDA, 0xD9]:
            break
        n = int.from_bytes(data[p + 2:p + 4], 'big')
        block = data[p + 4:p + 2 + n]
        if marker == 0xE1 and block.startswith(b'Exif\0\0'):
            return Tiff(block[6:])
        p += 2 + n
    raise ValueError(f'No EXIF found: {path}')


def shot_info(tiff):
    root = tiff.ifd(tiff.root)
    exif = tiff.ifd(root[34665]['value'][0])
    maker = exif[37500]
    assert maker['raw'][:8] == b'Ricoh\0\0\0'
    entries = tiff.ifd(maker['offset'] + 8, '>')
    shot = entries[0x1001]
    assert shot['count'] == 224 and shot['type'] == 7
    record = shot['raw']
    raw13 = record[0x31:0x34] + record[0x78:0x82]
    return {'date_time': exif[36867]['value'], 'iso': exif[34855]['value'][0],
            'exposure_seconds': exif[33434]['value'][0], 'f_number': exif[33437]['value'][0],
            'maker_shot_record_offset_in_tiff': shot['offset'], 'maker_shot_record_hex': record.hex(' '),
            'profile_record_selector': record[0x28],
            'record_0x2f_unknown_enum': record[0x2F], 'color_raw_13': list(raw13),
            'color_display': dict(zip(PARAMS, [RAW_TO_DISPLAY[x] for x in raw13])),
            'jpeg_color_space_exif': exif.get(40961, {}).get('value')}


def decode_raw(tiff):
    root = tiff.ifd(tiff.root)
    sub = [tiff.ifd(o) for o in root[330]['value']]
    raw = next(d for d in sub if d.get(262, {}).get('value') == [32803])
    value = lambda k: raw[k]['value']
    w, h = value(256)[0], value(257)[0]
    assert value(258) == [12] and value(259) == [1] and value(277) == [1]
    assert raw.get(266, {'value': [1]})['value'] == [1]
    assert value(33421) == [2, 2] and raw[33422]['raw'] == b'\0\1\1\2'
    assert len(value(273)) == 1
    offset, n = value(273)[0], value(279)[0]
    assert n == h * w * 12 // 8
    a = np.frombuffer(tiff.data, dtype=np.uint8, count=n, offset=offset).reshape(-1, 3).astype(np.uint16)
    mosaic = np.empty(h * w, dtype=np.uint16)
    mosaic[0::2] = (a[:, 0] << 4) | (a[:, 1] >> 4)
    mosaic[1::2] = ((a[:, 1] & 15) << 8) | a[:, 2]
    # Repacking checks lossless byte coverage, not agreement with a second RAW
    # decoder. MSB packing follows TIFF FillOrder=1 (including its default).
    assert np.array_equal(a[:, 0], mosaic[0::2] >> 4)
    assert np.array_equal(a[:, 1], ((mosaic[0::2] & 15) << 4) | (mosaic[1::2] >> 8))
    assert np.array_equal(a[:, 2], mosaic[1::2] & 255)
    mosaic = mosaic.reshape(h, w)
    ox, oy = map(int, value(50719))
    cw, ch = map(int, value(50720))
    assert 0 <= ox < w and 0 <= oy < h and ox + cw <= w and oy + ch <= h
    crop = mosaic[oy:oy + ch, ox:ox + cw]
    black, white = float(value(50714)[0]), float(value(50717)[0])
    neutral = np.array(root[50728]['value'], dtype=float)
    assert np.all(neutral > 0) and black < white
    stats = {'shape': [h, w], 'crop_origin_xy': [ox, oy], 'crop_wh': [cw, ch],
             'black_level': black, 'white_level': white, 'as_shot_neutral': neutral.tolist(),
             'baseline_exposure_ev': root[50730]['value'][0],
             'raw_strip_offset': offset, 'raw_strip_bytes': n,
             'raw_dn_percentiles_0_1_5_50_95_99_100': np.percentile(crop, [0, 1, 5, 50, 95, 99, 100]).tolist(),
             'raw_saturation_fraction': float(np.mean(crop >= white)),
             'color_matrix_1': root[50721]['value'], 'color_matrix_2': root[50722]['value'],
             'calibration_illuminants': [root[50778]['value'][0], root[50779]['value'][0]],
             'processing': '12-bit MSB packing; CFA-aware area means; no demosaic sharpening, DNG baseline exposure or color matrix applied'}
    return crop, black, white, neutral, stats


def mean_blocks(a, n):
    h, w = a.shape[:2]
    assert h % n == 0 and w % n == 0
    return a.reshape(h // n, n, w // n, n, *a.shape[2:]).mean(axis=(1, 3))


def fit_tone(x, rgb, bins=24):
    """Quantile-bin means + weighted PAVA, with endpoint clamping outside support."""
    order = np.argsort(x, kind='stable')
    groups = np.array_split(order, min(bins, len(order) // 10))
    xp = np.array([x[g].mean() for g in groups])
    yp = np.array([rgb[g].mean(axis=0) for g in groups])
    weights = np.array([len(g) for g in groups])
    if not np.all(np.diff(xp) > 0):
        raise ValueError('RAW variation insufficient for a monotonic tone fit')
    for c in range(3):
        blocks = []
        for i, (y, w) in enumerate(zip(yp[:, c], weights)):
            blocks.append([i, i + 1, float(y * w), float(w)])
            while len(blocks) > 1 and blocks[-2][2] / blocks[-2][3] > blocks[-1][2] / blocks[-1][3]:
                b = blocks.pop()
                a = blocks.pop()
                blocks.append([a[0], b[1], a[2] + b[2], a[3] + b[3]])
        for start, end, total, weight in blocks:
            yp[start:end, c] = total / weight
    return xp, yp


def predict(model, x):
    xp, yp = model
    return np.column_stack([np.interp(x, xp, yp[:, c]) for c in range(3)])


def lab(rgb):
    rgb = np.clip(rgb, 0, 1)
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = linear @ np.array([[0.4124564, 0.3575761, 0.1804375],
                             [0.2126729, 0.7151522, 0.0721750],
                             [0.0193339, 0.1191920, 0.9503041]]).T
    t = xyz / [0.95047, 1, 1.08883]
    f = np.where(t > (6 / 29) ** 3, np.cbrt(t), t / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.column_stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])])


def metrics(prediction, actual):
    error = (prediction - actual) * 255
    de = np.linalg.norm(lab(prediction) - lab(actual), axis=1)
    return {'n_patches': len(actual), 'rgb_code_rmse': float(np.sqrt(np.mean(error ** 2))),
            'rgb_code_mae': float(np.mean(np.abs(error))),
            'channel_error_2p5_97p5': np.percentile(error, [2.5, 97.5], axis=0).tolist(),
            'delta_e_76_median': float(np.median(de)), 'delta_e_76_p95': float(np.percentile(de, 95)),
            'meaning': 'within-frame 16x16 patch reproduction error, not color accuracy or brand match'}


def analyze(path, jpeg_path):
    tiff = Tiff(path.read_bytes())
    thumbnail = Image.open(jpeg_path)
    thumbnail.thumbnail((900, 600))
    thumbnail.save(HERE / 'capture_thumbnail.jpg')
    dng_info, jpg_info = shot_info(tiff), shot_info(jpeg_tiff(jpeg_path))
    assert dng_info['date_time'] == jpg_info['date_time']
    assert dng_info['color_raw_13'] == jpg_info['color_raw_13']
    crop, black, white, neutral, raw_stats = decode_raw(tiff)
    j = np.asarray(Image.open(jpeg_path).convert('RGB'), dtype=float) / 255
    assert j.shape[:2] == crop.shape
    assert jpg_info['jpeg_color_space_exif'] == [1]  # observed sRGB, not assumed AdobeRGB
    oy, ox = raw_stats['crop_origin_xy'][1], raw_stats['crop_origin_xy'][0]
    channels = [[] for _ in range(3)]
    cfa = [[0, 1], [1, 2]]
    for dy in range(2):
        for dx in range(2):
            color = cfa[(dy + oy) % 2][(dx + ox) % 2]
            channels[color].append(mean_blocks(crop[dy::2, dx::2].astype(float), 8))
    camera = np.stack([np.mean(c, axis=0) for c in channels], axis=-1)
    camera = (camera - black) / (white - black)
    camera_wb = camera / neutral
    # This is explicitly a sensor proxy, not scene luminance in XYZ or sRGB.
    signal = camera_wb @ np.array([0.25, 0.5, 0.25])
    target = mean_blocks(j, 16)
    yy, xx = np.indices(signal.shape)
    valid = ((camera.min(axis=-1) > 0.005) & (camera.max(axis=-1) < 0.98)
             & (target.min(axis=-1) > 1 / 255) & (target.max(axis=-1) < 254 / 255))
    assert valid.sum() > 500
    x, y = signal[valid], target[valid]
    fold = np.minimum(xx[valid] * 4 // signal.shape[1], 3)
    fold_results, heldout = [], np.empty_like(y)
    for i in range(4):
        test = fold == i
        model = fit_tone(x[~test], y[~test])
        pred = predict(model, x[test])
        heldout[test] = pred
        constant = np.broadcast_to(y[~test].mean(axis=0), pred.shape)
        design = np.column_stack([x[~test], np.ones((~test).sum())])
        linear = np.column_stack([x[test], np.ones(test.sum())]) @ np.linalg.lstsq(design, y[~test], rcond=None)[0]
        fold_results.append({'fold': i, 'test_n': int(test.sum()), 'train_n': int((~test).sum()),
                             'test_in_training_signal_support_fraction': float(np.mean((x[test] >= model[0][0]) & (x[test] <= model[0][-1]))),
                             'monotone': metrics(pred, y[test]), 'constant': metrics(constant, y[test]),
                             'linear': metrics(linear, y[test])})
    model = fit_tone(x, y)
    final_prediction = predict(model, x)
    design = camera_wb[valid]
    singular = np.linalg.svd(design - design.mean(axis=0), compute_uv=False)
    directions = design / np.maximum(design.sum(axis=1, keepdims=True), 1e-12)
    chroma = np.linalg.norm(lab(y)[:, 1:], axis=1)
    # Tiles, rather than individual nearby pixels, are the resampling unit.
    tile = (yy[valid] // 8) * ((signal.shape[1] + 7) // 8) + xx[valid] // 8
    tiles = np.unique(tile)
    members = [np.flatnonzero(tile == t) for t in tiles]
    rng = np.random.default_rng(20261016)
    grid = np.quantile(x, np.linspace(0.05, 0.95, 10))
    boot = []
    for _ in range(100):
        ids = np.concatenate([members[k] for k in rng.integers(0, len(tiles), len(tiles))])
        boot.append(predict(fit_tone(x[ids], y[ids]), grid))
    low, high = np.percentile(boot, [2.5, 97.5], axis=0)
    identifiability = {
        'scene_description': 'one bright, near-neutral curtain; no color chart, skin, foliage, sky or dark ramp',
        'capture_count': 1, 'reference_brand_pairs': 0, 'controlled_parameter_deltas': 0,
        'centered_sensor_rgb_singular_values': singular.tolist(),
        'centered_sensor_rgb_condition_number': float(singular[0] / singular[-1]),
        'sensor_chromaticity_p1_p99': np.percentile(directions, [1, 99], axis=0).tolist(),
        'jpeg_patch_chroma_Cab_p50_p95_max': np.percentile(chroma, [50, 95, 100]).tolist(),
        'jpeg_patch_fraction_Cab_above_10': float(np.mean(chroma > 10)),
        'global_color_matrix_identifiable': False, 'full_tone_curve_identifiable': False,
        'controls_13_plus_wb_jacobian_identifiable': False,
        'brand_match_confidence_interval': None,
        'reason': 'One near-neutral scene under one unknown light and one fixed non-neutral Setting1 cannot identify color directions, slider derivatives, shadows, or a brand transform.'}
    result = {'schema': 'gxr-raw-jpeg-neutral-response-v1',
              'input': {str(p.relative_to(ROOT)): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
                        for p in [path, jpeg_path]},
              'dng_shot': dng_info, 'jpeg_shot': jpg_info, 'raw': raw_stats,
              'sampling': {'patch_size_pixels': 16, 'grid_shape': list(signal.shape), 'patches_total': int(valid.size),
                           'patches_used': int(valid.sum()), 'excluded': int((~valid).sum()),
                           'valid_rule': 'all raw channel means >0.005 and <0.98; all JPEG means >1/255 and <254/255',
                           'jpeg_any_channel_255_pixel_fraction': float(np.mean(j.max(axis=-1) >= 1)),
                           'jpeg_RGB_code_percentiles_1_5_50_95_99': np.percentile(j * 255, [1, 5, 50, 95, 99], axis=(0, 1)).tolist(),
                           'linear_sensor_proxy_percentiles_0_1_5_50_95_99_100': np.percentile(x, [0, 1, 5, 50, 95, 99, 100]).tolist(),
                           'registration': 'DNG DefaultCropOrigin=(8,7), size=(4288,2848), orientation 1; CFA phase accounted; no estimated image warp',
                           'unverified_registration': 'No textured chart/feature alignment; subpixel or lens-processing residuals remain.'},
              'model': {'input_definition': 'u=(R/nR+2G/nG+B/nB)/4 after (DN-black)/(white-black); camera-linear proxy, not XYZ Y',
                        'output_definition': 'three sRGB-encoded JPEG channel means; no EOTF on output',
                        'fit': '24 quantile-bin means; weighted isotonic regression per channel; linear interpolation; clamp outside data support',
                        'parameter_count': int(len(model[0]) * 4), 'x_knots': model[0].tolist(),
                        'rgb_knots': model[1].tolist(), 'in_frame_fit': metrics(final_prediction, y),
                        'spatial_fourfold': fold_results, 'pooled_heldout': metrics(heldout, y),
                        'bootstrap': {'seed': 20261016, 'replicates': 100, 'unit': '128x128 pixel spatial tiles within this single frame',
                                      'n_tiles': len(tiles), 'signal_grid': grid.tolist(),
                                      'rgb_code_95pct_interval_low': (low * 255).tolist(),
                                      'rgb_code_95pct_interval_high': (high * 255).tolist(),
                                      'coverage': 'conditional resampling interval only; excludes new scenes, illumination, decoder/systematic errors, and brand matching'}},
              'identifiability': identifiability,
              'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'pillow': pillow_version}}
    save('capture_analysis.json', result)
    save('baseline_model.json', result['model'])
    with (HERE / 'paired_patch_measurements.csv').open('w') as f:
        writer = csv.writer(f)
        writer.writerow(['patch_x', 'patch_y', 'fold', 'raw_R', 'raw_G', 'raw_B', 'sensor_proxy', 'jpeg_R', 'jpeg_G', 'jpeg_B'])
        for px, py, ff, cam, sig, rgb in zip(xx[valid], yy[valid], fold, camera[valid], x, y):
            writer.writerow([int(px), int(py), int(ff)] + [round(float(v), 9) for v in [*cam, sig, *rgb]])
    # A data figure; SVG coordinates are computed directly from fitted values.
    xlo, xhi = float(x.min()), float(x.max())
    px = lambda a: 70 + 720 * (a - xlo) / (xhi - xlo)
    py = lambda a: 350 - 280 * a
    polylines = []
    for c, color in enumerate(['#a34331', '#4c7859', '#4677a4']):
        points = ' '.join(f'{px(a):.2f},{py(b):.2f}' for a, b in zip(model[0], model[1][:, c]))
        polylines.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="860" height="430" viewBox="0 0 860 430">
<rect width="860" height="430" fill="white"/><g font-family="sans-serif" font-size="15" fill="#222">
<text x="70" y="30">Observed curtain response / Setting1 C8 S6 V8, ISO 3200</text>
<text x="70" y="55">RAW camera-linear proxy → encoded JPEG means; only the measured interval is shown</text>
<path d="M70 70V350H790" fill="none" stroke="#777"/>
<text x="12" y="78">255</text><text x="40" y="354">0</text>
<text x="70" y="378">{xlo:.5f}</text><text x="725" y="378">{xhi:.5f}</text>
<text x="220" y="410">Sensor proxy u (not colorimetric luminance)</text>
{''.join(polylines)}</g></svg>'''
    (HERE / 'neutral_response.svg').write_text(svg)
    obs = np.zeros_like(target)
    pred = np.zeros_like(target)
    obs[:] = target
    pred[valid] = final_prediction
    pred[~valid] = target[~valid]
    side_by_side = np.concatenate([obs, pred], axis=1)
    Image.fromarray(np.uint8(np.clip(side_by_side, 0, 1) * 255)).resize((1072, 356)).save(HERE / 'observed_and_fitted.png')
    print(json.dumps({'pairs': 1, 'used_patches': int(valid.sum()),
                      'shot_parameters': dng_info['color_display'], 'identifiability': identifiability,
                      'pooled_holdout': result['model']['pooled_heldout']}))


def main():
    dngs = sorted(p for p in CAP.rglob('*') if p.is_file() and p.suffix.lower() == '.dng')
    pairs = []
    for p in dngs:
        jpgs = [q for q in p.parent.iterdir() if q.stem == p.stem and q.suffix.lower() in ['.jpg', '.jpeg']]
        if len(jpgs) == 1:
            pairs.append((p, jpgs[0]))
    save('capture_inventory.json', {'scan_root': str(CAP.relative_to(ROOT)), 'dng_count': len(dngs),
                                   'pairs': [[str(p.relative_to(ROOT)), str(j.relative_to(ROOT))] for p, j in pairs],
                                   'unpaired_jpeg_count': sum(p.suffix.lower() in ['.jpg', '.jpeg'] for p in CAP.rglob('*') if p.is_file()) - len(pairs)})
    # An expanded dataset needs grouped per-capture validation, not overwriting a
    # single-file fit and pretending its spatial folds are held-out scenes.
    if len(pairs) != 1:
        raise ValueError(f'Expected this evidence snapshot to have one pair; found {len(pairs)}. Add per-capture grouped fitting before expanding.')
    analyze(*pairs[0])


if __name__ == '__main__':
    main()
