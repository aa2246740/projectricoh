"""Chart-v2 homography and independent Hamming / printed-digit readers."""
import itertools
import math
import numpy as np
from PIL import Image
from scipy import ndimage
from analyzer_runtime import HERE, require

ORDER = ('TL', 'TR', 'BR', 'BL')


def cells(g, H, rectangles, ar):
    values = []
    off = np.array(list(itertools.product((-.16, 0., .16), repeat=2)))
    for x0, y0, x1, y1 in rectangles:
        xy = np.array([(x0+x1)/2, (y0+y1)/2]) + off * [x1-x0, y1-y0]
        values.append(float(np.median(ar.sample_bilinear(g, ar.apply_h(H, xy)))))
    return np.asarray(values)


def decode_hamming(bits):
    """Extended Hamming SECDED. Two errors are rejected, never nearest-page guessed."""
    b = np.asarray(bits, int).copy()
    syndrome = sum(weight * int(np.bitwise_xor.reduce(b[indices])) for weight, indices in
                   ((1, [0, 2, 4, 6]), (2, [1, 2, 5, 6]), (4, [3, 4, 5, 6])))
    parity = int(np.bitwise_xor.reduce(b))
    corrected = None
    if syndrome and not parity:
        return {'valid': False, 'reason': 'detected-double-bit-error', 'syndrome': syndrome}
    if parity:
        corrected = syndrome-1 if syndrome else 7
        b[corrected] ^= 1
    page = sum(int(b[k]) << i for i, k in enumerate((2, 4, 5, 6)))
    return {'valid': page in range(1, 7), 'page': page, 'corrected_bit': corrected,
            'syndrome': syndrome, 'parity': parity}


def read_code(g, H, layout, ar):
    code = layout['pages'][1]['page_code']
    rects = [x['bbox_px'] for x in code['cells']]
    v = cells(g, H, rects, ar).reshape(2, 12)
    diff = v[0]-v[1]
    # Differential decisions suppress exposure, WB and slowly varying illumination.
    bits = (diff > 0).astype(int)
    sync_errors = int(np.count_nonzero(bits[:4] != [1, 1, 0, 1]))
    contrast = np.abs(diff)
    weak = np.flatnonzero(contrast < .018).tolist()
    pair = decode_hamming(bits[4:])
    # Read each row separately too, so a band over one row cannot masquerade as ECC.
    row_reads = []
    for j in range(2):
        low, high = np.percentile(v[j], (15, 85))
        b = (v[j] > (low+high)/2).astype(int)
        if j:
            b ^= 1
        row_reads.append(decode_hamming(b[4:]))
    agreeing = [r['page'] for r in row_reads if r['valid']]
    valid = bool(pair['valid'] and sync_errors <= 1 and len(weak) <= 1
                 and (not agreeing or all(p == pair['page'] for p in agreeing)))
    return {**pair, 'valid': valid, 'row_reads': row_reads, 'sync_errors': sync_errors,
            'weak_cells': weak, 'cell_values': v.tolist(), 'differential_bits': bits.tolist(),
            'minimum_pair_contrast': float(contrast.min())}


def correlation(a, b):
    a, b = np.asarray(a).ravel(), np.asarray(b).ravel()
    a, b = a-a.mean(), b-b.mean()
    den = np.linalg.norm(a)*np.linalg.norm(b)
    return float(a @ b / den) if den > 1e-8 else 0.


_TEXT = None


def read_text(g, H, layout, ar):
    """Read the actual page digit in Pn/6, using the sealed bitmap glyphs."""
    global _TEXT
    # The generator uses 5x7 glyphs at eight source pixels per cell.
    yy, xx = np.meshgrid(np.arange(112.5, 168., 2), np.arange(1684.5, 1724., 2), indexing='ij')
    pts = np.stack([xx, yy], -1)
    observed = ar.sample_bilinear(g, ar.apply_h(H, pts))
    if _TEXT is None:
        _TEXT = {}
        for page in range(1, 7):
            with Image.open(HERE / layout['pages'][page]['file']) as im:
                tile = np.asarray(im.crop((1664, 92, 1744, 188)).convert('L'), float)/255.
            _TEXT[page] = [ndimage.gaussian_filter(tile, s)[20:76:2, 20:60:2]
                           for s in (0., 4., 7., 10., 13.)]
    scores = {p: max(correlation(observed, x) for x in refs) for p, refs in _TEXT.items()}
    ranked = sorted(scores, key=scores.get, reverse=True)
    page = ranked[0]
    margin = scores[page]-scores[ranked[1]]
    return {'page': page, 'valid': scores[page] >= .55 and margin >= .025,
            'correlation': scores[page], 'margin': margin, 'scores': scores,
            'method': 'P1/6..P6/6 digit-template correlation, read from image'}


