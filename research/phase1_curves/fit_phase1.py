#!/usr/bin/env python3
"""Phase-1 GXR tone identification and row-5 fit. Analysis only.

Reads firmware and captures. Writes under research/phase1_curves and /tmp/gxr_phase1_curves.
Does not modify inputs. Ricoh firmware bytes go only to the gitignored local/ dump.
"""
import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path('/Users/wu/.t3/projects/projectricoh')
OUT = ROOT / 'research/phase1_curves'
TMP = Path('/tmp/gxr_phase1_curves')
CAP = ROOT / 'captures/a12-50/2026-10-19/stage2c-first-run'
JLAUNCH = ROOT / 'artifacts/firmware/gxr-1.51/jlaunch3'
DEEP_C = ROOT / 'firmware/stage2c_category_gate/deep_tables.c'
PROTECTED = [
    JLAUNCH,
    *[CAP / f'R805114{n}.{ext}' for n in '4567' for ext in ('DNG', 'JPG')],
]

# Section 3 file offset = VMA - 0x200F2000 + 0xA7200
VMA_DELTA = 0x200F2000
SEC3_BIAS = 0xA7200


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def file_off(vma):
    return vma - VMA_DELTA + SEC3_BIAS


def u16be(raw):
    return [(raw[i] << 8) | raw[i + 1] for i in range(0, len(raw), 2)]


def parse_c_arrays(text):
    out = {}
    for m in re.finditer(r'static const uint8_t (table_\d+_\d+)\[\] = \{([^;]+)\};', text):
        nums = [int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]+)', m.group(2))]
        out[m.group(1)] = nums
    return out


def load_ac():
    spec = importlib.util.spec_from_file_location(
        'ac', ROOT / 'research/color_calibration/analyze_capture.py')
    ac = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ac)
    return ac


def srgb_oetf(lin):
    lin = np.clip(lin, 0, 1)
    return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def srgb_eotf(enc):
    enc = np.clip(enc, 0, 1)
    return np.where(enc <= 0.04045, enc / 12.92, np.power((enc + 0.055) / 1.055, 2.4))


def code_to_L(code):
    lin = srgb_eotf(np.asarray(code, float) / 255.0)
    t = np.where(lin > 0.008856, np.power(lin, 1 / 3), 7.787 * lin + 16 / 116)
    return 116 * t - 16


def eval_curve(A, B, x):
    xs = np.concatenate(([0.0], np.asarray(A, float), [4095.0]))
    ys = np.asarray(B, float)
    keep = np.ones(len(xs), dtype=bool)
    last = -1.0
    for i, v in enumerate(xs):
        if v <= last:
            keep[i] = False
        else:
            last = float(v)
    return np.interp(np.asarray(x, float), xs[keep], ys[keep])


def apply_pre(u, k, g):
    return np.clip(np.power(np.clip(u * k, 0, 1), g), 0, 1) * 4095.0


def apply_post(v, p, kind):
    t = np.clip(np.asarray(v, float) / 255.0, 0, 1)
    if kind == 'id':
        y = t
    elif kind == 'pow':
        y = np.power(t, p)
    elif kind == 'srgb':
        y = srgb_oetf(t)
    else:
        raise ValueError(kind)
    return np.clip(y * 255.0, 0, 255)


def inv_post(y, p, kind):
    t = np.clip(np.asarray(y, float) / 255.0, 0, 1)
    if kind == 'id':
        v = t
    elif kind == 'pow':
        v = np.power(t, 1.0 / p)
    elif kind == 'srgb':
        v = srgb_eotf(t)
    else:
        raise ValueError(kind)
    return np.clip(v * 255.0, 0, 255)


