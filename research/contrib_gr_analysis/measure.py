#!/usr/bin/env python3
"""Measure contributed Ricoh GR / GR IV RAW to JPEG rendering.

Reads only. Paths come from the command line. Decoder cross-check uses the
Python SOF3 decoder on the first two rows and lj92 for the full mosaic.
"""
import csv
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from PIL import Image

from lossless_jpeg import decode as decode_prefix
from tiff_makernote import (
    Tiff, decode_gr2013, decode_gr3_family, jpeg_exif_tiff, maker_note_bytes, subifds,
)

LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)
HUE_CENTER = np.array([65, 145, 280, 25, 335], np.float64)
HUE_NAME = ['orange', 'green', 'blue', 'red', 'magenta']


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_tiff(path):
    data = Path(path).read_bytes()
    if data[:2] == b'\xff\xd8':
        return jpeg_exif_tiff(data)[0]
    return Tiff(data)


def tag_map(entries):
    return {item['tag']: item for item in entries}


def scalar(entry, default=None):
    if not entry:
        return default
    value = entry['value']
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def exposure_record(root, exif):
    both = {**tag_map(root), **tag_map(exif)}
    names = {
        271: 'make', 272: 'model', 305: 'software', 306: 'datetime',
        36867: 'datetime_original', 33434: 'exposure_s', 33437: 'f_number',
        34855: 'iso', 37380: 'exposure_bias_ev', 37386: 'focal_length_mm',
        40961: 'color_space', 274: 'orientation', 34850: 'exposure_program',
        41987: 'white_balance_exif', 40962: 'pixel_x', 40963: 'pixel_y',
    }
    out = {}
    for tag, name in names.items():
        out[name] = scalar(both.get(tag))
    return out


def redact(value):
    # Hide long decimal identifiers. Short hex blobs and menu values stay.
    if isinstance(value, str) and any(ch.isalpha() for ch in value) and sum(ch.isdigit() for ch in value) >= 6:
        return '[redacted]'
    return value


def decode_note(tiff):
    source, offset, note, root, exif = maker_note_bytes(tiff)
    if note.startswith(b'Ricoh\0\0\0'):
        entries, decoded = decode_gr2013(tiff, offset)
        kind = 'ricoh_gr2013'
    elif note.startswith(b'RICOH\0'):
        entries, decoded = decode_gr3_family(tiff, offset)
        kind = 'ricoh_pentax_family'
    else:
        entries, decoded, kind = [], None, 'unknown'
    public = {}
    if decoded:
        for key, value in decoded.items():
            if 'serial' in key:
                continue
            public[key] = redact(value) if isinstance(value, str) else value
    return {'source': source, 'length': len(note), 'kind': kind,
            'header_hex': note[:16].hex(), 'entries': entries, 'decoded': public,
            'exposure': exposure_record(root, exif), 'root': root, 'exif': exif}


def raw_subifd(root_entries, tiff):
    subs = subifds(tiff, root_entries)
    raw = next(tag_map(item) for item in subs if scalar(tag_map(item).get(259)) == 7
               and scalar(tag_map(item).get(262)) == 32803)
    return raw, [tag_map(item) for item in subs]


def dng_geometry(raw, root):
    # DNG puts some of these tags on IFD0 and some on the raw SubIFD.
    tags = {**root, **raw}
    active = scalar(tags.get(50829), [0, 0, scalar(tags[257]), scalar(tags[256])])
    origin = [float(v) for v in tags[50719]['value']]
    size = [int(round(float(v))) for v in tags[50720]['value']]
    x0 = int(round(active[1] + origin[0]))
    y0 = int(round(active[0] + origin[1]))
    black = [float(v) for v in tags[50714]['value']]
    white = float(scalar(tags[50717]))
    neutral = [float(v) for v in tags[50728]['value']]
    cfa = list(tags[33422]['raw'])
    return {'active_area_tlbr': [int(v) for v in active], 'crop_origin_xy': [x0, y0],
            'crop_size_wh': size, 'default_crop_origin': origin, 'black_level': black,
            'white_level': white, 'as_shot_neutral': neutral, 'cfa_pattern': cfa,
            'width': int(scalar(raw[256])), 'height': int(scalar(raw[257])),
            'bits': int(scalar(raw[258])), 'compression': int(scalar(raw[259])),
            'strip_offset': int(raw[273]['value'][0]), 'strip_bytes': int(raw[279]['value'][0])}


def lab(rgb):
    rgb = np.clip(np.asarray(rgb, np.float64), 0, 1)
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = linear @ np.array([[0.4124564, 0.3575761, 0.1804375],
                             [0.2126729, 0.7151522, 0.0721750],
                             [0.0193339, 0.1191920, 0.9503041]]).T
    t = xyz / [0.95047, 1, 1.08883]
    f = np.where(t > (6 / 29) ** 3, np.cbrt(t), t / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.column_stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])])


