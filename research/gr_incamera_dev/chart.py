"""Two CFA cards with large interiors, neutral references, and coded fiducials."""
import numpy as np
from common import colour, require, sha

RADII = np.array([0., .5, .7, .85, 1.])
GAIN_EV = np.array([0., .23, .48, .75, 1.13])
PITCH = 104
SIDE = 88
ROI = 32
# ITU-R BT.2020 primaries, D65. Its positive cone is inside the spectral locus;
# it is wider than sRGB but is still not a measured GR sensor-response cone.
REC2020_XYZ = np.array([[.6369580483, .1446169036, .1688809752],
                        [.2627002120, .6779980715, .0593017165],
                        [0., .0280726930, 1.0609850577]])


def radial(x, y, wh):
    w, h = wh
    return np.hypot(np.asarray(x) - w / 2, np.asarray(y) - h / 2) / np.hypot(w / 2, h / 2)


def gain_ev(r):
    return np.interp(r, RADII, GAIN_EV)


def marker_codes():
    chosen = []
    for word in range(512):
        a = np.array([(word >> i) & 1 for i in range(9)]).reshape(3, 3)
        if not 3 <= a.sum() <= 6:
            continue
        rotations = [np.rot90(a, i) for i in range(4)]
        if min(np.count_nonzero(a != b) for b in rotations[1:]) < 4:
            continue
        if any(min(np.count_nonzero(a != np.rot90(b, i)) for i in range(4)) < 3 for b in chosen):
            continue
        chosen.append(a)
        if len(chosen) == 4:
            return chosen
    raise ValueError('找不到互异的定位码')


def marker_pattern(index):
    a = np.ones((9, 9), float)
    a[0, :] = a[-1, :] = a[:, 0] = a[:, -1] = 0
    a[3:6, 3:6] = marker_codes()[index]
    return a