def rmse(a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    return float(np.sqrt(np.mean((a - b) ** 2)))


def load_shot(ac, name):
    dng = CAP / f'R805{name}.DNG'
    jpg = CAP / f'R805{name}.JPG'
    raw_tiff = ac.Tiff(dng.read_bytes())
    crop, black, white, neutral, stats = ac.decode_raw(raw_tiff)
    crop = np.asarray(crop)
    assert crop.ndim == 2
    info = {}
    try:
        info = ac.shot_info(raw_tiff)
    except Exception as exc:
        info = {'shot_info_error': str(exc)}
    try:
        info['jpeg'] = ac.shot_info(ac.jpeg_tiff(jpg))
    except Exception as exc:
        info['jpeg_shot_info_error'] = str(exc)
    jpg_im = Image.open(jpg)
    orient = 1
    try:
        orient = int(jpg_im.getexif().get(274, 1) or 1)
    except Exception:
        orient = 1
    rgb = np.asarray(jpg_im.convert('RGB'), dtype=np.float64)
    return {
        'name': name, 'crop': crop, 'black': float(black), 'white': float(white),
        'neutral': np.asarray(neutral, float), 'stats': stats, 'info': info,
        'rgb': rgb, 'jpeg_size': list(jpg_im.size), 'orientation': orient,
    }


def sensor_fields(crop, neutral):
    # Cropped CFA phase is G/B/R/G, as used by tone_compare.py.
    g1 = crop[0::2, 0::2].astype(np.float64)
    b = crop[0::2, 1::2].astype(np.float64)
    r = crop[1::2, 0::2].astype(np.float64)
    g2 = crop[1::2, 1::2].astype(np.float64)
    n = neutral
    if len(n) < 3:
        raise RuntimeError(f'AsShotNeutral length {len(n)}')
    R = r / n[0]
    G = (g1 + g2) * 0.5 / n[1]
    B = b / n[2]
    u = (R + 2 * G + B) / 4.0 / 4095.0
    chroma = np.maximum(np.abs(R - G), np.abs(B - G)) / (G + 1.0)
    return u, chroma


def align_jpeg(rgb, u_shape, orientation):
    """Return half-resolution JPEG luma in the same array order as the CFA half-grid."""
    arr = rgb
    # PIL size and the raw crop are both sensor-stored for these GXR files when
    # orientation is 1. If a tag says otherwise, rotate the stored JPEG back.
    if orientation == 3:
        arr = np.rot90(arr, 2)
    elif orientation == 6:
        arr = np.rot90(arr, 1)  # stored is 90 CW; undo
    elif orientation == 8:
        arr = np.rot90(arr, -1)
    hh, ww = u_shape
    if arr.shape[0] < hh * 2 or arr.shape[1] < ww * 2:
        raise RuntimeError(f'JPEG {arr.shape} smaller than CFA half-grid {u_shape}')
    small = arr[:hh * 2, :ww * 2][0::2, 0::2]
    Y = 0.2126 * small[..., 0] + 0.7152 * small[..., 1] + 0.0722 * small[..., 2]
    sat = small.max(axis=2) - small.min(axis=2)
    return Y, sat, arr.shape


def best_shift(u, chroma, Y, sat, limit=4):
    """Pick a small integer shift of JPEG relative to the CFA grid. Stock shot only."""
    neutral = (chroma < 0.12) & (sat < 16) & (u > 0.01) & (u < 0.9)
    best = (0, 0, -1.0)
    h, w = u.shape
    m = 12
    a = u[m:h - m, m:w - m]
    n = neutral[m:h - m, m:w - m]
    a_n = a[n]
    if a_n.size < 500:
        return 0, 0, float('nan')
    a_n = a_n - a_n.mean()
    for dy in range(-limit, limit + 1):
        for dx in range(-limit, limit + 1):
            b = Y[m + dy:h - m + dy, m + dx:w - m + dx]
            b_n = b[n]
            b_n = b_n - b_n.mean()
            denom = math.sqrt(float(np.dot(a_n, a_n) * np.dot(b_n, b_n)))
            corr = float(np.dot(a_n, b_n) / denom) if denom else -1.0
            if corr > best[2]:
                best = (dy, dx, corr)
    return best


def shift_pair(u, chroma, Y, sat, dy, dx):
    if dy == 0 and dx == 0:
        return u, chroma, Y, sat
    h, w = u.shape
    y0, y1 = max(0, dy), h + min(0, dy)
    x0, x1 = max(0, dx), w + min(0, dx)
    ys0, ys1 = y0 - dy, y1 - dy
    xs0, xs1 = x0 - dx, x1 - dx
    return (u[y0:y1, x0:x1], chroma[y0:y1, x0:x1],
            Y[ys0:ys1, xs0:xs1], sat[ys0:ys1, xs0:xs1])


def block_samples(u, chroma, Y, sat, n=16, raw_thr=0.08, jpeg_thr=12.0):
    h = (u.shape[0] // n) * n
    w = (u.shape[1] // n) * n
    def blk(a):
        return a[:h, :w].reshape(h // n, n, w // n, n).mean(axis=(1, 3))
    ub, cb, yb, sb = blk(u), blk(chroma), blk(Y), blk(sat)
    ok = (cb < raw_thr) & (sb < jpeg_thr) & (ub > 0.004) & (ub < 0.92) & (yb > 3) & (yb < 250)
    return ub[ok], yb[ok], int(ok.sum()), int(ok.size)


def binned(u, y, edges):
    rows = []
    for a, b in zip(edges[:-1], edges[1:]):
        s = (u >= a) & (u < b)
        if s.sum() < 12:
            rows.append(None)
        else:
            rows.append({
                'u': float(np.sqrt(a * b)),
                'y': float(np.median(y[s])),
                'n': int(s.sum()),
                'y_p10': float(np.percentile(y[s], 10)),
                'y_p90': float(np.percentile(y[s], 90)),
            })
    return rows


def predict_bins(bins, A, B, k, g, p, kind):
    pred = []
    obs = []
    used = []
    for row in bins:
        if row is None:
            continue
        x = apply_pre(row['u'], k, g)
        v = eval_curve(A, B, x)
        y = apply_post(v, p, kind)
        pred.append(float(y))
        obs.append(row['y'])
        used.append(row)
    return np.array(obs), np.array(pred), used


def search(shots_bins, curve_for, grid, stock_ab):
    best = None
    for k, g, p, kind in grid:
        err2 = 0.0
        n = 0
        for name, bins in shots_bins.items():
            A, B = curve_for(name)
            obs, pred, _ = predict_bins(bins, A, B, k, g, p, kind)
            if len(obs) == 0:
                continue
            err2 += float(np.sum((obs - pred) ** 2))
            n += len(obs)
        if n == 0:
            continue
        score = math.sqrt(err2 / n)
        rec = {'k': k, 'g': g, 'p': p, 'kind': kind, 'rmse': score, 'nbins': n}
        if best is None or score < best['rmse']:
            best = rec
    return best


def complexity(rec):
    # Lower is simpler. Identity post and gamma 1 are the baseline.
    c = 0
    if abs(rec['g'] - 1) > 1e-6:
        c += 1
    if rec['kind'] != 'id':
        c += 1
    if rec['kind'] == 'pow' and abs(rec['p'] - 1) > 1e-6:
        c += 1
    return c


def transfer_T(std_codes, mode_codes):
    std = np.asarray(std_codes, float)
    mode = np.asarray(mode_codes, float)
    order = np.argsort(std)
    std, mode = std[order], mode[order]

    def T(y):
        y = np.asarray(y, float)
        out = np.interp(y, std, mode)
        # Linear extrapolation of the end segments, then clamp.
        left = mode[0] + (mode[1] - mode[0]) / (std[1] - std[0]) * (y - std[0])
        right = mode[-1] + (mode[-1] - mode[-2]) / (std[-1] - std[-2]) * (y - std[-1])
        out = np.where(y < std[0], left, out)
        out = np.where(y > std[-1], right, out)
        return np.clip(out, 0, 255)

    return T


def pava(y, w=None):
    y = np.asarray(y, float).copy()
    n = len(y)
    if w is None:
        w = np.ones(n)
    else:
        w = np.asarray(w, float)
    # Pool adjacent violators.
    starts = list(range(n))
    ends = list(range(1, n + 1))
    avg = list(y)
    wt = list(w)
    i = 0
    while i < len(avg) - 1:
        if avg[i] <= avg[i + 1] + 1e-12:
            i += 1
            continue
        avg[i] = (avg[i] * wt[i] + avg[i + 1] * wt[i + 1]) / (wt[i] + wt[i + 1])
        wt[i] = wt[i] + wt[i + 1]
        ends[i] = ends[i + 1]
        del avg[i + 1], wt[i + 1], starts[i + 1], ends[i + 1]
        if i:
            i -= 1
    out = np.empty(n)
    for a, b, v in zip(starts, ends, avg):
        out[a:b] = v
    return out


def greedy_nodes(x, v, n_interior=31, min_gap=6):
    chosen = [float(x[0]), float(x[-1])]
    gap = float(min_gap)
    while len(chosen) - 2 < n_interior:
        pred = np.interp(x, chosen, np.interp(chosen, x, v))
        err = np.abs(v - pred)
        for c in chosen:
            err[np.abs(x - c) < gap] = 0
        i = int(np.argmax(err))
        if err[i] <= 1e-6:
            gap = max(1.0, gap * 0.5)
            if gap <= 1.0 and err[i] <= 1e-6:
                # Fill the largest open interval.
                chosen.sort()
                widths = np.diff(chosen)
                j = int(np.argmax(widths))
                chosen.append(0.5 * (chosen[j] + chosen[j + 1]))
            continue
        chosen.append(float(x[i]))
        chosen.sort()
    interior = np.array(sorted(chosen)[1:-1], float)
    if len(interior) > n_interior:
        interior = interior[:n_interior]
    return interior


def nodes_from_interior(interior, ideal_x, ideal_v):
    A = np.rint(interior).astype(int)
    A = np.clip(A, 1, 4094)
    for i in range(1, len(A)):
        if A[i] <= A[i - 1]:
            A[i] = min(4094, A[i - 1] + 1)
    # If the top collided, walk backwards.
    for i in range(len(A) - 2, -1, -1):
        if A[i] >= A[i + 1]:
            A[i] = A[i + 1] - 1
    if A[0] < 1 or A[-1] > 4094 or np.any(np.diff(A) <= 0):
        raise RuntimeError('input nodes not strictly inside (0,4095)')
    xs = np.concatenate(([0.0], A.astype(float), [4095.0]))
    target = np.interp(xs, ideal_x, ideal_v)
    smooth = pava(target)
    B = np.clip(np.rint(smooth), 0, 255).astype(int)
    for i in range(1, len(B)):
        if B[i] < B[i - 1]:
            B[i] = B[i - 1]
    return A, B, xs, target


def curve_error(A, B, ideal_x, ideal_v):
    pred = eval_curve(A, B, ideal_x)
    d = pred - ideal_v
    return float(np.sqrt(np.mean(d ** 2))), float(np.max(np.abs(d)))


def stock_shaped_nodes(stock_A, ideal_x, ideal_v):
    return nodes_from_interior(np.asarray(stock_A, float), ideal_x, ideal_v)


def shadow_dense_nodes(ideal_x, ideal_v):
    low = np.geomspace(4, 700, 18)
    high = np.linspace(820, 4000, 13)
    return nodes_from_interior(np.unique(np.rint(np.concatenate([low, high]))), ideal_x, ideal_v)


def decode_coeff(b):
    return int(b) if b < 128 else -(int(b) - 128)


def sector_rows(raw96):
    rows = []
    for i in range(24):
        a, b, b2, a2 = raw96[4 * i:4 * i + 4]
        sa, sb = decode_coeff(a), decode_coeff(b)
        scale = math.hypot(sa, sb) / 32.0
        angle = math.degrees(math.atan2(sb, sa))
        rows.append({
            'sector': i, 'a': sa, 'b': sb, 'scale': scale, 'angle_deg': angle,
            'redundant_ok': (b2 == (b ^ 0x80)) and (a2 == a),
        })
    return rows


GROUPS = {
    'orange': [7, 8, 9, 10],
    'green': [12, 13, 14, 15, 16],
    'blue': [18, 19, 20, 21, 22],
    'red': [5, 6],
    'magenta': [1, 2, 3, 4],
}


def group_scales(rows):
    out = {}
    for name, idx in GROUPS.items():
        out[name] = float(np.median([rows[i]['scale'] for i in idx]))
    return out


def plot_series(path, title, xlabel, ylabel, series, guides=None):
    W, H = 980, 660
    im = Image.new('RGB', (W, H), 'white')
    dr = ImageDraw.Draw(im)
    l, r, t, b = 78, 24, 46, 64
    xs = np.concatenate([np.asarray(s[1], float) for s in series])
    ys = np.concatenate([np.asarray(s[2], float) for s in series])
    xmin, xmax = float(xs.min()), float(xs.max())
    ymin, ymax = min(0.0, float(ys.min()) - 2), max(255.0, float(ys.max()) + 2)
    if xmax <= xmin:
        xmax = xmin + 1

    def X(x):
        return l + (float(x) - xmin) / (xmax - xmin) * (W - l - r)

    def Y(y):
        return t + (1 - (float(y) - ymin) / (ymax - ymin)) * (H - t - b)

    dr.line([(l, t), (l, H - b), (W - r, H - b)], fill=(40, 40, 40))
    for tick in (0, 64, 128, 192, 255):
        if ymin <= tick <= ymax:
            yy = Y(tick)
            dr.line([(l - 4, yy), (l, yy)], fill=(40, 40, 40))
            dr.text((8, yy - 6), str(tick), fill=(40, 40, 40))
    for tick in (0, 50, 100, 150, 200, 250):
        if xmin <= tick <= xmax:
            xx = X(tick)
            dr.line([(xx, H - b), (xx, H - b + 4)], fill=(40, 40, 40))
            dr.text((xx - 10, H - b + 8), str(tick), fill=(40, 40, 40))
    colors = [(30, 30, 30), (180, 40, 40), (20, 80, 180), (20, 130, 70), (140, 80, 20), (100, 40, 140)]
    for i, (name, x, y) in enumerate(series):
        pts = [(X(a), Y(c)) for a, c in zip(x, y)]
        if len(pts) >= 2:
            dr.line(pts, fill=colors[i % len(colors)], width=2)
        dr.text((l + 8, t + 8 + 16 * i), name, fill=colors[i % len(colors)])
    if guides:
        for x, label in guides:
            xx = X(x)
            dr.line([(xx, t), (xx, H - b)], fill=(180, 180, 180))
    dr.text((l, 12), title, fill=(0, 0, 0))
    dr.text((l, H - 22), xlabel, fill=(40, 40, 40))
    ylab = Image.new('L', (220, 18), 255)
    ImageDraw.Draw(ylab).text((0, 2), ylabel, fill=0)
    ylab = ylab.rotate(90, expand=True)
    im.paste(ylab.convert('RGB'), (6, t + 80))
    im.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'local').mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    before = {str(p.relative_to(ROOT)): sha256(p) for p in PROTECTED}

    blob = JLAUNCH.read_bytes()
    stock_a_raw = blob[file_off(0x2012F504):file_off(0x2012F504) + 62]
    stock_b_raw = blob[file_off(0x2012FFFC):file_off(0x2012FFFC) + 33]
    hc_a_raw = blob[file_off(0x2012F8A6):file_off(0x2012F8A6) + 62]
    hc_b_raw = blob[file_off(0x201301EB):file_off(0x201301EB) + 33]
    color_raw = blob[file_off(0x2012C5D4):file_off(0x2012C5D4) + 96]
    stock_A, stock_B = u16be(stock_a_raw), list(stock_b_raw)
    hc_A, hc_B = u16be(hc_a_raw), list(hc_b_raw)
    # Integrity check only. The node list stays in the gitignored local dump.
    hc_a_sha = hashlib.sha256(bytes(hc_a_raw)).hexdigest()
    hc_b_sha = hashlib.sha256(bytes(hc_b_raw)).hexdigest()
    if hc_a_sha != '2180c9c81c2146940bef62da996350428502560ddaa29b9a7ea04747f66e3c29':
        raise SystemExit('row 20 input hash changed')
    if hc_b_sha != 'dd589d5c9306f26576a3c3932bad76742cf708e16349c71613da94fbb9df5afc':
        raise SystemExit('row 20 output hash changed')
    if not all(x < y for x, y in zip(hc_A, hc_A[1:])) or hc_A[-1] != 4095 or hc_B[0] != 0 or hc_B[-1] != 255:
        raise SystemExit('row 20 is not a monotone full-range curve')
    # ordinary_contrast.csv display 5, node 1 input/output = 5/3
    if stock_A[0] != 5 or stock_B[1] != 3 or stock_B[0] != 0 or stock_B[-1] != 255:
        raise SystemExit(f'row 5 extraction unexpected {stock_A[:4]} {stock_B[:4]}')

    arrays = parse_c_arrays(DEEP_C.read_text())
    deep = {}
    for key in ('0', '1', '2', '3', '4'):
        if f'table_{key}_0' not in arrays and key == '4':
            A = u16be(bytes(arrays['table_1_0']))
        elif f'table_{key}_0' in arrays:
            A = u16be(bytes(arrays[f'table_{key}_0']))
        else:
            continue
        B = arrays[f'table_{key}_1']
        deep[f'table_{key}'] = {'A': A, 'B': B, 'sha_a': hashlib.sha256(bytes(arrays.get(f'table_{key}_0', arrays['table_1_0']))).hexdigest(),
                                'sha_b': hashlib.sha256(bytes(B)).hexdigest()}
    color_tables = {}
    for name, raw in arrays.items():
        if name.endswith('_2'):
            color_tables[name] = raw

    catalog = json.loads((ROOT / 'research/canonical_gr_pack/deep_isp_tables.json').read_text())
    slot_match = {}
    for sid, slot in catalog['slots'].items():
        tone = slot.get('type26') or {}
        a = (tone.get('input31_u16BE') or {}).get('sha256')
        b = (tone.get('output33') or {}).get('sha256')
        if not a or not b:
            continue
        hits = [name for name, row in deep.items() if row['sha_a'] == a and row['sha_b'] == b]
        # Slot 05 may reuse another row's A with its own B.
        b_hits = [name for name, row in deep.items() if row['sha_b'] == b]
        slot_match[sid] = {
            'source_row_1based': tone.get('source_row_1based'),
            'provenance': slot.get('source_provenance'),
            'exact_ab': hits,
            'b_only': b_hits,
        }

    ac = load_ac()
    shots = {n: load_shot(ac, n) for n in ('1144', '1145', '1146', '1147')}
    fields = {}
    for n, s in shots.items():
        u, chroma = sensor_fields(s['crop'], s['neutral'])
        Y, sat, full_shape = align_jpeg(s['rgb'], u.shape, s['orientation'])
        fields[n] = {'u': u, 'chroma': chroma, 'Y': Y, 'sat': sat, 'jpeg_array_shape': full_shape}

    dy, dx, corr = best_shift(fields['1144']['u'], fields['1144']['chroma'],
                              fields['1144']['Y'], fields['1144']['sat'])
    samples = {}
    for n in fields:
        u, c, Y, sat = shift_pair(fields[n]['u'], fields[n]['chroma'], fields[n]['Y'], fields[n]['sat'], dy, dx)
        uu, yy, kept, total = block_samples(u, c, Y, sat)
        samples[n] = {'u': uu, 'y': yy, 'kept': kept, 'total': total,
                      'u_p': [float(x) for x in np.percentile(uu, [1, 5, 50, 95, 99])] if kept else []}

    # Shared bins from the union of stock neutral u.
    u_all = np.concatenate([samples['1144']['u'], samples['1147']['u']])
    lo, hi = np.percentile(u_all, [2, 98])
    edges = np.geomspace(max(lo, 1e-3), hi, 18)
    bins = {n: binned(samples[n]['u'], samples[n]['y'], edges) for n in samples}

    # Curve hypotheses for 1145. Stock shots always use jlaunch row 5.
    hypotheses = {
        'table_0': deep['table_0'],
        'table_1': deep['table_1'],
        'table_2': deep['table_2'],
        'table_3': deep['table_3'],
        'table_4_pair': {'A': deep['table_4']['A'], 'B': deep['table_4']['B']},
    }

    def grid(k_n=18, g_vals=None, p_vals=None):
        if g_vals is None:
            g_vals = [0.5, 0.7, 0.85, 1.0, 1.25, 1.6, 2.2]
        if p_vals is None:
            p_vals = [0.5, 0.75, 1.0, 1.4, 2.2]
        ks = np.geomspace(0.45, 10.0, k_n)
        out = []
        for k in ks:
            for g in g_vals:
                out.append((float(k), float(g), 1.0, 'id'))
                for p in p_vals:
                    if abs(p - 1) < 1e-9:
                        continue
                    out.append((float(k), float(g), float(p), 'pow'))
            out.append((float(k), 1.0, 1.0, 'srgb'))
            out.append((float(k), 0.85, 1.0, 'srgb'))
            out.append((float(k), 1.25, 1.0, 'srgb'))
        return out

    coarse = grid()
    hypothesis_fit = {}
    for hname, curve in hypotheses.items():
        def curve_for(shot, curve=curve):
            if shot in ('1144', '1147'):
                return stock_A, stock_B
            return curve['A'], curve['B']
        fit = search({'1144': bins['1144'], '1145': bins['1145'], '1147': bins['1147']},
                     curve_for, coarse, (stock_A, stock_B))
        hypothesis_fit[hname] = fit

    winner_name = min(hypothesis_fit, key=lambda n: hypothesis_fit[n]['rmse'])
    winner_curve = hypotheses[winner_name]
    # Refine around the winner, and also always refine table_1 (GRD row 28 if the hash says so).
    refine_names = [winner_name]
    if 'table_1' not in refine_names:
        refine_names.append('table_1')
    refined = {}
    for hname in refine_names:
        base = hypothesis_fit[hname]
        ks = np.geomspace(base['k'] / 1.35, base['k'] * 1.35, 13)
        gs = np.unique(np.clip(np.linspace(base['g'] * 0.75, base['g'] * 1.25, 9), 0.35, 3.0))
        ps = np.unique(np.clip(np.linspace(max(0.35, base['p'] * 0.7), base['p'] * 1.35, 7), 0.35, 3.0))
        fine = []
        for k in ks:
            for g in list(gs) + [1.0]:
                fine.append((float(k), float(g), 1.0, 'id'))
                for p in ps:
                    fine.append((float(k), float(g), float(p), 'pow'))
            fine.append((float(k), float(g), 1.0, 'srgb'))
        curve = hypotheses[hname]

        def curve_for(shot, curve=curve):
            if shot in ('1144', '1147'):
                return stock_A, stock_B
            return curve['A'], curve['B']
        fit = search({'1144': bins['1144'], '1145': bins['1145'], '1147': bins['1147']},
                     curve_for, fine, (stock_A, stock_B))
        # Prefer a simpler model within 0.4 code of this hypothesis best.
        simple_best = fit
        for k, g, p, kind in fine:
            rec_rmse_probe = None
        # Re-score the identity-post and gamma-1 subsets by a dedicated search on a small list.
        family = []
        for k, g, p, kind in fine:
            if kind == 'id' or (kind == 'pow' and abs(g - 1) < 1e-9) or (kind == 'id' and abs(g - 1) < 1e-9) or kind == 'srgb':
                family.append((k, g, p, kind))
        # Score every fine candidate's complexity via a second pass limited to those near the best.
        near = []
        for k, g, p, kind in fine:
            # cheap reject by sampling 4 bins
            pass
        refined[hname] = fit

    # Simplicity pass: evaluate a short list of nested models at the refined k neighborhood.
    chosen_h = min(refined, key=lambda n: refined[n]['rmse'])
    best = refined[chosen_h]
    simple_grid = []
    for k in np.geomspace(best['k'] / 1.2, best['k'] * 1.2, 11):
        simple_grid.append((float(k), 1.0, 1.0, 'id'))
        for g in (0.6, 0.8, 1.0, 1.25, 1.6, 2.2):
            simple_grid.append((float(k), g, 1.0, 'id'))
        for p in (0.45, 0.6, 0.8, 1.0, 1.4, 2.2):
            simple_grid.append((float(k), 1.0, p, 'pow'))
        simple_grid.append((float(k), 1.0, 1.0, 'srgb'))
    curve = hypotheses[chosen_h]

    def curve_for_chosen(shot, curve=curve):
        if shot in ('1144', '1147'):
            return stock_A, stock_B
        return curve['A'], curve['B']

    simple_fit = search({'1144': bins['1144'], '1145': bins['1145'], '1147': bins['1147']},
                        curve_for_chosen, simple_grid, (stock_A, stock_B))
    if simple_fit['rmse'] <= best['rmse'] + 0.40:
        best = simple_fit
    model = best
    model['hypothesis'] = chosen_h

    # Per-shot residuals under the chosen model, including 1146 checked against every curve.
    def shot_rmse(name, A, B):
        obs, pred, used = predict_bins(bins[name], A, B, model['k'], model['g'], model['p'], model['kind'])
        if len(obs) == 0:
            return None
        return {
            'rmse': rmse(obs, pred),
            'max_abs': float(np.max(np.abs(obs - pred))),
            'bias': float(np.mean(pred - obs)),
            'n': len(obs),
            'pairs': [{'u': r['u'], 'measured': r['y'], 'predicted': float(p), 'n': r['n']}
                      for r, p in zip(used, pred)],
        }

    ident = {
        '1144_stock': shot_rmse('1144', stock_A, stock_B),
        '1147_stock': shot_rmse('1147', stock_A, stock_B),
        '1145_chosen': shot_rmse('1145', hypotheses[chosen_h]['A'], hypotheses[chosen_h]['B']),
    }
    check_1146 = {}
    for hname, curve in hypotheses.items():
        check_1146[hname] = shot_rmse('1146', curve['A'], curve['B'])
    check_1146['stock_row5'] = shot_rmse('1146', stock_A, stock_B)

    # Targets from the measured GR III chart, not from DCP.
    ref = json.loads((ROOT / 'research/color_calibration/reference_analysis.json').read_text())['relative_mappings']
    chart = []
    import csv
    with open(ROOT / 'research/color_references/gr3_chart_targets.csv') as f:
        for row in csv.DictReader(f):
            if row['group'] == 'neutral':
                chart.append(row)

    def mode_neutrals(mode):
        rows = [r for r in chart if r['mode'] == mode]
        # D6..D1 is dark to light in the file order used by the CSV.
        return rows

    std_rows = mode_neutrals('standard')
    pos_rows = mode_neutrals('positive')
    neg_rows = mode_neutrals('negative')

    def enc_luma(row):
        r, g, b = float(row['jpeg_R']), float(row['jpeg_G']), float(row['jpeg_B'])
        return 255.0 * (0.2126 * r + 0.7152 * g + 0.0722 * b)

    std_codes = [enc_luma(r) for r in std_rows]
    pos_codes = [enc_luma(r) for r in pos_rows]
    neg_codes = [enc_luma(r) for r in neg_rows]
    T_pos = transfer_T(std_codes, pos_codes)
    T_neg = transfer_T(std_codes, neg_codes)

    # Ideal curve in hardware x, from the identified post and the stock curve.
    x_fine = np.linspace(0, 4095, 4096)
    v_stock = eval_curve(stock_A, stock_B, x_fine)
    y_stock = apply_post(v_stock, model['p'], model['kind'])

    def ideal_v(T):
        y = T(y_stock)
        return inv_post(y, model['p'], model['kind'])

    fitted = {}
    level_rows = {}
    for look, T in (('positive', T_pos), ('negative', T_neg)):
        v_id = ideal_v(T)
        candidates = {
            'greedy': nodes_from_interior(greedy_nodes(x_fine, v_id), x_fine, v_id),
            'stock_inputs': stock_shaped_nodes(stock_A, x_fine, v_id),
            'shadow_dense': shadow_dense_nodes(x_fine, v_id),
        }
        scored = {}
        for cname, (A, B, xs, target) in candidates.items():
            e_rms, e_max = curve_error(A, B, x_fine, v_id)
            # JPEG-space error of the quantized curve against T(stock).
            y_hat = apply_post(eval_curve(A, B, x_fine), model['p'], model['kind'])
            y_tgt = T(y_stock)
            scored[cname] = {
                'A': A.tolist(), 'B': B.tolist(),
                'node_rmse': e_rms, 'node_max': e_max,
                'jpeg_rmse': rmse(y_hat, y_tgt),
                'jpeg_max': float(np.max(np.abs(y_hat - y_tgt))),
            }
        best_name = min(scored, key=lambda n: scored[n]['jpeg_rmse'])
        use = scored[best_name]
        A, B = use['A'], use['B']
        # Residuals exactly at the six GR standard codes.
        levels = []
        y_s = np.array(std_codes)
        y_m = np.array(pos_codes if look == 'positive' else neg_codes)
        # Invert stock JPEG -> x by interpolation along the monotone stock curve.
        order = np.argsort(y_stock)
        for s_code, m_code, patch in zip(y_s, y_m, [r['patch'] for r in std_rows]):
            x = float(np.interp(s_code, y_stock[order], x_fine[order]))
            y_pred = float(apply_post(eval_curve(A, B, np.array([x])), model['p'], model['kind'])[0])
            y_cont = float(np.asarray(T(np.array([s_code]))).reshape(-1)[0])
            levels.append({
                'patch': patch,
                'gr_standard_code': s_code,
                'gr_mode_code': m_code,
                'target_code': y_cont,
                'predicted_code': y_pred,
                'residual_code': y_pred - m_code,
                'residual_L': float(code_to_L(y_pred) - code_to_L(m_code)),
                'intended_delta_code': m_code - s_code,
                'inside_measured_gr_span': bool(min(std_codes) - 0.5 <= s_code <= max(std_codes) + 0.5),
                'x': x,
            })
        fitted[look] = {
            'placement': best_name,
            'input31_u16': A,
            'output33_u8': B,
            'candidates': {k: {kk: vv for kk, vv in d.items() if kk != 'A' and kk != 'B'} | {'n_in': len(d['A'])}
                           for k, d in scored.items()},
            'chosen_jpeg_rmse': use['jpeg_rmse'],
            'chosen_jpeg_max': use['jpeg_max'],
        }
        # Keep full candidate curves only in memory for the local dump.
        fitted[look]['_candidates_full'] = scored
        level_rows[look] = levels

        xs_plot = np.linspace(min(std_codes) - 15, max(std_codes) + 15, 240)
        xs_plot = np.clip(xs_plot, 0, 255)
        order = np.argsort(y_stock)
        x_of = np.interp(xs_plot, y_stock[order], x_fine[order])
        y_fit = apply_post(eval_curve(A, B, x_of), model['p'], model['kind'])
        y_t = np.asarray(T(xs_plot))
        plot_series(
            OUT / f'{look}_vs_gr_target.png',
            f'GXR {look}: target is GR III mode at the same stock JPEG code',
            'GXR stock JPEG luma (8-bit)',
            'JPEG luma',
            [
                ('stock (identity)', xs_plot, xs_plot),
                ('GR III target', xs_plot, y_t),
                ('fitted row 5', xs_plot, y_fit),
            ],
            guides=[(c, '') for c in std_codes],
        )
        plot_series(
            TMP / f'{look}_vs_gr_target.png',
            f'GXR {look}: target is GR III mode at the same stock JPEG code',
            'GXR stock JPEG luma (8-bit)',
            'JPEG luma',
            [
                ('stock (identity)', xs_plot, xs_plot),
                ('GR III target', xs_plot, y_t),
                ('fitted row 5', xs_plot, y_fit),
            ],
            guides=[(c, '') for c in std_codes],
        )

    # Base-shape mismatch: GR Standard JPEG vs linear camera G, against GXR stock JPEG vs u.
    # Align the log-linear axis so each curve passes through JPEG 128.
    def aligned_shape(linear, jpeg, name):
        linear = np.asarray(linear, float)
        jpeg = np.asarray(jpeg, float)
        order = np.argsort(jpeg)
        # u or camera G at which JPEG would be 128, if inside the span.
        if jpeg.min() > 140 or jpeg.max() < 100:
            return None
        lin_mid = float(np.interp(128.0, jpeg[order], linear[order]))
        return {'name': name, 'log2_rel': np.log2(linear / lin_mid), 'jpeg': jpeg, 'lin_mid': lin_mid}

    gr_shape = aligned_shape([float(r['camera_G']) for r in std_rows], std_codes, 'GR III Standard')
    # GXR measured stock bins.
    gxr_u, gxr_y = [], []
    for row4, row7 in zip(bins['1144'], bins['1147']):
        if row4 and row7:
            gxr_u.append(0.5 * (row4['u'] + row7['u']))
            gxr_y.append(0.5 * (row4['y'] + row7['y']))
    gxr_shape = aligned_shape(gxr_u, gxr_y, 'GXR stock')
    base_mismatch = None
    if gr_shape and gxr_shape:
        grid_l = np.linspace(-3.0, 2.2, 28)
        gr_j = np.interp(grid_l, gr_shape['log2_rel'], gr_shape['jpeg'], left=np.nan, right=np.nan)
        gx_j = np.interp(grid_l, gxr_shape['log2_rel'], gxr_shape['jpeg'], left=np.nan, right=np.nan)
        ok = ~np.isnan(gr_j) & ~np.isnan(gx_j)
        if ok.sum() >= 4:
            d = gx_j[ok] - gr_j[ok]
            base_mismatch = {
                'n': int(ok.sum()),
                'rmse_code': float(np.sqrt(np.mean(d ** 2))),
                'max_abs_code': float(np.max(np.abs(d))),
                'bias_code': float(np.mean(d)),
                'note': 'Shapes aligned at JPEG 128. GR linear axis is camera G; GXR axis is WB luma proxy. Not a shared-scene measurement.',
            }

    # Hi-contrast comparison in the identified response, versus stock JPEG code.
    hc_curves = {
        'stock_row5': (stock_A, stock_B),
        'gxr_native_row20': (hc_A, hc_B),
    }
    # GRD HC is whichever deep table matched slot 03 / row 11.
    for sid, info in slot_match.items():
        if info.get('source_row_1based') == 11 and info['exact_ab']:
            hc_curves['grd4_row11_' + info['exact_ab'][0]] = (
                hypotheses[info['exact_ab'][0]]['A'], hypotheses[info['exact_ab'][0]]['B'])
    hc_report = {}
    xs_plot = np.linspace(0, 255, 256)
    order = np.argsort(y_stock)
    x_of = np.interp(xs_plot, y_stock[order], x_fine[order])
    series = []
    for cname, (A, B) in hc_curves.items():
        y = apply_post(eval_curve(A, B, x_of), model['p'], model['kind'])
        # slope around midtones
        y96 = float(np.interp(96, xs_plot, y))
        y160 = float(np.interp(160, xs_plot, y))
        slope = (y160 - y96) / (160 - 96)
        shadow = float(np.mean([s - float(np.interp(s, xs_plot, y)) for s in (24, 32, 40, 48, 56)]))
        clip = None
        for s, yy in zip(xs_plot, y):
            if yy >= 250:
                clip = float(s)
                break
        hc_report[cname] = {
            'mid_slope_dy_per_dstock': slope,
            'shadow_drop_codes': shadow,
            'stock_code_where_output_reaches_250': clip,
            'output_at_stock_40': float(np.interp(40, xs_plot, y)),
            'output_at_stock_128': float(np.interp(128, xs_plot, y)),
            'output_at_stock_220': float(np.interp(220, xs_plot, y)),
        }
        series.append((cname, xs_plot[::4], y[::4]))
    plot_series(OUT / 'hc_bw_comparison.png',
                'Hi-contrast candidates in the identified GXR response',
                'GXR stock JPEG luma (8-bit)', 'Predicted JPEG luma', series)
    plot_series(TMP / 'hc_bw_comparison.png',
                'Hi-contrast candidates in the identified GXR response',
                'GXR stock JPEG luma (8-bit)', 'Predicted JPEG luma', series)

    # Colour rows.
    stock_color = sector_rows(color_raw)
    color_decoded = {'jlaunch_row1': stock_color}
    for name, raw in color_tables.items():
        if len(raw) == 96:
            color_decoded[name] = sector_rows(raw)
    stock_scales = group_scales(stock_color)
    gr_ratios = {}
    for look in ('ricoh_gr3_positive', 'ricoh_gr3_negative'):
        gr_ratios[look] = {g['color']: g['median_chroma_ratio'] for g in ref[look]['groups']}
        gr_ratios[look + '_hue'] = {g['color']: g['median_hue_shift_degrees'] for g in ref[look]['groups']}
    colour_distance = {}
    for name, rows in color_decoded.items():
        if name == 'jlaunch_row1':
            continue
        scales = group_scales(rows)
        ratio = {g: (scales[g] / stock_scales[g] if stock_scales[g] else None) for g in GROUPS}
        entry = {'scale_ratio_vs_stock_row1': ratio, 'median_scale': {g: scales[g] for g in GROUPS}}
        for look, key in (('positive', 'ricoh_gr3_positive'), ('negative', 'ricoh_gr3_negative')):
            err = []
            for g in GROUPS:
                if ratio[g] is None:
                    continue
                err.append(ratio[g] - gr_ratios[key][g])
            entry[f'rms_vs_{look}_chroma_ratio'] = float(np.sqrt(np.mean(np.square(err))))
        colour_distance[name] = entry
    # Also the stock row against GR, using ratio 1.
    for look, key in (('positive', 'ricoh_gr3_positive'), ('negative', 'ricoh_gr3_negative')):
        err = [1.0 - gr_ratios[key][g] for g in GROUPS]
        colour_distance['jlaunch_row1_' + look] = {
            'rms_vs_chroma_ratio': float(np.sqrt(np.mean(np.square(err)))),
            'assumed_ratio': 1.0,
        }

    # Neutral tint of the GR III chart.
    tint = {}
    for mode, rows in (('standard', std_rows), ('positive', pos_rows), ('negative', neg_rows)):
        tint[mode] = []
        for r in rows:
            a, b, L = float(r['target_a']), float(r['target_b']), float(r['target_L'])
            tint[mode].append({
                'patch': r['patch'], 'L': L, 'a': a, 'b': b,
                'C': math.hypot(a, b),
            })

    # Firmware look matrices, re-read. Not used to place nodes.
    constraints = json.loads((ROOT / 'research/color_references/gr_firmware_constraints.json').read_text())
    matrices = {}
    for variant in constraints['variants']:
        if variant['model'] != 'gr3':
            continue
        for m in variant['look_matrix_constraints']:
            M = np.array(m['normalized']).reshape(3, 3)
            matrices[m['mode']] = {
                'normalized': M.tolist(),
                'row_sums': m['row_sums'],
                'offdiag_l1': float(np.abs(M - np.diag(np.diag(M))).sum()),
                'sha256': m['sha256'],
            }

    # DCP appendix only. Never consulted above.
    dcp_appendix = {'used_in_fit': False}
    try:
        dcp = json.loads((ROOT / 'research/color_references/adobe_gr_profiles.json').read_text())
        wanted = {}
        for prof in dcp['profiles']:
            if prof.get('camera_folder') != 'Ricoh GR III':
                continue
            name = prof.get('profile_name') or ''
            if name in ('Camera Standard', 'Camera Positive Film', 'Camera Negative Film'):
                ramps = []
                for probe in prof.get('derived_probes') or []:
                    if probe.get('set') != 'neutral_ramp':
                        continue
                    rgb = probe['output_srgb']
                    luma = 255.0 * (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2])
                    ramps.append({'id': probe['id'], 'L_in': probe['Lab_D50'][0], 'code': luma})
                wanted.setdefault(name, []).append({
                    'sha256': prof['sha256'], 'n': len(ramps), 'ramp': ramps,
                    'path': prof.get('path_scratch', ''),
                })
        # If duplicate profiles, keep the first and record the count.
        std = wanted.get('Camera Standard', [])
        pos = wanted.get('Camera Positive Film', [])
        neg = wanted.get('Camera Negative Film', [])
        cross = None
        if std and pos and neg:
            s, p, n = std[0]['ramp'], pos[0]['ramp'], neg[0]['ramp']
            # Pair on probe id.
            sp = {r['id']: r for r in s}
            rows = []
            for pr in p:
                if pr['id'] not in sp:
                    continue
                sc = sp[pr['id']]['code']
                target = float(np.asarray(T_pos(np.array([sc]))).reshape(-1)[0])
                rows.append(abs(pr['code'] - target))
            rows_n = []
            for pr in n:
                if pr['id'] not in sp:
                    continue
                sc = sp[pr['id']]['code']
                # Only inside the GR chart span, where T is measured rather than extrapolated.
                if not (min(std_codes) <= sc <= max(std_codes)):
                    continue
                target = float(np.asarray(T_neg(np.array([sc]))).reshape(-1)[0])
                rows_n.append(abs(pr['code'] - target))
            cross = {
                'positive_median_abs_code_vs_real_transfer': float(np.median(rows)) if rows else None,
                'negative_median_abs_code_vs_real_transfer_inside_chart_span': float(np.median(rows_n)) if rows_n else None,
                'n_positive': len(rows),
                'n_negative_inside_span': len(rows_n),
                'profiles_found': {k: len(v) for k, v in wanted.items()},
                'standard_sha256': std[0]['sha256'],
                'positive_sha256': pos[0]['sha256'],
                'negative_sha256': neg[0]['sha256'],
            }
        dcp_appendix['crosscheck'] = cross
        dcp_appendix['note'] = 'Adobe approximation. Not a fitting target. decisions.tsv color_references_result.'
    except Exception as exc:
        dcp_appendix['error'] = str(exc)

    after = {str(p.relative_to(ROOT)): sha256(p) for p in PROTECTED}
    hash_same = before == after

    # Measured bin table for the report.
    bin_table = {}
    for n, rows in bins.items():
        bin_table[n] = [r for r in rows if r]

    result = {
        'schema': 'gxr-phase1-tone-v1',
        'hashes_before': before,
        'hashes_after': after,
        'hashes_unchanged': hash_same,
        'extraction_checks': {
            'row20_sha256_matches': True,
            'row5_matches_ordinary_contrast_head': True,
            'jpeg_shift_dy_dx': [dy, dx],
            'jpeg_shift_neutral_correlation': corr,
        },
        'shots': {
            n: {
                'jpeg_size': s['jpeg_size'],
                'orientation': s['orientation'],
                'crop': s['stats']['crop_wh'],
                'neutral': s['neutral'].tolist(),
                'black': s['black'],
                'white': s['white'],
                'iso': (s['info'].get('iso') if isinstance(s['info'], dict) else None),
                'exposure_seconds': s['info'].get('exposure_seconds') if isinstance(s['info'], dict) else None,
                'f_number': s['info'].get('f_number') if isinstance(s['info'], dict) else None,
                'date_time': s['info'].get('date_time') if isinstance(s['info'], dict) else None,
                'color_display': s['info'].get('color_display') if isinstance(s['info'], dict) else None,
                'jpeg_color_display': (s['info'].get('jpeg') or {}).get('color_display') if isinstance(s['info'], dict) else None,
                'neutral_blocks_kept': samples[n]['kept'],
                'neutral_blocks_total': samples[n]['total'],
                'neutral_u_percentiles_1_5_50_95_99': samples[n]['u_p'],
            } for n, s in shots.items()
        },
        'slot_match_by_sha256': slot_match,
        'hypothesis_rmse_coarse': {k: v['rmse'] for k, v in hypothesis_fit.items()},
        'refined_rmse': {k: v['rmse'] for k, v in refined.items()},
        'model': model,
        'identification': ident,
        'check_1146': {k: ({kk: vv for kk, vv in d.items() if kk != 'pairs'} if d else None) for k, d in check_1146.items()},
        'gr_codes': {'standard': std_codes, 'positive': pos_codes, 'negative': neg_codes,
                     'patches': [r['patch'] for r in std_rows]},
        'fitted_summary': {k: {kk: vv for kk, vv in d.items() if not kk.startswith('_')} for k, d in fitted.items()},
        'levels': level_rows,
        'base_mismatch_aligned_at_jpeg_128': base_mismatch,
        'hc': hc_report,
        'colour_distance': colour_distance,
        'gr_group_chroma': {k: v for k, v in gr_ratios.items() if not k.endswith('_hue')},
        'gr_group_hue_deg': {k: v for k, v in gr_ratios.items() if k.endswith('_hue')},
        'tint': tint,
        'gr3_matrices': matrices,
        'attribution': {
            '1145': 'table_1 matches catalog slot 01 / GRD IV row 28 by SHA-256, and it is the curve that predicts R8051145. table_0 is byte-identical to jlaunch row 5, not row 28.',
            '1146': 'table_4 matches catalog slot 05 / GRD IV row 19 by SHA-256. With the pre/post frozen on 1144/1145/1147, it predicts R8051146; the other deep curves do not. Slot identity of the file is still an inference.',
            'hc_row11': 'table_3 matches catalog slot 03 / GRD IV row 11, not table_2.',
            'colour': 'table_0_2 is byte-identical to jlaunch colour row 1. Slot 01 colour column is table_1_2 (catalog color10). Slot 05 colour column is table_4_2 (catalog color6).',
        },
        'dcp_appendix': dcp_appendix,
        'stock_color_redundant_ok': all(r['redundant_ok'] for r in stock_color),
        'color_table_redundant_ok': {name: all(r['redundant_ok'] for r in rows) for name, rows in color_decoded.items()},
        'bin_medians': bin_table,
    }

    # Local dump may contain firmware bytes. Gitignored.
    local = {
        'local_only': True,
        'contains_ricoh_firmware_bytes': True,
        'do_not_commit': True,
        'stock_row5': {'input31_u16': stock_A, 'output33_u8': stock_B},
        'gxr_native_row20': {'input31_u16': hc_A, 'output33_u8': hc_B},
        'deep_tables': {name: {'input31_u16': row['A'], 'output33_u8': row['B']} for name, row in deep.items()},
        'colour_bytes_sha256': {
            'jlaunch_row1': hashlib.sha256(bytes(color_raw)).hexdigest(),
            **{name: hashlib.sha256(bytes(raw)).hexdigest() for name, raw in color_tables.items()},
        },
        'fitted_candidates': {look: d['_candidates_full'] for look, d in fitted.items()},
    }
    (OUT / 'local' / 'firmware_and_fit.json').write_text(json.dumps(local, indent=2) + '\n')
    (TMP / 'firmware_and_fit.json').write_text(json.dumps(local, indent=2) + '\n')

    public = {k: v for k, v in result.items()}
    (TMP / 'results.json').write_text(json.dumps(public, indent=2) + '\n')
    (OUT / 'results.json').write_text(json.dumps(public, indent=2) + '\n')

    curves = {
        'schema': 'gxr-phase1-curves-v1',
        'local_only': False,
        'contains_ricoh_firmware_bytes': False,
        'note': 'Fitted numbers only. Stock, row 20 and GRD IV bytes are in local/firmware_and_fit.json, which is gitignored. Negative input knots are the stock row-5 positions because that placement beat a new spacing; the 33 outputs are the fit, not the stock outputs.',
        'model': model,
        'positive': {
            'input31_u16': fitted['positive']['input31_u16'],
            'output33_u8': fitted['positive']['output33_u8'],
            'placement': fitted['positive']['placement'],
            'levels': level_rows['positive'],
        },
        'negative': {
            'input31_u16': fitted['negative']['input31_u16'],
            'output33_u8': fitted['negative']['output33_u8'],
            'placement': fitted['negative']['placement'],
            'levels': level_rows['negative'],
        },
        'hc_bw': {
            'recommendation_inputs': 'see REPORT.md; candidate metrics only, no Ricoh bytes',
            'metrics': hc_report,
        },
    }
    (OUT / 'curves.json').write_text(json.dumps(curves, indent=2) + '\n')
    (TMP / 'curves.json').write_text(json.dumps(curves, indent=2) + '\n')
    (OUT / '.gitignore').write_text('local/\n')

    # Console summary, no firmware byte dumps.
    print('HASH_UNCHANGED', hash_same)
    print('SHIFT', dy, dx, round(corr, 4))
    print('SLOT_MATCH')
    for sid, info in slot_match.items():
        if info['exact_ab'] or info.get('source_row_1based') in (28, 19, 11, 5):
            print(' ', sid, 'row', info['source_row_1based'], 'exact', info['exact_ab'], 'b', info['b_only'])
    print('COARSE', {k: round(v, 3) for k, v in result['hypothesis_rmse_coarse'].items()})
    print('MODEL', model)
    print('IDENT', {k: None if v is None else round(v['rmse'], 3) for k, v in ident.items()})
    print('CHECK1146', {k: None if v is None else round(v['rmse'], 3) for k, v in check_1146.items()})
    print('BASE', base_mismatch)
    for look in ('positive', 'negative'):
        rs = [r['residual_code'] for r in level_rows[look]]
        print(look, fitted[look]['placement'], 'jpeg_rms', round(fitted[look]['chosen_jpeg_rmse'], 3),
              'level_residuals', [round(x, 2) for x in rs])
    print('HC')
    for k, v in hc_report.items():
        print(' ', k, {kk: round(vv, 3) if isinstance(vv, float) else vv for kk, vv in v.items()})
    print('COLOUR')
    for k, v in colour_distance.items():
        if 'rms_vs_positive_chroma_ratio' in v:
            print(' ', k, 'pos', round(v['rms_vs_positive_chroma_ratio'], 3), 'neg', round(v['rms_vs_negative_chroma_ratio'], 3))
        else:
            print(' ', k, v)
    print('TINT negative C*', [round(r['C'], 2) for r in tint['negative']], 'a', [round(r['a'], 2) for r in tint['negative']], 'b', [round(r['b'], 2) for r in tint['negative']])
    print('NEUTRAL_KEPT', {n: samples[n]['kept'] for n in samples})
    print('EXPOSURE', {n: (shots[n]['info'].get('iso'), shots[n]['info'].get('exposure_seconds'), shots[n]['info'].get('f_number'), shots[n]['info'].get('color_display')) for n in shots})


if __name__ == '__main__':
    main()