def _edge(values):
    values = values.astype(np.float64).ravel()
    if values.size == 0:
        return None
    return {'samples': int(values.size), 'median': float(np.median(values)),
            'p10': float(np.percentile(values, 10)), 'p90': float(np.percentile(values, 90))}


def border_stats(mosaic, active):
    top, left, bottom, right = [int(v) for v in active]
    sides = {
        'top': _edge(mosaic[:top, :]) if top > 0 else None,
        'bottom': _edge(mosaic[bottom:, :]) if bottom < mosaic.shape[0] else None,
        'left': _edge(mosaic[:, :left]) if left > 0 else None,
        'right': _edge(mosaic[:, right:]) if right < mosaic.shape[1] else None,
    }
    present = [side for side in sides.values() if side]
    if not present:
        return None
    values = []
    if top > 0:
        values.append(mosaic[:top, :].ravel())
    if bottom < mosaic.shape[0]:
        values.append(mosaic[bottom:, :].ravel())
    if left > 0:
        values.append(mosaic[:, :left].ravel())
    if right < mosaic.shape[1]:
        values.append(mosaic[:, right:].ravel())
    pooled = np.concatenate(values).astype(np.float64)
    return {'pooled_median': float(np.median(pooled)), 'pooled_mean': float(pooled.mean()),
            'sides': sides}


def compile_decoder(source, binary):
    if binary.exists():
        return
    subprocess.run(['cc', '-O3', '-Wall', '-Wextra', '-o', str(binary), str(source)], check=True)


def decode_mosaic(binary, blob, expect_wh, tmp):
    jpeg_path = tmp / 'strip.ljpeg'
    raw_path = tmp / 'strip.u16'
    jpeg_path.write_bytes(blob)
    proc = subprocess.run([str(binary), str(jpeg_path), str(raw_path)], check=True,
                          capture_output=True, text=True)
    header = dict(part.split('=') for part in proc.stdout.split())
    mosaic = np.fromfile(raw_path, dtype='<u2')
    raw_path.unlink()
    jpeg_path.unlink()
    width, height = expect_wh
    if mosaic.size != width * height:
        raise RuntimeError(f'sample count {mosaic.size} != {width * height}')
    diffs, info = decode_prefix(blob, max_samples=width * 2)
    precision = info['precision']
    components = info['components']
    sof_w = info['sof_wh'][0]
    mask = (1 << precision) - 1
    seed = 1 << (precision - 1)
    rows = np.empty((2, width), np.uint16)
    left = [0] * components
    above = [0] * components
    cursor = 0
    for y in range(2):
        for x in range(sof_w):
            for component in range(components):
                diff = int(diffs[cursor])
                cursor += 1
                if y == 0 and x == 0:
                    prediction = seed
                elif y == 0 or x:
                    prediction = left[component]
                else:
                    prediction = above[component]
                value = (prediction + diff) & mask
                left[component] = value
                if x == 0:
                    above[component] = value
                rows[y, x * components + component] = value
    got = mosaic.reshape(height, width)
    mismatch = int(np.count_nonzero(rows != got[:2]))
    if mismatch:
        raise RuntimeError(f'Python/C prefix mismatch {mismatch}')
    return got, {'lj92': header, 'prefix_rows_mismatch': mismatch,
                 'python_sof': info['sof_wh'], 'python_components': components,
                 'python_precision': precision}


def half_res(mosaic, geometry):
    x0, y0 = geometry['crop_origin_xy']
    width, height = geometry['crop_size_wh']
    crop = mosaic[y0:y0 + height, x0:x0 + width].astype(np.float32)
    pattern = np.array(geometry['cfa_pattern'], np.uint8).reshape(2, 2)
    if pattern[y0 % 2, x0 % 2] != 0 or (x0 % 2) or (y0 % 2):
        raise RuntimeError(f'crop phase is not RGGB at an even origin: {geometry}')
    black = np.array(geometry['black_level'], np.float32)
    if black.size == 1:
        black = np.repeat(black, 4)
    if black.size != 4:
        raise RuntimeError(f'unexpected black level {geometry["black_level"]}')
    planes = [crop[0::2, 0::2] - black[0],
              0.5 * (crop[0::2, 1::2] - black[1] + crop[1::2, 0::2] - black[2]),
              crop[1::2, 1::2] - black[3]]
    scale = geometry['white_level'] - float(np.mean(black))
    # Per-channel scale uses that channel's own black, not the mean.
    denom = np.array([geometry['white_level'] - float(black[0]),
                      geometry['white_level'] - float(0.5 * (black[1] + black[2])),
                      geometry['white_level'] - float(black[3])], np.float32)
    rgb = np.stack([planes[i] / denom[i] for i in range(3)], axis=-1)
    neutral = np.array(geometry['as_shot_neutral'], np.float32)
    gains = neutral[1] / neutral
    wb = np.clip(rgb, 0, None) * gains
    sensor_y = 0.25 * wb[..., 0] + 0.5 * wb[..., 1] + 0.25 * wb[..., 2]
    spread = wb.max(axis=-1) - wb.min(axis=-1)
    level = np.maximum(wb.mean(axis=-1), 1e-4)
    neutral_mask = (spread / level) < 0.10
    green_ratio = float(planes[1].mean() / max(float(crop[0::2, 1::2].mean() - black[1]), 1e-6))
    return {'rgb_linear': rgb, 'wb': wb, 'sensor_y': sensor_y, 'neutral': neutral_mask,
            'green_channel_ratio_note': green_ratio, 'half_wh': [int(sensor_y.shape[1]), int(sensor_y.shape[0])],
            'scale_check': float(scale)}


