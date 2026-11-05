"""Offline grid geometry and page identity. No vendor data or image fixtures."""
import numpy as np
from PIL import Image
from scipy import ndimage, optimize, signal


def project(H, xy):
    xy = np.asarray(xy, float)
    q = np.c_[xy.reshape(-1, 2), np.ones(xy.size // 2)] @ np.asarray(H).T
    return (q[:, :2] / q[:, 2:]).reshape(xy.shape)


def homography(source, target):
    A, b = [], []
    for (x, y), (u, v) in zip(source, target):
        A.extend(([x, y, 1, 0, 0, 0, -u*x, -u*y], [0, 0, 0, x, y, 1, -v*x, -v*y]))
        b.extend((u, v))
    return np.r_[np.linalg.lstsq(A, b, rcond=None)[0], 1].reshape(3, 3)


def _clusters(x, n):
    means = np.quantile(x, (np.arange(n) + .5) / n)
    for _ in range(40):
        label = np.argmin(abs(x[:, None] - means), axis=1)
        update = np.array([np.median(x[label == k]) if np.any(label == k) else means[k] for k in range(n)])
        if np.max(abs(update - means)) < .001:
            break
        means = np.sort(update)
    return np.argmin(abs(x[:, None] - means), axis=1), means


def locate_grid(rgb, cols=8, rows=6):
    """Fit each frame independently from flat patch interiors, then hold out cells.

    No nominal patch colour enters geometry. Reject incomplete/ambiguous grids;
    callers can supply four corners in a local manifest instead.
    """
    h0, w0 = rgb.shape[:2]
    w = min(1200, w0)
    h = round(h0 * w / w0)
    a = np.asarray(Image.fromarray(rgb).resize((w, h), Image.Resampling.BOX), float)
    smooth = ndimage.gaussian_filter(a, (1.0, 1.0, 0))
    gx = np.max(abs(ndimage.sobel(smooth, axis=1)), axis=2) / 8
    gy = np.max(abs(ndimage.sobel(smooth, axis=0)), axis=2) / 8
    gradient = np.hypot(gx, gy)
    attempts = []
    for threshold in (1.8, 3.5, 6., 10.):
        flat = gradient < threshold
        flat = ndimage.binary_erosion(flat, iterations=2, border_value=0)
        labels, _ = ndimage.label(flat)
        components = []
        for i, sl in enumerate(ndimage.find_objects(labels)):
            yy, xx = sl
            bh, bw = yy.stop - yy.start, xx.stop - xx.start
            if not (w*.018 < bw < w*.22 and h*.018 < bh < h*.30 and .45 < bw/bh < 4.5):
                continue
            mask = labels[sl] == i+1
            count = int(mask.sum())
            if count < bw*bh*.50:
                continue
            components.append(dict(center=[(xx.start+xx.stop)/2/w, (yy.start+yy.stop)/2/h],
                wh=[bw/w, bh/h], area=count, label=i+1, bbox=[xx.start, yy.start, xx.stop, yy.stop]))
        if len(components) < max(12, cols*rows*.48):
            continue
        # Select a size mode, leaving enough missing dark or grey-on-grey patches.
        areas = np.array([c['area'] for c in components])
        best = max(range(len(areas)), key=lambda k: np.sum(abs(np.log(areas/areas[k])) < .65))
        chosen = [c for c in components if abs(np.log(c['area']/areas[best])) < .85]
        if len(chosen) < max(12, cols*rows*.48):
            continue
        centers = np.array([c['center'] for c in chosen])
        cc, cm = _clusters(centers[:, 0], cols)
        rr, rm = _clusters(centers[:, 1], rows)
        source = np.c_[(cc+.5)/cols, (rr+.5)/rows]
        unique = {}
        for i, cell in enumerate(zip(rr, cc)):
            old = unique.get(cell)
            if old is None or chosen[i]['area'] > chosen[old]['area']:
                unique[cell] = i
        ix = np.array(list(unique.values()))
        source, target = source[ix], centers[ix]
        H0 = homography(source, target)
        scale = np.array([w, h])
        fit = optimize.least_squares(lambda p: ((project(np.r_[p, 1].reshape(3, 3), source)-target)*scale).ravel(),
            H0.ravel()[:8], loss='soft_l1', f_scale=2., max_nfev=100)
        H = np.r_[fit.x, 1].reshape(3, 3)
        residual = np.linalg.norm((project(H, source)-target)*scale, axis=1)
        pitch = np.median(np.diff(cm))*w
        keep = residual < max(3., pitch*.12)
        if keep.sum() < max(12, cols*rows*.48):
            continue
        H = homography(source[keep], target[keep])
        corners = project(H, [[0, 0], [1, 0], [1, 1], [0, 1]])
        if np.any(corners < -.035) or np.any(corners > 1.035):
            continue
        if np.ptp(corners[:, 0]) < .25 or np.ptp(corners[:, 1]) < .25:
            continue
        parity = ((rr[ix]+cc[ix]) % 2).astype(bool)
        train, held = keep & ~parity, keep & parity
        if train.sum() < 7 or held.sum() < 5:
            continue
        holdH = homography(source[train], target[train])
        hold_error = np.linalg.norm((project(holdH, source[held])-target[held])*scale, axis=1)
        p95 = float(np.percentile(hold_error, 95))
        if p95 > max(5., pitch*.10):
            continue
        # Interior components shrink at their edge. Conservative gutter estimates
        # only alter the definition of central fractions, not patch centres.
        inv = np.linalg.inv(H)
        extents = []
        for ci in ix[keep]:
            x0, y0, x1, y1 = chosen[ci]['bbox']
            p = project(inv, [[x0/w, y0/h], [x1/w, y1/h]])
            extents.append(abs(p[1]-p[0])*[cols, rows])
        sizes = np.clip(np.median(extents, axis=0)+.035, .70, .985)
        result = dict(method='independent-flat-interiors-homography', H=H, corners_normalized=corners,
            component_count=len(components), inliers=int(keep.sum()), heldout_count=int(held.sum()),
            heldout_p95_px_at_work_width=p95, work_width=w, patch_fraction_of_pitch=sizes,
            threshold=threshold, source_centers=source[keep], image_centers=target[keep])
        attempts.append(result)
    if not attempts:
        raise ValueError('自动网格定位不足；在 local manifest 填该帧 corners，顺序 TL/TR/BR/BL')
    result = max(attempts, key=lambda x: (x['inliers'], -x['heldout_p95_px_at_work_width']))
    return result['H'], result


def grid_patches(page, sizes=(.96, .95), cols=8, rows=6):
    sx, sy = sizes
    return [dict(id=p['id'], group=p.get('group', 'unknown'), rgb=p.get('rgb8_srgb', [0, 0, 0]),
        swatch=dict(x=(p['col']+(1-sx)/2)/cols, y=(p['row']+(1-sy)/2)/rows,
                    w=sx/cols, h=sy/rows)) for p in page['patches']]


def quick_samples(rgb, H, cols=8, rows=6):
    h, w = rgb.shape[:2]
    offsets = np.array([[dx, dy] for dy in (-.08, 0, .08) for dx in (-.08, 0, .08)])
    xy = np.array([[(c+.5)/cols, (r+.5)/rows] for r in range(rows) for c in range(cols)])
    pts = project(H, xy[:, None, :]+offsets/[cols, rows])*[w, h]-.5
    return np.stack([ndimage.map_coordinates(rgb[..., k].astype(float), [pts[..., 1], pts[..., 0]], order=1) for k in range(3)], -1).mean(1)


def identify_page(observed, pages):
    """Cross-validated colour-pattern match; CSS values are identity hints only."""
    y = np.asarray(observed, float)/255
    scores = {}
    for page in pages:
        x = np.array([p['rgb8_srgb'] for p in page['patches']], float)/255
        X = np.c_[np.ones(len(x)), x]
        pred = np.empty_like(y)
        # Interleaved cells put neutrals and memory colours in every training fold.
        for fold in range(4):
            held = np.arange(len(x)) % 4 == fold
            coef = np.linalg.lstsq(X[~held], y[~held], rcond=None)[0]
            pred[held] = X[held]@coef
        error = np.linalg.norm(pred-y, axis=1)
        scores[page['id']] = float(np.sqrt(np.mean(np.minimum(error, .5)**2)))
    ranked = sorted(scores, key=scores.get)
    best, second = ranked[:2]
    margin = scores[second]-scores[best]
    valid = scores[best] < .16 and margin > max(.002, scores[best]*.10)
    return dict(page=best if valid else 'unknown', best=best, scores=scores, margin=margin,
                valid=bool(valid), method='four-fold-affine-colour-pattern',
                nominal_values_are_not_colour_reference=True)


def identify_header(rgb, H, directory):
    """Read the actual T/V page label independently of the colour transform."""
    templates = sorted(directory.glob('*.png'))
    if len(templates) != 8:
        return dict(valid=False, reason='missing-local-header-templates')
    yy, xx = np.mgrid[-.050:.002:64j, -.006:.060:112j]
    pts = project(H, np.stack([xx, yy], -1))*rgb.shape[1::-1]-.5
    visible = (pts[..., 0] >= 0) & (pts[..., 1] >= 0) & (pts[..., 0] < rgb.shape[1]-1) & (pts[..., 1] < rgb.shape[0]-1)
    if np.mean(visible) < .2:
        return dict(valid=False, reason='header-outside-frame')
    gray = rgb.mean(2)
    strip = ndimage.map_coordinates(gray, [pts[..., 1], pts[..., 0]], order=1, mode='nearest')
    # The strip has approximately 1.05x horizontal and 1.23x vertical pixels
    # per CSS pixel at the fixture viewport. Search scale and optical blur.
    scores, locations = {}, {}
    for path in templates:
        original = Image.open(path).convert('L')
        best, where = -1., None
        for scale in (.60, .75, .9, 1.05, 1.25, 1.50, 1.8):
            size = (max(8, round(original.width*scale*1.05)), max(8, round(original.height*scale*1.23)))
            for blur in (0., .65, 1.1):
                t = np.asarray(original.resize(size, Image.Resampling.BICUBIC), float)
                if blur:
                    t = ndimage.gaussian_filter(t, blur)
                t -= t.mean()
                norm = np.linalg.norm(t)
                if norm < 1:
                    continue
                num = signal.correlate2d(strip, t, mode='valid')
                ones = np.ones(t.shape)
                total = signal.correlate2d(strip, ones, mode='valid')
                square = signal.correlate2d(strip*strip, ones, mode='valid')
                den = np.sqrt(np.maximum(square-total*total/t.size, 0))*norm
                corr = np.divide(num, den, out=np.zeros_like(num), where=den > 1e-6)
                visibility = signal.correlate2d(visible.astype(float), ones, mode='valid')
                corr[visibility < t.size*.98] = 0
                # Page labels start next to the first column. A good match far
                # to its right is a different word or a ramp marker.
                corr[:, 48:] = 0
                peak = np.unravel_index(np.argmax(corr), corr.shape)
                score = float(corr[peak])
                if score > best:
                    best, where = score, dict(x=int(peak[1]), y=int(peak[0]), scale=scale, blur=blur)
        scores[path.stem], locations[path.stem] = best, where
    ranked = sorted(scores, key=scores.get, reverse=True)
    best, second = ranked[:2]
    margin = scores[best]-scores[second]
    return dict(valid=bool(scores[best] > .58 and margin > .025), page=best,
                scores=scores, margin=margin, location=locations[best], method='printed-T/V-and-digit-template')


def page_identity(rgb, H, pages, templates):
    colour = identify_page(quick_samples(rgb, H), pages)
    text = identify_header(rgb, H, templates)
    if text.get('valid') and colour['scores'][text['page']] < .16:
        conflict = colour['valid'] and colour['page'] != text['page']
        return dict(page='unknown' if conflict else text['page'], valid=not conflict,
                    colour=colour, text=text, conflict=bool(conflict), method='header-and-colour-pattern')
    if text.get('valid') and not colour['valid']:
        # A monochrome recipe destroys the colour-pattern page code. The
        # independently read printed label still identifies the page.
        return dict(page=text['page'], valid=True, colour=colour, text=text,
                    conflict=False, colour_confirmation=False,
                    method='printed-header-without-colour-confirmation')
    if text.get('scores') and min(colour['scores'].values()) < .16:
        best_error = min(colour['scores'].values())
        plausible = [k for k, v in colour['scores'].items() if v <= best_error+max(.012, best_error*.15)]
        ranked = sorted(plausible, key=lambda k:text['scores'][k], reverse=True)
        if len(ranked) >= 2:
            margin = text['scores'][ranked[0]]-text['scores'][ranked[1]]
            if text['scores'][ranked[0]] >= .65 and margin > .04:
                return dict(page=ranked[0], valid=True, colour=colour, text=text,
                    joint_margin=margin, method='colour-shortlist-plus-printed-header')
    return {**colour, 'text':text}