def identify(g, H, layout, ar):
    code, text = read_code(g, H, layout, ar), read_text(g, H, layout, ar)
    if code['valid'] and text['valid']:
        require(code['page'] == text['page'], f'Hamming/文字页码冲突: {code["page"]}/{text["page"]}')
        return {'page': code['page'], 'confidence': 'hamming-and-text', 'hamming': code, 'text': text}
    if code['valid']:
        return {'page': code['page'], 'confidence': 'hamming-only', 'hamming': code, 'text': text}
    if text['valid'] and text['correlation'] >= .75 and text['margin'] >= .07:
        return {'page': text['page'], 'confidence': 'text-only', 'hamming': code, 'text': text}
    raise ValueError('Hamming 和文字都不足以可靠识页')


def border_candidates(g):
    """Find enclosed bright rims, including an 8x8 checker blurred into grey."""
    f = max(1, int(round(g.shape[1]/1400)))
    a = ndimage.gaussian_filter(g[::f, ::f], .6)
    lo, hi = np.percentile(a, (8, 99.8))
    out = []
    for t in (.52, .64, .75, .84):
        binary = ndimage.binary_closing(a > lo+t*(hi-lo), iterations=1)
        labels, _ = ndimage.label(binary)
        for k, sl in enumerate(ndimage.find_objects(labels)):
            hh, ww = sl[0].stop-sl[0].start, sl[1].stop-sl[1].start
            if min(hh, ww) < max(14, .012*a.shape[1]) or max(hh, ww) > .14*a.shape[1]:
                continue
            if not .5 < hh/ww < 1.8:
                continue
            comp = labels[sl] == k+1
            fill = ndimage.binary_fill_holes(comp)
            area = int(fill.sum())
            holes = float((fill.sum()-comp.sum())/max(area, 1))
            occupancy = area/(hh*ww)
            if holes < .10 or occupancy < .55:
                continue
            cy, cx = ndimage.center_of_mass(fill)
            p = np.array([(cx+sl[1].start+.5)*f, (cy+sl[0].start+.5)*f])
            candidate = {'xy': p, 'size_px': math.sqrt(area)*f,
                         'score': holes*occupancy, 'hole_fraction': holes}
            close = next((i for i, q in enumerate(out) if np.linalg.norm(p-q['xy']) < .35*q['size_px']), None)
            if close is None:
                out.append(candidate)
            elif candidate['score'] > out[close]['score']:
                out[close] = candidate
    return sorted(out, key=lambda x: x['score'], reverse=True)[:10]


def refine_borders(g, H, layout, ar):
    """Refine against the outside of the white rim, not the disappearing cells."""
    src, dst = [], []
    for _ in range(3):
        src, dst = [], []
        for m in layout['markers']:
            x0, y0, x1, y1 = m['bbox_px']
            for t in np.linspace(.22, .78, 7):
                for p, normal in (([x0, y0+t*(y1-y0)], [1, 0]),
                                  ([x1, y0+t*(y1-y0)], [-1, 0]),
                                  ([x0+t*(x1-x0), y0], [0, 1]),
                                  ([x0+t*(x1-x0), y1], [0, -1])):
                    shifts = np.linspace(-14, 14, 57)
                    pts = np.asarray(p) + shifts[:, None]*normal
                    vv = ar.sample_bilinear(g, ar.apply_h(H, pts))
                    derivative = np.gradient(ndimage.gaussian_filter1d(vv, 1.2))
                    k = int(np.argmax(derivative))
                    if not 2 <= k < len(shifts)-2 or derivative[k] < .001:
                        continue
                    a, b, c = derivative[k-1:k+2]
                    den = a-2*b+c
                    offset = float(np.clip(.5*(a-c)/den, -.5, .5)) if den else 0.
                    shift = shifts[k]+offset*(shifts[1]-shifts[0])
                    src.append(p)
                    dst.append(ar.apply_h(H, np.asarray(p)+shift*np.asarray(normal)))
        if len(src) < 24:
            break
        src, dst = np.asarray(src), np.asarray(dst)
        H2 = ar.dlt(src, dst)
        res = np.linalg.norm(ar.apply_h(H2, src)-dst, axis=1)
        keep = res < max(1.5, float(np.median(res))*3.)
        if keep.sum() >= 24:
            H2 = ar.dlt(src[keep], dst[keep])
        H = H2
    return H, len(src)