def jpeg_half(image, size_wh):
    width, height = size_wh
    array = np.asarray(image.convert('RGB'), np.float32)
    if array.shape[1] != width or array.shape[0] != height:
        raise RuntimeError(f'JPEG {array.shape[1]}x{array.shape[0]} != crop {width}x{height}')
    blocks = array.reshape(height // 2, 2, width // 2, 2, 3).mean(axis=(1, 3)) / 255.0
    luma = blocks @ LUMA
    clipped = (array <= 0).any(axis=-1) | (array >= 255).any(axis=-1)
    clipped = clipped.reshape(height // 2, 2, width // 2, 2).mean(axis=(1, 3))
    return blocks, luma, clipped


def tone_curve(sensor_y, jpeg_luma, mask, bins=24):
    high = float(np.quantile(sensor_y[mask], 0.995)) if mask.any() else 1.0
    high = max(high, 0.05)
    edges = np.linspace(0, high, bins + 1)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        chosen = mask & (sensor_y >= lo) & (sensor_y < hi)
        count = int(chosen.sum())
        if count < 50:
            continue
        rows.append({'raw_y_lo': float(lo), 'raw_y_hi': float(hi),
                     'raw_y_median': float(np.median(sensor_y[chosen])),
                     'jpeg_luma_median': float(np.median(jpeg_luma[chosen])),
                     'jpeg_luma_p25': float(np.percentile(jpeg_luma[chosen], 25)),
                     'jpeg_luma_p75': float(np.percentile(jpeg_luma[chosen], 75)),
                     'n': count})
    return rows


def block_means(sensor_wb, jpeg_rgb, clipped, tiles=24):
    height, width = sensor_wb.shape[:2]
    tile_h = height // tiles
    tile_w = width // (tiles * 3 // 2)
    rows = []
    for y in range(0, tile_h * tiles, tile_h):
        for x in range(0, tile_w * (tiles * 3 // 2), tile_w):
            wb = sensor_wb[y:y + tile_h, x:x + tile_w].mean(axis=(0, 1))
            jpg = jpeg_rgb[y:y + tile_h, x:x + tile_w].mean(axis=(0, 1))
            clip = float(clipped[y:y + tile_h, x:x + tile_w].mean())
            rows.append({'xy': [int(x), int(y)], 'wb_rgb': wb, 'jpeg_rgb': jpg, 'clip': clip})
    return rows


def ncc_shift(reference, moving):
    """Integer shift of moving relative to reference.

    Phase correlation locked onto the flat wall. Edge NCC on a coarse grid,
    then a small refine, matches the shared projector framing.
    """
    step = 4
    def edges(image):
        small = image[::step, ::step]
        gy, gx = np.gradient(small)
        return np.hypot(gx, gy)
    ref, mov = edges(reference), edges(moving)
    height, width = ref.shape
    margin = 8

    def score(dy, dx):
        y0, x0 = margin + max(dy, 0), margin + max(dx, 0)
        y1, x1 = height - margin + min(dy, 0), width - margin + min(dx, 0)
        aa = ref[y0:y1, x0:x1]
        bb = mov[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
        if aa.size < 1000:
            return -1.0
        aa = (aa - aa.mean()) / (aa.std() + 1e-8)
        bb = (bb - bb.mean()) / (bb.std() + 1e-8)
        return float((aa * bb).mean())

    best = (-1.0, 0, 0)
    for dy in range(-24, 25, 2):
        for dx in range(-12, 13, 2):
            value = score(dy, dx)
            if value > best[0]:
                best = (value, dy, dx)
    _, dy0, dx0 = best
    best = (-1.0, dy0, dx0)
    for dy in range(dy0 - 2, dy0 + 3):
        for dx in range(dx0 - 2, dx0 + 3):
            value = score(dy, dx)
            if value > best[0]:
                best = (value, dy, dx)
    return {'dy_half': int(best[1] * step), 'dx_half': int(best[2] * step),
            'ncc': float(best[0]), 'search': 'edge NCC, coarse ±24/±12 then ±2, step 4'}


def shift_pair(reference, moving, dy, dx):
    height, width = reference.shape[:2]
    y0 = max(0, dy)
    x0 = max(0, dx)
    y1 = height + min(0, dy)
    x1 = width + min(0, dx)
    ref = reference[y0:y1, x0:x1]
    mov = moving[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    return ref, mov


def interp_curve(curve, x):
    xs = np.array([row['raw_y_median'] for row in curve])
    ys = np.array([row['jpeg_luma_median'] for row in curve])
    order = np.argsort(xs)
    return np.interp(x, xs[order], ys[order], left=np.nan, right=np.nan)


def gain_normalized_mapping(standard_curve, other_curve, gain):
    """gain = other_raw / standard_raw. Same reflectance, two JPEG outputs."""
    xs = np.array([row['raw_y_median'] for row in standard_curve])
    jpeg_std = np.array([row['jpeg_luma_median'] for row in standard_curve])
    jpeg_other = interp_curve(other_curve, xs * gain)
    keep = np.isfinite(jpeg_other)
    return [{'standard_raw_y': float(a), 'standard_jpeg_luma': float(b),
             'other_jpeg_luma': float(c), 'delta_jpeg_luma': float(c - b)}
            for a, b, c in zip(xs[keep], jpeg_std[keep], jpeg_other[keep])]


def gr3_predict(mapping_rows, reference):
    src = np.array(reference['tone_input_encoded_luma'])
    dst = np.array(reference['tone_output_encoded_luma'])
    order = np.argsort(src)
    src, dst = src[order], dst[order]
    rows = []
    for row in mapping_rows:
        x = row['standard_jpeg_luma']
        if x < src[0] or x > src[-1]:
            continue
        rows.append({**row, 'gr3_jpeg_luma': float(np.interp(x, src, dst)),
                     'gr3_delta': float(np.interp(x, src, dst) - x)})
    if not rows:
        return {'n': 0}
    got = np.array([row['other_jpeg_luma'] for row in rows])
    expect = np.array([row['gr3_jpeg_luma'] for row in rows])
    delta = np.array([row['delta_jpeg_luma'] for row in rows])
    gr3_delta = np.array([row['gr3_delta'] for row in rows])
    return {'n': len(rows), 'rmse_jpeg_luma': float(np.sqrt(np.mean((got - expect) ** 2))),
            'mean_delta': float(delta.mean()), 'mean_gr3_delta': float(gr3_delta.mean()),
            'delta_correlation': float(np.corrcoef(delta, gr3_delta)[0, 1]) if len(rows) > 2 else None,
            'rows': rows}


def color_groups(source_rgb, target_rgb, source_l_limit=True):
    source = lab(np.vstack(source_rgb))
    target = lab(np.vstack(target_rgb))
    chroma_s = np.linalg.norm(source[:, 1:], axis=1)
    chroma_t = np.linalg.norm(target[:, 1:], axis=1)
    hue_s = np.degrees(np.arctan2(source[:, 2], source[:, 1])) % 360
    hue_t = np.degrees(np.arctan2(target[:, 2], target[:, 1])) % 360
    distance = np.abs((hue_s[:, None] - HUE_CENTER[None, :] + 180) % 360 - 180)
    nearest = distance.argmin(axis=1)
    groups = []
    for index, name in enumerate(HUE_NAME):
        chosen = (chroma_s > 15) & (nearest == index)
        if source_l_limit:
            chosen &= (source[:, 0] >= 15) & (source[:, 0] <= 90)
        ratio = chroma_t[chosen] / np.maximum(chroma_s[chosen], 1e-6)
        shift = (hue_t[chosen] - hue_s[chosen] + 180) % 360 - 180
        groups.append({'color': name, 'n': int(chosen.sum()),
                       'median_chroma_ratio': float(np.median(ratio)) if chosen.any() else None,
                       'ratio_p25_p75': [float(np.percentile(ratio, 25)), float(np.percentile(ratio, 75))] if chosen.any() else None,
                       'median_hue_shift_degrees': float(np.median(shift)) if chosen.any() else None})
    return groups


def svg_plot(path, series, xlabel, ylabel, title, identity=False):
    width, height = 920, 560
    left, top, right, bottom = 70, 36, 24, 48
    xs = np.concatenate([np.array(item['x'], np.float64) for item in series])
    ys = np.concatenate([np.array(item['y'], np.float64) for item in series])
    lo = min(0, float(np.nanmin(xs)), float(np.nanmin(ys)))
    hi = max(float(np.nanmax(xs)), float(np.nanmax(ys)), 0.05) * 1.05
    def px(x):
        return left + (x - lo) / (hi - lo) * (width - left - right)
    def py(y):
        return top + (1 - (y - lo) / (hi - lo)) * (height - top - bottom)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
             '<rect width="100%" height="100%" fill="#f7f4ee"/>',
             f'<text x="{left}" y="24" font-family="PingFang SC, sans-serif" font-size="16">{title}</text>']
    for tick in np.linspace(lo, hi, 5):
        parts.append(f'<line x1="{px(tick):.1f}" y1="{top}" x2="{px(tick):.1f}" y2="{height-bottom}" stroke="#ddd"/>')
        parts.append(f'<line x1="{left}" y1="{py(tick):.1f}" x2="{width-right}" y2="{py(tick):.1f}" stroke="#ddd"/>')
        parts.append(f'<text x="{px(tick):.1f}" y="{height-bottom+18}" text-anchor="middle" font-size="11">{tick:.2f}</text>')
        parts.append(f'<text x="{left-8}" y="{py(tick):.1f}" text-anchor="end" font-size="11">{tick:.2f}</text>')
    if identity:
        parts.append(f'<line x1="{px(lo):.1f}" y1="{py(lo):.1f}" x2="{px(hi):.1f}" y2="{py(hi):.1f}" stroke="#999" stroke-dasharray="4 3"/>')
    for item in series:
        x = np.array(item['x'], np.float64)
        y = np.array(item['y'], np.float64)
        keep = np.isfinite(x) & np.isfinite(y)
        points = ' '.join(f'{px(a):.1f},{py(b):.1f}' for a, b in zip(x[keep], y[keep]))
        dash = ' stroke-dasharray="6 4"' if item.get('dash') else ''
        parts.append(f'<polyline fill="none" stroke="{item["color"]}" stroke-width="2"{dash} points="{points}"/>')
    for index, item in enumerate(series):
        parts.append(f'<text x="{width-220}" y="{56+index*18}" fill="{item["color"]}" font-family="PingFang SC, sans-serif" font-size="13">{item["name"]}</text>')
    parts.append(f'<text x="{(width)/2:.0f}" y="{height-8}" text-anchor="middle" font-size="12">{xlabel}</text>')
    parts.append(f'<text x="16" y="{height/2:.0f}" font-size="12" transform="rotate(-90 16 {height/2:.0f})">{ylabel}</text>')
    parts.append('</svg>')
    path.write_text('\n'.join(parts), encoding='utf-8')


def thumbnail(image, path):
    copy = image.copy()
    copy.thumbnail((480, 320))
    copy.save(path, quality=70)


def main():
    if len(sys.argv) != 5:
        raise SystemExit('usage: measure.py captures_dir reference_json research_out tmp_out')
    captures, reference_path, research, tmp = map(Path, sys.argv[1:])
    research.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    files = sorted(captures.rglob('*'))
    files = [path for path in files if path.suffix.upper() in {'.DNG', '.JPG'}]
    before = {str(path.relative_to(captures)): {'sha256': sha256(path), 'bytes': path.stat().st_size} for path in files}
    reference = json.loads(reference_path.read_text())['relative_mappings']
    binary = tmp / 'lj92'
    compile_decoder(Path(__file__).resolve().parent / 'lj92.c', binary)

    meta = {}
    for path in files:
        meta[path.name] = decode_note(load_tiff(path))
        meta[path.name]['path'] = str(path)

    # DNG/JPEG effect agreement and the four-frame maker-note diff.
    effect_agreement = []
    for stem in ['GR000006', 'GR000007', 'GR000008', 'GR000009', 'GR000106', 'GR000109']:
        dng = meta[stem + '.DNG']['decoded']['image_effects']
        jpg = meta[stem + '.JPG']['decoded']['image_effects']
        effect_agreement.append({'stem': stem, 'dng': dng, 'jpg': jpg, 'match': dng == jpg,
                                 'dng_firmware': meta[stem + '.DNG']['decoded']['firmware'],
                                 'jpg_firmware': meta[stem + '.JPG']['decoded']['firmware']})
    base_entries = {item['tag']: item['raw'] for item in meta['GR000006.DNG']['entries']}
    diffs = {}
    for stem in ['GR000007', 'GR000008', 'GR000009']:
        changed = []
        other = {item['tag']: item for item in meta[stem + '.DNG']['entries']}
        for tag, raw in base_entries.items():
            if tag not in other or other[tag]['raw'] == raw:
                continue
            if len(raw) > 32:
                changed.append({'tag': tag, 'kind': 'binary', 'bytes': len(raw)})
                continue
            changed.append({'tag': tag, 'from_hex': raw.hex(), 'to_hex': other[tag]['raw'].hex()})
        diffs[stem] = changed

    per_file = {}
    kept = {}
    dngs = [path for path in files if path.suffix.upper() == '.DNG']
    for path in dngs:
        tiff = load_tiff(path)
        info = meta[path.name]
        raw, subs = raw_subifd(info['root'], tiff)
        geometry = dng_geometry(raw, tag_map(info['root']))
        blob = tiff.data[geometry['strip_offset']:geometry['strip_offset'] + geometry['strip_bytes']]
        mosaic, check = decode_mosaic(binary, blob, (geometry['width'], geometry['height']), tmp)
        border = border_stats(mosaic, geometry['active_area_tlbr'])
        half = half_res(mosaic, geometry)
        if path.name.startswith('R0000097'):
            embedded = next(item for item in subs if scalar(item.get(262)) == 6)
            off, nbytes = int(embedded[273]['value'][0]), int(embedded[279]['value'][0])
            image = Image.open(Path(path).open('rb')) if False else None
            import io
            image = Image.open(io.BytesIO(tiff.data[off:off + nbytes]))
            jpeg_source = 'SubIFD lossy JPEG'
            try:
                embedded_note = decode_note(jpeg_exif_tiff(tiff.data[off:off + nbytes])[0])
            except Exception as exc:
                embedded_note = {'error': str(exc)}
        else:
            sidecar = path.with_suffix('.JPG')
            image = Image.open(sidecar)
            jpeg_source = sidecar.name
            embedded_note = None
        jpeg_rgb, jpeg_luma, clipped = jpeg_half(image, geometry['crop_size_wh'])
        neutral = half['neutral'] & (clipped < 0.02) & (half['sensor_y'] < 1.05)
        spread = half['wb'].max(axis=-1) - half['wb'].min(axis=-1)
        loose = (spread / np.maximum(half['wb'].mean(axis=-1), 1e-4) < 0.35) & (clipped < 0.02) & (half['sensor_y'] < 1.05)
        curve = tone_curve(half['sensor_y'], jpeg_luma, neutral)
        curve_loose = tone_curve(half['sensor_y'], jpeg_luma, loose)
        values = mosaic.ravel()
        record = {
            'geometry': geometry,
            'decoder': check,
            'border_outside_active_area': border,
            'raw_min': int(values.min()), 'raw_max': int(values.max()),
            'raw_median': float(np.median(values)),
            'raw_p01': float(np.percentile(values, 1)), 'raw_p99': float(np.percentile(values, 99)),
            'fraction_at_or_above_white': float(np.mean(values >= geometry['white_level'])),
            'fraction_at_zero': float(np.mean(values == 0)),
            'jpeg_source': jpeg_source, 'jpeg_size': list(image.size),
            'neutral_fraction': float(neutral.mean()),
            'loose_fraction': float(loose.mean()),
            'tone_neutral': curve,
            'tone_loose': curve_loose,
            'g1_over_g2': float((mosaic[0::2, 1::2].mean()) / mosaic[1::2, 0::2].mean()),
        }
        if embedded_note is not None:
            record['embedded_jpeg_maker'] = {key: embedded_note.get(key) for key in ('kind', 'decoded', 'error', 'source')}
        # Coloured blocks against the JPEG itself are stored for the single-file signature.
        blocks = block_means(half['wb'], jpeg_rgb, clipped)
        sensor_chroma = []
        jpeg_colors = []
        for block in blocks:
            if block['clip'] > 0.02:
                continue
            wb = block['wb_rgb']
            if wb.mean() < 0.02:
                continue
            chroma = float((wb.max() - wb.min()) / max(float(wb.mean()), 1e-4))
            if chroma < 0.28:
                continue
            sensor_chroma.append(wb / max(float(wb.mean()), 1e-6))
            jpeg_colors.append(block['jpeg_rgb'])
        if sensor_chroma:
            # Hue of the white-balanced camera RGB, treated only as a direction, not as sRGB.
            sensor = np.vstack(sensor_chroma)
            jpg = lab(np.vstack(jpeg_colors))
            sensor_hue = np.degrees(np.arctan2(sensor[:, 2] - sensor[:, 1], sensor[:, 0] - sensor[:, 1]))
            record['colored_blocks'] = {'n': len(sensor_chroma),
                                        'median_jpeg_chroma': float(np.median(np.linalg.norm(jpg[:, 1:], axis=1))),
                                        'median_jpeg_L': float(np.median(jpg[:, 0])),
                                        'sensor_hue_p50': float(np.median(sensor_hue))}
        else:
            record['colored_blocks'] = {'n': 0}
        per_file[path.name] = record
        kept[path.name] = {'sensor_y': half['sensor_y'], 'jpeg_rgb': jpeg_rgb,
                           'jpeg_luma': jpeg_luma, 'neutral': neutral, 'loose': loose, 'clipped': clipped}
        thumbnail(image, tmp / f'{path.stem}.jpg')
        del mosaic
        print(path.name, 'decoded', geometry['width'], geometry['height'], 'neutral', round(record['neutral_fraction'], 3), flush=True)

    # Same-scene pairs. 006 is the zero-slider Standard.
    pair_reports = {}
    ref_name = 'GR000006.DNG'
    for other_name in ['GR000007.DNG', 'GR000008.DNG', 'GR000009.DNG']:
        shift = ncc_shift(kept[ref_name]['sensor_y'], kept[other_name]['sensor_y'])
        ref_y, oth_y = shift_pair(kept[ref_name]['sensor_y'], kept[other_name]['sensor_y'], shift['dy_half'], shift['dx_half'])
        ref_j, oth_j = shift_pair(kept[ref_name]['jpeg_rgb'], kept[other_name]['jpeg_rgb'], shift['dy_half'], shift['dx_half'])
        ref_n, oth_n = shift_pair(kept[ref_name]['neutral'], kept[other_name]['neutral'], shift['dy_half'], shift['dx_half'])
        ref_c, oth_c = shift_pair(kept[ref_name]['clipped'], kept[other_name]['clipped'], shift['dy_half'], shift['dx_half'])
        ref_l, oth_l = shift_pair(kept[ref_name]['loose'], kept[other_name]['loose'], shift['dy_half'], shift['dx_half'])
        usable = (ref_c < 0.02) & (oth_c < 0.02) & (ref_y > 0.015) & (ref_y < 0.85) & (oth_y > 0.008) & (oth_y < 0.85)
        ratio = (oth_y[usable] / ref_y[usable])
        gain = float(np.median(ratio))
        log_std = float(np.std(np.log2(np.clip(ratio, 1e-4, None))))
        mapping = gain_normalized_mapping(per_file[ref_name]['tone_loose'], per_file[other_name]['tone_loose'], gain)
        neutral_overlap = int((ref_n & oth_n & usable).sum())
        loose_overlap = int((ref_l & oth_l & usable).sum())
        # Direct block comparison at matched pixels, for the exposure-confounded view.
        both_luma_ref = (ref_j @ LUMA)
        both_luma_oth = (oth_j @ LUMA)
        # Colour on 48 px blocks of the aligned frame.
        tile = 48
        src_cols, dst_cols, close_src, close_dst = [], [], [], []
        for y in range(0, ref_j.shape[0] - tile, tile):
            for x in range(0, ref_j.shape[1] - tile, tile):
                a = ref_j[y:y + tile, x:x + tile]
                b = oth_j[y:y + tile, x:x + tile]
                if a.size == 0:
                    continue
                if np.mean((a <= 0.01) | (a >= 0.99)) > 0.02 or np.mean((b <= 0.01) | (b >= 0.99)) > 0.02:
                    continue
                am, bm = a.mean(axis=(0, 1)), b.mean(axis=(0, 1))
                src_cols.append(am)
                dst_cols.append(bm)
                if abs(float((am @ LUMA) - (bm @ LUMA))) < 0.06:
                    close_src.append(am)
                    close_dst.append(bm)
        groups = color_groups(src_cols, dst_cols) if src_cols else []
        groups_light_matched = color_groups(close_src, close_dst) if close_src else []
        mode = meta[other_name]['decoded']['image_effects']['name']
        compared = None
        if mode == 'Positive Film':
            compared = gr3_predict(mapping, reference['ricoh_gr3_positive'])
        pair_reports[other_name] = {
            'alignment_half_pixels': shift, 'raw_gain_other_over_standard': gain,
            'log2_gain_std': log_std, 'midtone_overlap_pixels': int(usable.sum()),
            'neutral_overlap_pixels': neutral_overlap, 'loose_overlap_pixels': loose_overlap,
            'gain_normalized_jpeg_mapping': mapping,
            'gr3_positive_comparison': compared,
            'chroma_groups_all_aligned_blocks': groups,
            'chroma_groups_similar_luma': groups_light_matched,
            'similar_luma_blocks': len(close_src), 'aligned_blocks': len(src_cols),
        }
        # Small evidence picture of the luma difference. It stays in tmp.
        diff = np.clip(np.abs(both_luma_ref - both_luma_oth), 0, 1)
        preview = (diff[::4, ::4] * 255).astype(np.uint8)
        Image.fromarray(preview, 'L').save(tmp / f'diff_{other_name[:9]}.png')

    # Curves for the plot.
    svg_plot(tmp / 'tone_raw_to_jpeg.svg', [
        {'name': name.replace('.DNG', ''), 'x': [row['raw_y_median'] for row in per_file[name]['tone_loose']],
         'y': [row['jpeg_luma_median'] for row in per_file[name]['tone_loose']],
         'color': color}
        for name, color in [('GR000006.DNG', '#444'), ('GR000007.DNG', '#c45c26'),
                            ('GR000008.DNG', '#d39a2d'), ('GR000009.DNG', '#6b5b95'),
                            ('GR000106.DNG', '#2f6f4e'), ('GR000109.DNG', '#3d6f8a'),
                            ('R0000097.DNG', '#9c2f2f')]
    ], 'white-balanced sensor Y', 'JPEG encoded luma', 'Loose neutral mask: sensor Y to JPEG luma')

    positive = pair_reports['GR000007.DNG']['gain_normalized_jpeg_mapping']
    gr3 = reference['ricoh_gr3_positive']
    svg_plot(tmp / 'positive_vs_gr3.svg', [
        {'name': 'GR 2013 007 vs 006', 'x': [row['standard_jpeg_luma'] for row in positive],
         'y': [row['other_jpeg_luma'] for row in positive], 'color': '#c45c26'},
        {'name': 'GR III Positive vs Standard', 'x': gr3['tone_input_encoded_luma'],
         'y': gr3['tone_output_encoded_luma'], 'color': '#2457a6', 'dash': True},
    ], 'Standard JPEG luma', 'other JPEG luma', 'Exposure-normalised Positive against GR III', identity=True)

    # Drop bulky arrays before JSON.
    for record in per_file.values():
        record['geometry']['strip_offset'] = record['geometry']['strip_offset']
    public_meta = {}
    for name, item in meta.items():
        decoded = item['decoded']
        public_meta[name] = {'source': item['source'], 'kind': item['kind'], 'header_hex': item['header_hex'],
                             'length': item['length'], 'exposure': item['exposure'], 'decoded': decoded}

    def dump(obj):
        return json.dumps(obj, ensure_ascii=False, indent=2, default=lambda v: float(v) if isinstance(v, np.floating) else int(v) if isinstance(v, np.integer) else list(v) if isinstance(v, np.ndarray) else str(v))

    (research / 'modes.json').write_text(dump({'files': public_meta, 'dng_jpg_effect_agreement': effect_agreement,
                                              'maker_note_raw_diff_from_GR000006': diffs}))
    (research / 'measurements.json').write_text(dump({'per_file': per_file, 'pairs_against_GR000006': pair_reports,
        'method': {
            'raw_luma': '0.25 R + 0.5 G + 0.25 B after black/white normalisation and AsShotNeutral white balance with green gain 1',
            'jpeg_luma': 'encoded sRGB 0.2126 R + 0.7152 G + 0.0722 B, same weights as reference_analysis.py',
            'neutral': 'white-balanced max-min over mean < 0.10, JPEG clip fraction < 0.02',
            'pair_gain': 'median other/standard of aligned neutral sensor Y; other curve is then read at standard_Y * gain',
            'lab': 'same sRGB to Lab transform as research/color_calibration/analyze_capture.py lab()',
            'hue_groups': 'same five Lab-hue centres as reference_analysis.py',
        }}))
    with (research / 'tone_response.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['file', 'mask', 'raw_y_lo', 'raw_y_hi', 'raw_y_median', 'jpeg_luma_median', 'jpeg_luma_p25', 'jpeg_luma_p75', 'n'])
        writer.writeheader()
        for name, record in per_file.items():
            for mask, rows in [('neutral', record['tone_neutral']), ('loose', record['tone_loose'])]:
                for row in rows:
                    writer.writerow({'file': name, 'mask': mask, **row})
    with (research / 'pair_deltas.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['other_file', 'standard_raw_y', 'standard_jpeg_luma', 'other_jpeg_luma', 'delta_jpeg_luma'])
        writer.writeheader()
        for name, record in pair_reports.items():
            for row in record['gain_normalized_jpeg_mapping']:
                writer.writerow({'other_file': name, **row})
    with (research / 'chroma_groups.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['other_file', 'set', 'color', 'n', 'median_chroma_ratio', 'median_hue_shift_degrees'])
        writer.writeheader()
        for name, record in pair_reports.items():
            for label, groups in [('all_aligned', record['chroma_groups_all_aligned_blocks']),
                                  ('similar_luma', record['chroma_groups_similar_luma'])]:
                for group in groups:
                    writer.writerow({'other_file': name, 'set': label, 'color': group['color'], 'n': group['n'],
                                     'median_chroma_ratio': group['median_chroma_ratio'],
                                     'median_hue_shift_degrees': group['median_hue_shift_degrees']})
    after = {str(path.relative_to(captures)): {'sha256': sha256(path), 'bytes': path.stat().st_size} for path in files}
    (research / 'hashes.json').write_text(dump({'before': before, 'after': after, 'unchanged': before == after}))
    print('unchanged', before == after)


if __name__ == '__main__':
    main()