def design(tiff, kind):
    require(kind in ('tone', 'colour'), '未知测试卡')
    cm = colour()
    g = tiff.geometry()
    require(g['orientation'] == 1, '请使用未旋转的横幅 DNG，Orientation 必须为 1')
    matrix, matrix_info = cm.dng_camera_to_xyz(tiff.tags())
    inv = np.linalg.inv(matrix)
    neutral = np.asarray(g['neutral'], float)
    w, h = g['crop_wh']
    require(w >= 4000 and h >= 3000, '裁切尺寸太小')
    unit = 20
    markers = []
    for i, (fx, fy) in enumerate(((.08, .08), (.92, .08), (.92, .92), (.08, .92))):
        x, y = int(round((w * fx - 110) / 2)) * 2, int(round((h * fy - 110) / 2)) * 2
        # The detected black square is inside a one-cell external white moat.
        markers.append(dict(id=i, unit=unit, xy=[x, y],
                            corners=[[x + 20, y + 20], [x + 200, y + 20],
                                     [x + 200, y + 200], [x + 20, y + 200]]))
    cells = []
    nx, ny = w // PITCH, h // PITCH
    start_x, start_y = (w - nx * PITCH) // 4 * 2, (h - ny * PITCH) // 4 * 2
    for iy in range(ny):
        for ix in range(nx):
            x, y = start_x + ix * PITCH + PITCH // 2, start_y + iy * PITCH + PITCH // 2
            if any(abs(x - (m['xy'][0] + 110)) < 170 and abs(y - (m['xy'][1] + 110)) < 170 for m in markers):
                continue
            cells.append(dict(cx=x, cy=y, r=float(radial(x, y, (w, h)))))
    patches = []

    def allocate(item, cell, compensate=True):
        x, y = cell['cx'], cell['cy']
        patches.append({**item, 'center': [x, y], 'radius': cell['r'],
                        'box': [x - SIDE // 2, y - SIDE // 2, x + SIDE // 2, y + SIDE // 2],
                        'roi': [x - ROI // 2, y - ROI // 2, x + ROI // 2, y + ROI // 2],
                        'precompensated': compensate})
        cells.remove(cell)

    # References are held out from the outer radial fit and span its invertible range.
    levels = np.unique(np.r_[np.geomspace(.0003, .03, 37), np.linspace(.03, .99, 60)])
    center = sorted(cells, key=lambda c: (c['r'], c['cy'], c['cx']))[:len(levels)]
    order = np.random.default_rng(62021).permutation(len(levels))
    for i, j in enumerate(order):
        u = float(levels[j])
        allocate(dict(id=f'ref-{j:03d}', role='reference', level=u, raw=neutral * u), center[i])
    center_max = max(p['radius'] for p in patches)
    probe_levels = np.geomspace(.001, .42, 16)
    for k, r in enumerate((.35, .5, .7, .85, .93)):
        chosen = sorted(cells, key=lambda c: (abs(c['r'] - r), c['cy'], c['cx']))[:32]
        chosen.sort(key=lambda c: np.arctan2(c['cy'] - h / 2, c['cx'] - w / 2))
        for j, c in enumerate(chosen):
            u = float(probe_levels[(j * 7) % 16])
            allocate(dict(id=f'rad-{k}-{j:02d}', role='radial', level=u, raw=neutral * u), c, False)
    candidates, rejects = [], []
    boundary_checks = dict(tested=0, outside_rec2020=0, negative_camera=0, above_camera_headroom=0)
    if kind == 'tone':
        denom = g['white'] - max(g['black'])
        values = np.unique(np.r_[0., 1 / denom, np.geomspace(2 / denom, .08, 129),
                                 np.linspace(0., 1., 257), .9999])
        for i, u in enumerate(values):
            candidates.append(dict(id=f'tone-{i:03d}', role='tone', level=float(u), raw=neutral * u))
    else:
        # D65 Lab definitions for useful scene families, not measured skin/leaf spectra.
        naturals = [('skin-dark', 30, 16, 16), ('skin-mid', 52, 22, 24), ('skin-light', 76, 15, 18),
                    ('skin-rosy', 65, 25, 12), ('skin-warm', 62, 20, 30), ('skin-shadow', 24, 10, 8),
                    ('leaf-dark', 25, -18, 15), ('leaf-mid', 42, -30, 28), ('leaf-light', 68, -25, 38),
                    ('leaf-olive', 48, -8, 30), ('sky-deep', 35, 5, -34), ('sky-mid', 57, -5, -30),
                    ('sky-light', 78, -8, -15), ('cloud-warm', 82, 2, 8), ('earth', 38, 16, 22),
                    ('flower-red', 44, 45, 27), ('flower-purple', 45, 32, -30), ('flower-magenta', 55, 45, -20)]

        def convert(lab):
            xyz65 = cm.lab_xyz(np.array(lab), cm.D65)
            xyz50 = cm.cat(cm.D65, cm.D50) @ xyz65
            linear = np.linalg.solve(cm.SRGB_XYZ, xyz65)
            wide = np.linalg.solve(REC2020_XYZ, xyz65)
            raw = inv @ xyz50
            boundary_checks['tested'] += 1
            boundary_checks['outside_rec2020'] += int(np.any(wide < -1e-10) or np.any(wide > 1 + 1e-10))
            boundary_checks['negative_camera'] += int(np.any(raw < 0))
            boundary_checks['above_camera_headroom'] += int(np.any(raw > .96))
            valid = bool(np.all(wide >= -1e-10) and np.all(wide <= 1 + 1e-10)
                         and np.all(raw >= 0) and np.all(raw <= .96))
            return raw, linear, xyz50, valid

        for label, L, a, b in naturals:
            raw, linear, xyz50, ok = convert([L, a, b])
            item = dict(id=label, role='natural', lab_d65=[L, a, b], raw=raw,
                        linear_srgb=linear, xyz_d50=xyz50)
            (candidates if ok else rejects).append(item)
        hues = sorted(set(np.arange(0., 360., 15.).tolist() +
                          [7.5, 22.5, 337.5, 352.5, 232.5, 247.5, 262.5, 277.5, 292.5, 307.5, 322.5]))
        for hue in hues:
            angle = np.radians(hue)
            for L in (15., 30., 45., 60., 78.):
                low, high = 0., 180.
                for _ in range(32):
                    C = (low + high) / 2
                    if convert([L, C * np.cos(angle), C * np.sin(angle)])[3]:
                        low = C
                    else:
                        high = C
                for j, fraction in enumerate((.2, .45, .7, .95)):
                    C = low * fraction
                    lab = [L, C * np.cos(angle), C * np.sin(angle)]
                    raw, linear, xyz50, ok = convert(lab)
                    item = dict(id=f'h{hue:05.1f}-L{L:02.0f}-s{j}', role='colour', hue=hue,
                                L=L, saturation_fraction=fraction, chroma_limit=low,
                                lab_d65=lab, linear_srgb=linear, xyz_d50=xyz50, raw=raw)
                    (candidates if ok else rejects).append(item)
        candidates.sort(key=lambda p: (p['role'] != 'natural',
                                      not (p.get('hue', 180) <= 30 or p.get('hue', 180) >= 230), p['id']))
    available = sorted((c for c in cells if c['r'] <= .65), key=lambda c: (c['r'], c['cy'], c['cx']))
    require(len(candidates) <= len(available), '中心区域容纳不了色块')
    if kind == 'tone':
        candidates = [candidates[i] for i in np.random.default_rng(62022).permutation(len(candidates))]
    for item, cell in zip(candidates, available):
        allocate(item, cell)
    if kind == 'colour':
        # These are not training samples. Their identical camera RGB tests whether
        # neutral-derived residual compensation also holds for colour and local tone.
        for label in ('skin-mid', 'leaf-mid', 'sky-mid', 'flower-red', 'flower-purple', 'flower-magenta'):
            parent = next(p for p in patches if p['id'] == label)
            for ri, radius in enumerate((.55, .80)):
                cell = min(cells, key=lambda c: (abs(c['r'] - radius), c['cy'], c['cx']))
                allocate(dict(id=f'holdout-{label}-{ri}', role='validation', parent_id=label,
                              raw=parent['raw']), cell)
    return dict(schema='gr-incamera-card/1', kind=kind, geometry=g,
                radial_definition='Euclidean distance from crop centre / half crop diagonal',
                prior_radius=RADII, prior_gain_ev=GAIN_EV, compensation='per 2x2 CFA quad, signal only',
                pitch=PITCH, patch_side=SIDE, roi_side=ROI, reference_max_radius=center_max,
                markers=markers, patches=patches, rejected=rejects, boundary_checks=boundary_checks, colour_matrix=matrix,
                matrix_info=matrix_info, support='linear Rec.2020 D65 positive cone and nonnegative unclipped camera RGB; not spectral characterization',
                reference_grade='synthetic_input', camera_acceptance=False)


def raw_mosaic(card):
    g = card['geometry']
    w, h = g['width'], g['height']
    black = np.array(g['black'], float).reshape(2, 2)
    raw = np.tile(black.astype(np.uint16), (h // 2, w // 2))
    x0, y0 = g['crop_xy']
    cw, ch = g['crop_wh']
    yy, xx = np.mgrid[0:ch:2, 0:cw:2]
    compensation = 2. ** -gain_ev(radial(xx + 1, yy + 1, (cw, ch)))
    neutral = np.asarray(g['neutral'], float)
    crop = raw[y0:y0 + ch, x0:x0 + cw]
    for iy, ix, c in ((0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 2)):
        b = black[iy, ix]
        crop[iy::2, ix::2] = np.rint(b + (g['white'] - b) * .025 * neutral[c] * compensation)
    def fill(box, rgb, compensate):
        x1, y1, x2, y2 = map(int, box)
        require(all(n % 2 == 0 for n in (x1, y1, x2, y2)), 'CFA 色块边界不为偶数')
        factor = compensation[y1 // 2:y2 // 2, x1 // 2:x2 // 2] if compensate else 1.
        for iy, ix, c in ((0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 2)):
            b = black[iy, ix]
            vals = np.rint(b + (g['white'] - b) * rgb[c] * factor)
            require(np.all(vals >= b) and np.all(vals <= g['white']), 'RAW 色块超黑白电平')
            crop[y1 + iy:y2:2, x1 + ix:x2:2] = vals
    for p in card['patches']:
        fill(p['box'], p['raw'], p['precompensated'])
    for m in card['markers']:
        x, y = m['xy']
        u = m['unit']
        fill([x, y, x + 11 * u, y + 11 * u], neutral * .65, True)
        for iy, row in enumerate(marker_pattern(m['id'])):
            for ix, v in enumerate(row):
                xa, ya = x + (ix + 1) * u, y + (iy + 1) * u
                fill([xa, ya, xa + u, ya + u], neutral * (.65 if v else 0.), True)
    return raw


def camera_half(mosaic, card):
    g = card['geometry']
    x, y = g['crop_xy']
    w, h = g['crop_wh']
    crop = mosaic[y:y + h, x:x + w].astype(np.float32)
    b = np.array(g['black'], float)
    planes = [(crop[iy::2, ix::2] - b[k]) / (g['white'] - b[k])
              for k, (iy, ix) in enumerate(((0, 0), (0, 1), (1, 0), (1, 1)))]
    return np.stack([planes[0], (planes[1] + planes[2]) * .5, planes[3]], axis=-1)


def preview_half(mosaic, card):
    cm = colour()
    rgb = camera_half(mosaic, card)
    # A generic DNG colourimetric preview; no claim that it is a GR style render.
    w, h = card['geometry']['crop_wh']
    yy, xx = np.mgrid[0:h:2, 0:w:2]
    rgb *= (2. ** gain_ev(radial(xx + 1, yy + 1, (w, h))))[..., None]
    xyz50 = rgb @ np.asarray(card['colour_matrix']).T
    linear = xyz50 @ cm.cat(cm.D50, cm.D65).T @ np.linalg.inv(cm.SRGB_XYZ).T
    return np.clip(cm.srgb_encode(np.maximum(linear, 0)), 0, 1)