def fallback(g, layout, ar):
    candidates = border_candidates(g)
    require(len(candidates) >= 4, f'white-rim candidates <4: {len(candidates)}')
    mk = {m['corner']: m for m in layout['markers']}
    src = np.array([mk[k]['center_px'] for k in ORDER])
    hypotheses = []
    for combo in itertools.combinations(candidates[:9], 4):
        pts = np.array([q['xy'] for q in combo])
        angle = np.argsort(np.arctan2(*(pts-pts.mean(0))[:, ::-1].T))
        for mirror in (False, True):
            seq = angle[::-1] if mirror else angle
            for rot in range(4):
                dst = pts[np.roll(seq, -rot)]
                u, v = dst[1]-dst[0], dst[3]-dst[0]
                if abs(u[0]*v[1]-u[1]*v[0]) < .08*g.size:
                    continue
                H = ar.dlt(src, dst)
                cc = {k: ar.checker_corr(g, H, mk[k], mk[k]['n_cells']) for k in ORDER}
                # TL/TR still carry direction; BL is never classified by a cell count.
                if cc['TL'] < .35 or cc['TR'] < .25 or sum(cc.values()) < 1.7:
                    continue
                hypotheses.append((sum(cc.values()), H, cc, mirror))
    require(hypotheses, '无可验证的外白框单应候选')
    errors = []
    for score, H, corr, mirror in sorted(hypotheses, key=lambda x: x[0], reverse=True)[:8]:
        H, used = refine_borders(g, H, layout, ar)
        try:
            ident = identify(g, H, layout, ar)
        except ValueError as e:
            errors.append(str(e))
            continue
        return {'H': H, 'Hinv': np.linalg.inv(H), 'method': 'blur-robust-outer-white-rims',
                'marker_correlations': corr, 'marker_score': score, 'mirrored': mirror,
                'border_points_used': used, 'candidate_count': len(candidates)}, ident
    raise ValueError('外白框拟合后页码失败: ' + '; '.join(errors[:3]))


def locate(rgb, layout, ar, force_fallback=False):
    g = ar.gray_of(rgb)
    failure = None
    if not force_fallback:
        try:
            geo = ar.locate_screen(rgb, {'markers': {m['corner']: m for m in layout['markers']}})
            ident = identify(g, geo['H'], layout, ar)
            geo['method'] = 'original-locate_screen'
            return geo, ident
        except ValueError as e:
            failure = str(e)
    geo, ident = fallback(g, layout, ar)
    geo['original_failure'] = failure
    return geo, ident


def locate_white(rgb, layout, ar):
    """Recognise a large continuous near-neutral field; no orientation claim."""
    a = np.asarray(rgb[::4, ::4], float)
    y = a @ [.299, .587, .114]
    threshold = max(float(np.percentile(y, 95))*.55, 25.)
    labels, _ = ndimage.label(y > threshold)
    sizes = np.bincount(labels.ravel()); sizes[0] = 0
    require(sizes.size > 1 and sizes.max() > .22*y.size, '不是大面积白页')
    label = int(np.argmax(sizes))
    mask = labels == label
    coords = np.column_stack(np.nonzero(mask))[:, ::-1]*4.+2.
    z = coords[:, 0]+coords[:, 1]; d = coords[:, 0]-coords[:, 1]
    dst = coords[[np.argmin(z), np.argmax(d), np.argmax(z), np.argmin(d)]]
    W, HH = layout['canvas_px']
    H = ar.dlt([[0, 0], [W, 0], [W, HH], [0, HH]], dst)
    rect = [W*.25, HH*.25, W*.75, HH*.75]
    roi = ar.roi_mask({'H': H, 'Hinv': np.linalg.inv(H)}, rect, rgb.shape)
    require(roi is not None, '白页 ROI 无效')
    ya, yb, xa, xb, keep, _ = roi
    block = np.asarray(rgb[ya:yb, xa:xb], float)[keep]
    luma = block @ [.299, .587, .114]
    chroma = np.median(block.max(1)-block.min(1))
    # A chart's differently coloured cells and gutters violate these conditions.
    require(float(np.std(luma)/max(np.mean(luma), 1)) < .12 and chroma < 32,
            '大亮区域不满足白页均匀/中性条件')
    return {'H': H, 'Hinv': np.linalg.inv(H), 'method': 'white-field-component',
            'orientation': 'unknown (uniform field)', 'field_fraction': float(mask.mean())}, {
                'page': 0, 'confidence': 'white-field', 'white_luma_cv': float(np.std(luma)/np.mean(luma))}
