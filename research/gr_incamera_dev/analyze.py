#!/usr/bin/env python3
"""Align returned JPEGs, measure centres, and derive Standard-relative transfers."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import io
import numpy as np
from PIL import Image, ImageCms, ImageOps
from scipy import ndimage
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull
from common import LOCAL, ROOT, colour, read, dump, output, require, sha, pin, load_module
from chart import marker_codes, RADII, gain_ev


def project(h, points):
    q = np.c_[np.asarray(points, float), np.ones(len(points))] @ np.asarray(h).T
    require(np.all(np.abs(q[:, 2]) > 1e-12), '退化的投影')
    return q[:, :2] / q[:, 2:]


def homography(source, target):
    def normalized(a):
        a = np.asarray(a, float)
        mean = a.mean(axis=0)
        s = np.sqrt(2.) / np.sqrt(np.mean(np.sum((a - mean) ** 2, axis=1)))
        h = np.array([[s, 0, -s * mean[0]], [0, s, -s * mean[1]], [0, 0, 1]])
        return project(h, a), h
    a, ha = normalized(source)
    b, hb = normalized(target)
    matrix = []
    for (x, y), (u, v) in zip(a, b):
        matrix += [[-x, -y, -1, 0, 0, 0, u * x, u * y, u],
                   [0, 0, 0, -x, -y, -1, v * x, v * y, v]]
    _, singular, vh = np.linalg.svd(matrix, full_matrices=True)
    require(singular[-2] > 1e-8, '定位点退化')
    h = np.linalg.inv(hb) @ vh[-1].reshape(3, 3) @ ha
    return h / h[2, 2]


def quadrilateral(points):
    hull = points[ConvexHull(points).vertices]
    while len(hull) > 4:
        left, right = np.roll(hull, 1, axis=0) - hull, np.roll(hull, -1, axis=0) - hull
        area = np.abs(left[:, 0] * right[:, 1] - left[:, 1] * right[:, 0])
        hull = np.delete(hull, int(np.argmin(area)), axis=0)
    order = np.argsort(np.arctan2(hull[:, 1] - hull[:, 1].mean(), hull[:, 0] - hull[:, 0].mean()))
    hull = hull[order]
    return np.roll(hull, -int(np.argmin(hull.sum(axis=1))), axis=0)


def align(image, card):
    scaled = image.copy()
    scaled.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    a = np.asarray(scaled, float) @ np.array([.2126, .7152, .0722])
    low, high = np.percentile(a, [1, 99])
    require(high - low >= 25, 'JPEG 定位标记对比不足')
    labels, _ = ndimage.label(a < low + .35 * (high - low))
    slices = ndimage.find_objects(labels)
    codes, found = marker_codes(), {}
    local = np.array([[0, 0], [9, 0], [9, 9], [0, 9]], float)
    gy, gx = np.mgrid[.5:9:1., .5:9:1.]
    grid = np.c_[gx.ravel(), gy.ravel()]
    for ident, sl in enumerate(slices, 1):
        if sl is None:
            continue
        hh, ww = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if not (.018 * a.shape[1] <= ww <= .065 * a.shape[1] and .65 <= hh / ww <= 1.5):
            continue
        yy, xx = np.nonzero(labels[sl] == ident)
        if not .18 < len(xx) / (hh * ww) < .60:
            continue
        pts = np.c_[xx + sl[1].start, yy + sl[0].start].astype(float)
        quad = quadrilateral(pts)
        transform = homography(local, quad)
        sampling = project(transform, grid)
        values = ndimage.map_coordinates(a, [sampling[:, 1], sampling[:, 0]], order=1).reshape(9, 9)
        mn, mx = np.percentile(values, [10, 90])
        if mx - mn < 25:
            continue
        observed = values[3:6, 3:6] > (mn + mx) / 2
        trials = sorted((int(np.count_nonzero(np.rot90(observed, k) != code)), i, k)
                        for i, code in enumerate(codes) for k in range(4))
        distance, i, rotation = trials[0]
        if distance > 1 or trials[1][0] - distance < 2:
            continue
        # Reject a patch that happens to contain a valid code without the ring.
        border = np.r_[values[0, :], values[-1, :], values[1:-1, 0], values[1:-1, -1]]
        moat = np.r_[values[1, 1:-1], values[-2, 1:-1], values[2:-2, 1], values[2:-2, -2]]
        if border.mean() >= moat.mean() - .25 * (mx - mn):
            continue
        require(i not in found, '发现重复的定位码；拒绝猜测配准')
        found[i] = np.roll(quad, -rotation, axis=0)
    require(set(found) == {0, 1, 2, 3}, f'定位标记不全: {sorted(found)}')
    scale = np.array(image.size) / np.array(scaled.size)
    source = np.concatenate([np.asarray(m['corners'], float) for m in card['markers']])
    target = np.concatenate([found[m['id']] * scale + .5 * (scale - 1) for m in card['markers']])
    h = homography(source, target)
    error = np.linalg.norm(project(h, source) - target, axis=1)
    require(float(error.max()) <= 9 * max(scale) / 3, f'定位残差过大: {error.max():.2f}px')
    return h, dict(marker_ids=sorted(found), rms_pixel=float(np.sqrt(np.mean(error ** 2))),
                   max_pixel=float(error.max()), image_wh=list(image.size), homography=h)


def load_jpeg(path):
    with Image.open(path) as original:
        require(original.format == 'JPEG', '必须是原始 JPEG 文件')
        original.load()
        exif = original.getexif()
        profile = original.info.get('icc_profile')
        image = ImageOps.exif_transpose(original).convert('RGB')
        if profile:
            image = ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                                              ImageCms.createProfile('sRGB'), outputMode='RGB')
        else:
            cs = exif.get_ifd(34665).get(40961) if 34665 in exif else exif.get(40961)
            require(cs in (None, 1), 'JPEG 不是带已知色彩描述的 sRGB')
    return image


def sample(image, card, h):
    a = np.asarray(image, float) / 255
    result = []
    for p in card['patches']:
        x1, y1, x2, y2 = p['roi']
        yy, xx = np.mgrid[y1 + .5:y2:1., x1 + .5:x2:1.]
        xy = project(h, np.c_[xx.ravel(), yy.ravel()])
        require(xy[:, 0].min() >= 1 and xy[:, 1].min() >= 1 and xy[:, 0].max() < image.width - 1
                and xy[:, 1].max() < image.height - 1, '中心取样区越过 JPEG 边界')
        corners = project(h, [[x1, y1], [x2, y1], [x2, y2], [x1, y2]])
        require(np.linalg.norm(corners[0] - corners[1]) >= 12
                and np.linalg.norm(corners[0] - corners[3]) >= 12, 'JPEG 分辨率不足，取样区小于 12 像素')
        values = np.stack([ndimage.map_coordinates(a[..., c], [xy[:, 1], xy[:, 0]], order=1) for c in range(3)], axis=-1)
        result.append(dict(id=p['id'], rgb_observed=values.mean(axis=0), std=values.std(axis=0),
                           spatially_flat=bool(values.std(axis=0).max() < .025),
                           clipped_fraction=np.mean((values <= 1 / 255) | (values >= 254 / 255), axis=0)))
    return result


def pava(values):
    means, weights, starts = [], [], []
    for i, value in enumerate(values):
        means.append(float(value)); weights.append(1); starts.append(i)
        while len(means) > 1 and means[-2] > means[-1]:
            w = weights[-2] + weights[-1]
            means[-2] = (means[-2] * weights[-2] + means[-1] * weights[-1]) / w
            weights[-2] = w
            means.pop(); weights.pop(); starts.pop()
    return np.concatenate([np.repeat(m, w) for m, w in zip(means, weights)])


class NeutralLUT:
    def __init__(self, patches, measurements):
        refs = sorted([(p['level'], m['rgb_observed']) for p, m in zip(patches, measurements)
                       if p['role'] == 'reference'], key=lambda x: x[0])
        self.x = np.log2(np.array([v[0] for v in refs]))
        self.y = np.stack([pava(np.array([v[1][c] for v in refs])) for c in range(3)], axis=-1)
        self.inv = []
        for c in range(3):
            y = self.y[:, c]
            # Flat or clipped response cannot be inverted; keep its entire extent marked unsupported.
            good = (y > 2 / 255) & (y < 253 / 255)
            uy = np.unique(np.round(y[good], 7))
            ux = np.array([np.mean(self.x[good][np.isclose(y[good], v, atol=1e-7)]) for v in uy])
            require(len(uy) >= 8, '中性参考没有足够可逆阶调')
            self.inv.append((uy, ux))

    def inverse(self, rgb):
        rgb = np.asarray(rgb, float)
        v = np.array([np.interp(rgb[c], self.inv[c][0], self.inv[c][1]) for c in range(3)])
        good = np.array([self.inv[c][0][0] < rgb[c] < self.inv[c][0][-1] for c in range(3)])
        return v, good

    def forward(self, log_u):
        return np.array([np.interp(log_u[c], self.x, self.y[:, c]) for c in range(3)])


def radial_fit(card, measurements, lut):
    design, observations, radii = [], [], []
    for p, m in zip(card['patches'], measurements):
        if p['role'] != 'radial' or not m['spatially_flat']:
            continue
        log_u, good = lut.inverse(m['rgb_observed'])
        # The same scalar signal gain must explain each nonclipped output channel.
        for c in range(3):
            if not good[c]:
                continue
            design.append([np.interp(p['radius'], RADII, np.eye(5)[k]) for k in range(1, 5)])
            observations.append(log_u[c] - np.log2(p['level']))
            radii.append(p['radius'])
    require(len(observations) >= 60 and max(radii) >= .8, '径向灰块不足或半径覆盖不足')
    a, b = np.asarray(design), np.asarray(observations)
    fit = least_squares(lambda v: a @ v - b, [.23, .48, .75, 1.13], bounds=(-.3, 2.5),
                        loss='soft_l1', f_scale=.03, max_nfev=100)
    residual = a @ fit.x - b
    inlier = np.abs(residual) < .12
    rmse = float(np.sqrt(np.mean(residual[inlier] ** 2))) if inlier.any() else 1.
    passed = bool(fit.success and inlier.mean() >= .8 and rmse < .06)
    return dict(radius=RADII, gain_ev=np.r_[0, fit.x], samples=len(b), inlier_fraction=float(inlier.mean()),
                rmse_ev=rmse, passed=passed, max_observed_radius=float(max(radii)),
                centre_assumption='r<=reference_max_radius uses the supplied prior; absolute exposure remains unknown',
                colour_correction_assumption='homogeneous linear colour stage followed by separable per-channel neutral LUT',
                spectral_or_local_tone_correction_proven=False)


def correct(card, measurements):
    lut = NeutralLUT(card['patches'], measurements)
    fit = radial_fit(card, measurements, lut)
    for p, m in zip(card['patches'], measurements):
        log_u, good = lut.inverse(m['rgb_observed'])
        actual = np.interp(p['radius'], fit['radius'], fit['gain_ev'])
        residual = actual - (gain_ev(p['radius']) if p['precompensated'] else 0)
        shifted = log_u - residual
        supported = bool(fit['passed'] and m['spatially_flat'] and good.all()
                         and np.all(shifted > lut.x[0]) and np.all(shifted < lut.x[-1]))
        m.update(rgb_center=lut.forward(shifted) if supported else None, radial_shift_ev=float(residual),
                 radial_supported=supported)
    fit['reference_log2_u'] = lut.x
    fit['reference_rgb_monotone'] = lut.y
    by_id = {m['id']: m for m in measurements}
    errors = []
    cm = colour()
    for p, m in zip(card['patches'], measurements):
        if p['role'] == 'validation':
            parent = by_id[p['parent_id']]
            if m['radial_supported'] and parent['radial_supported']:
                errors.append(float(cm.delta_e00(cm.rgb_lab(m['rgb_center']), cm.rgb_lab(parent['rgb_center']))))
    passed = len(errors) >= 4 and np.median(errors) < 1.5 and np.percentile(errors, 90) < 3.
    fit['colour_holdout'] = dict(n=len(errors), delta_e00=errors, passed=bool(passed),
                                 scope='same camera RGB at centre and radii near 0.55 and 0.80')
    if card['kind'] == 'colour' and not passed:
        for p, m in zip(card['patches'], measurements):
            if p['role'] in ('colour', 'natural'):
                m['radial_supported'], m['rgb_center'] = False, None
    return fit


def metadata(path, mode, source):
    if source == 'model_prediction':
        return dict(source=source, camera_evidence=False, style_metadata_verified=False)
    tm = load_module('gr_card_tm', ROOT / 'research/contrib_gr_analysis/tiff_makernote.py')
    tiff, _ = tm.jpeg_exif_tiff(Path(path).read_bytes())
    _, at, note, root, _ = tm.maker_note_bytes(tiff)
    require(at is not None and note.startswith(b'RICOH\0'), '相机原图缺少 RICOH MakerNote')
    maker_entries, decoded = tm.decode_gr3_family(tiff, at)
    wb = next((e['value'] for e in maker_entries if e['tag'] == 0x0201), None)
    tone = decoded['image_tone']['value']
    require(tone == {'standard': 256, 'positive': 262, 'negative': 267, 'hc_bw': 261}[mode],
            f'JPEG 实际风格与 {mode} 标签不符')
    return dict(source=source, camera_evidence=True, style_metadata_verified=True,
                image_tone=tone, raw_development_process=decoded['raw_development_process_0x0062'],
                control=decoded['image_control_0x0247'], white_balance=decoded['white_balance_0x0019'],
                wb_rggb=wb,
                model=next(r['value'] for r in root if r['tag'] == 272))


def relative_row(standard, styled, cm):
    a, b = cm.rgb_lab(np.asarray(standard)), cm.rgb_lab(np.asarray(styled))
    ca, cb = np.hypot(a[1], a[2]), np.hypot(b[1], b[2])
    dh = (np.degrees(np.arctan2(b[2], b[1]) - np.arctan2(a[2], a[1])) + 180) % 360 - 180
    return dict(standard_lab=a, styled_lab=b, delta_lab=b - a,
                chroma_ratio=float(cb / ca) if ca >= 8 else None,
                delta_hue_deg=float(dh) if min(ca, cb) >= 8 else None)


def analyze(manifest, styles, destination, source='camera'):
    require('standard' in styles and len(styles) >= 2, '至少需要 Standard 和一种风格')
    require(set(styles) <= {'standard', 'positive', 'negative', 'hc_bw'}, '未知风格名')
    card = read(manifest)
    require(sha(card['dng_path']) == card['dng_sha256'], '分析前 DNG 哈希不符')
    cm = colour()
    modes = {}
    for mode, path in styles.items():
        path = Path(path).resolve()
        if not path.is_relative_to(LOCAL):
            pin(path)
        md = metadata(path, mode, source)
        if source == 'camera':
            require(md['model'].strip() == card['geometry']['model'].strip(), '回传 JPG 机型与 DNG 容器不符')
            if modes:
                previous = next(iter(modes.values()))['metadata']
                require(md['wb_rggb'] == previous['wb_rggb'] and md['white_balance'] == previous['white_balance'],
                        '各风格白平衡不一致，不能作为同输入的相对变换')
        image = load_jpeg(path)
        h, alignment = align(image, card)
        samples = sample(image, card, h)
        fit = correct(card, samples)
        modes[mode] = dict(path=str(path), sha256=sha(path), metadata=md, alignment=alignment,
                           radial=fit, patches=samples)
    transforms = {}
    for mode, state in modes.items():
        if mode == 'standard':
            continue
        rows = []
        for p, a, b in zip(card['patches'], modes['standard']['patches'], state['patches']):
            row = dict(id=p['id'], role=p['role'], raw=p['raw'], radius=p['radius'],
                       observed=relative_row(a['rgb_observed'], b['rgb_observed'], cm))
            supported = a['radial_supported'] and b['radial_supported']
            row['normalized'] = relative_row(a['rgb_center'], b['rgb_center'], cm) if supported else None
            row['usable_for_fit'] = bool(supported and p['role'] in ('tone', 'colour', 'natural'))
            rows.append(row)
        transforms[mode] = rows
    result = dict(schema='gr-relative-targets/1', card_manifest=str(Path(manifest).resolve()),
                  dng_sha256=card['dng_sha256'], source=source,
                  camera_jpg_observed=source == 'camera', camera_acceptance=False, metering_anchor_determined=False,
                  relative_definition='paired same-DNG same-position style minus Standard; paired observations retained',
                  correction_scope='RAW prior precompensation plus measured neutral-LUT residual; colour separability remains an assumption',
                  lab_white='D50', modes=modes, transforms=transforms,
                  firmware_ready=False, deployable=False)
    dump(destination, result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('--style', action='append', required=True, help='standard=/absolute/file.JPG; repeat per style')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--source', choices=['camera', 'model_prediction'], default='camera')
    a = p.parse_args()
    pairs = [s.split('=', 1) for s in a.style]
    require(all(len(q) == 2 for q in pairs) and len({q[0] for q in pairs}) == len(pairs), '风格参数重复或无效')
    r = analyze(a.manifest, dict(pairs), a.out, a.source)
    print({k: sum(p['usable_for_fit'] for p in v) for k, v in r['transforms'].items()})
