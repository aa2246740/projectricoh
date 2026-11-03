#!/usr/bin/env python3
"""Dense camera-response and model-output sampling; all point records stay local."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dense
common = dense.legacy()
import itertools
import numpy as np
import chart
from predict import Renderer

HUES = tuple(range(0, 360, 3))
LIGHTNESS = (12, 24, 36, 48, 60, 72, 84, 94)
FRACTIONS = (.08, .25, .50, .75, .90, .98)
CAMERA_LEVELS = (.0005, .0015, .004, .01, .025, .05, .1, .18, .3, .45, .65, .82, .98)
OUTPUT_LEVELS = (.01, .05, .12, .25, .4, .55, .7, .85, .98)
LOW, HIGH = .0005, .98
PITCH, SIDE, ROI = 96, 80, 32


def points(tiff):
    cm = common.colour()
    g = tiff.geometry()
    matrix, info = cm.dng_camera_to_xyz(tiff.tags())
    renderer = Renderer()
    state = renderer.record['results']['standard']
    forward = np.asarray(state['ColorMatrix_Calc_front_signed12_Q8_hypothesis'], float) / 256
    curve = np.asarray(state['effective_curve256_u16LE']['values'], float)
    dense.require((np.diff(curve) >= 0).all(), 'Standard curve is not monotone')
    unique, indices = np.unique(curve, return_index=True)
    inverse_forward = np.linalg.inv(forward)
    def standard_inverse(target):
        code = np.interp(np.asarray(target) * 16384, unique, indices * 16 / 4095)
        return inverse_forward @ (code / renderer.record['parameters']['exposure_scale']) * g['neutral']
    result = []
    def colour_point(raw, **fields):
        raw = np.asarray(raw, float)
        xyz50 = matrix @ raw
        xyz65 = cm.cat(cm.D50, cm.D65) @ xyz50
        lab = cm.xyz_lab(xyz65, cm.D65)
        chroma = float(np.hypot(lab[1], lab[2]))
        return dict(role='colour', raw=raw, lab_d65=lab, xyz_d50=xyz50,
                    linear_srgb=np.linalg.solve(cm.SRGB_XYZ, xyz65),
                    nominal_chroma=chroma,
                    nominal_hue=float(np.degrees(np.arctan2(lab[2], lab[1])) % 360), **fields)
    for li, L in enumerate(LIGHTNESS):
        for hue in HUES:
            angle = np.radians(hue)
            def convert(chroma):
                lab = [L, chroma * np.cos(angle), chroma * np.sin(angle)]
                rgb = cm.lab_rgb(lab, cm.D65)
                return standard_inverse(rgb), rgb
            def inside(converted):
                raw, rgb = converted
                return bool(np.isfinite(raw).all() and (raw >= LOW).all() and (raw <= HIGH).all()
                            and (rgb >= .002).all() and (rgb <= .998).all())
            dense.require(inside(convert(0)), f'neutral L={L} outside model/output domain')
            lo, hi = 0., 512.
            dense.require(not inside(convert(hi)), 'chroma search bracket too short')
            for _ in range(48):
                mid = (lo + hi) / 2
                if inside(convert(mid)):
                    lo = mid
                else:
                    hi = mid
            for ci, fraction in enumerate(FRACTIONS):
                raw, rgb = convert(lo * fraction)
                dense.require(inside((raw, rgb)), 'accepted LCh point outside camera/output domain')
                dense.require(np.max(np.abs(renderer.render(raw, g['neutral'], 'standard') - rgb)) < 1e-7,
                              'LCh Standard inverse does not round-trip')
                result.append(colour_point(raw, id=f'h{hue:03d}-L{L:02d}-c{ci}', family='lch',
                    hue=hue, L=L, chroma_limit=lo, saturation_fraction=fraction,
                    target_standard_rgb=rgb, designed_standard_chroma=lo*fraction,
                    band=li // 2))
    for i, raw in enumerate(itertools.product(CAMERA_LEVELS, repeat=3)):
        result.append(colour_point(raw, id=f'camera-{i:04d}', family='camera-cube', band=i % 4))
    accepted, rejected = 0, 0
    for i, target in enumerate(itertools.product(OUTPUT_LEVELS, repeat=3)):
        raw = standard_inverse(target)
        if (raw < LOW).any() or (raw > HIGH).any():
            rejected += 1
            continue
        error = float(np.max(np.abs(renderer.render(raw, g['neutral'], 'standard') - target)))
        dense.require(error < 1e-7, 'Standard inverse does not round-trip')
        result.append(colour_point(raw, id=f'output-{i:04d}', family='standard-output',
                                    target_standard_rgb=target, band=i % 4))
        accepted += 1
    return result, matrix, info, dict(attempted=len(OUTPUT_LEVELS) ** 3,
        accepted=accepted, rejected_outside_unclipped_camera_domain=rejected)


def design(tiff, band, acceptance=False):
    g = tiff.geometry()
    pitch, side, roi = (300, 240, 64) if acceptance else (PITCH, SIDE, ROI)
    dense.require(g['orientation'] == 1 and min(g['crop_wh']) >= 3000, 'unsupported crop/orientation')
    all_points, matrix, info, inverse = points(tiff)
    if acceptance:
        selected = [p for p in all_points if p['family'] == 'lch' and p['L'] == 48
                    and p['hue'] % 60 == 0 and p['saturation_fraction'] in (.25, .75, .98)]
        extremes = [p for p in all_points if p['family'] == 'camera-cube'
                    and set(p['raw']) == {LOW, HIGH} and sum(p['raw'] == HIGH) == 1]
        selected += extremes
    else:
        selected = [p for p in all_points if p['band'] == band]
    selected = [dict(p) for p in selected]
    w, h = g['crop_wh']
    markers = []
    for i, (fx, fy) in enumerate(((.08, .08), (.92, .08), (.92, .92), (.08, .92))):
        x, y = int(round((w * fx - 110) / 2)) * 2, int(round((h * fy - 110) / 2)) * 2
        markers.append(dict(id=i, unit=20, xy=[x, y], corners=[
            [x + 20, y + 20], [x + 200, y + 20], [x + 200, y + 200], [x + 20, y + 200]]))
    nx, ny = w // pitch, h // pitch
    sx, sy = (w - nx * pitch) // 4 * 2, (h - ny * pitch) // 4 * 2
    cells = []
    for iy in range(ny):
        for ix in range(nx):
            x, y = sx + ix * pitch + pitch // 2, sy + iy * pitch + pitch // 2
            margin = 110 + side // 2 + 8
            if any(abs(x - m['xy'][0] - 110) < margin and abs(y - m['xy'][1] - 110) < margin for m in markers):
                continue
            cells.append(dict(cx=x, cy=y, r=float(chart.radial(x, y, (w, h)))))
    patches = []
    def allocate(item, cell, compensate=True):
        x, y = cell['cx'], cell['cy']
        patches.append(dict(item, center=[x, y], radius=cell['r'],
            box=[x-side//2, y-side//2, x+side//2, y+side//2],
            roi=[x-roi//2, y-roi//2, x+roi//2, y+roi//2], precompensated=compensate))
        cells.remove(cell)
    neutral = np.asarray(g['neutral'])
    ramp = np.geomspace(LOW, HIGH, 17)
    row = sorted(sorted(cells, key=lambda c: (-c['cy'], abs(c['cx'] - w/2)))[:17], key=lambda c: c['cx'])
    for j, (u, cell) in enumerate(zip(ramp, row)):
        allocate(dict(id=f'ramp-{j:02d}', role='tone', level=float(u), raw=neutral*u), cell)
    if not acceptance:
        levels = np.unique(np.r_[np.geomspace(.0003, .03, 37), np.linspace(.03, .98, 60)])
        chosen = sorted(cells, key=lambda c: (c['r'], c['cy'], c['cx']))[:len(levels)]
        order = np.random.default_rng(72022).permutation(len(levels))
        for j, cell in zip(order, chosen):
            u = float(levels[j])
            allocate(dict(id=f'ref-{j:03d}', role='reference', level=u, raw=neutral*u), cell)
        reference_max = max(p['radius'] for p in patches if p['role'] == 'reference')
        probe = np.geomspace(.001, .42, 16)
        for k, radius in enumerate((.35, .5, .7, .85, .93)):
            chosen = sorted(cells, key=lambda c: (abs(c['r']-radius), c['cy'], c['cx']))[:32]
            chosen.sort(key=lambda c: np.arctan2(c['cy'] - h/2, c['cx'] - w/2))
            for j, cell in enumerate(chosen):
                u = float(probe[j * 7 % 16])
                allocate(dict(id=f'rad-{k}-{j:02d}', role='radial', level=u, raw=neutral*u), cell, False)
        holds = []
        first_L = LIGHTNESS[band * 2]
        parents = [p for p in selected if p['family'] == 'lch' and p['L'] == first_L
                   and p['hue'] % 60 == 0 and p['saturation_fraction'] == .25]
        # Reserve spatial checks before filling the remaining frame.
        for parent in parents:
            for ri, radius in enumerate((.55, .80)):
                cell = min(cells, key=lambda c: (abs(c['r'] - radius), c['cy'], c['cx']))
                holds.append((dict(id=f'holdout-{parent["id"]}-{ri}', role='validation',
                                   parent_id=parent['id'], raw=parent['raw']), cell))
                cells.remove(cell)
        for item, cell in holds:
            cells.append(cell)
            allocate(item, cell)
    else:
        reference_max = None
    dense.require(len(selected) <= len(cells), f'patch capacity exceeded: {len(selected)} / {len(cells)}')
    # Fixed shuffle breaks hue/lightness-position correlation. Exact positions remain local.
    selected = [selected[i] for i in np.random.default_rng(82022 + band).permutation(len(selected))]
    chosen = sorted(cells, key=lambda c: (c['r'], c['cy'], c['cx']))[:len(selected)]
    for item, cell in zip(selected, chosen):
        allocate(item, cell)
    return dict(schema='gr-incamera-card/1', task='gr-dense-reference-r1', kind='colour',
        band=band, acceptance_microtest=acceptance, geometry=g, colour_matrix=matrix, matrix_info=info,
        pitch=pitch, patch_side=side, roi_side=roi, markers=markers, patches=patches,
        prior_radius=chart.RADII, prior_gain_ev=chart.GAIN_EV,
        reference_max_radius=reference_max, background_neutral_level=.15,
        raw_coordinate='black/white-normalized unbalanced camera RGB after nominal spatial gain; WB is separate',
        support='full positive camera response cube with 2 percent highlight headroom; no Rec.2020/display gate',
        lch_coordinate='predicted Standard JPEG CIELAB D65; inverse of frozen partial predictor, not camera truth',
        physical_spectral_gamut_proven=False, standard_inverse_lattice=inverse,
        reference_grade='synthetic_input', camera_acceptance=False)


def mosaic(card):
    w, h = card['geometry']['crop_wh']
    background = dict(box=[0, 0, w, h], raw=np.asarray(card['geometry']['neutral']) *
                      card['background_neutral_level'], precompensated=True)
    # Reuse every CFA, black-level, spatial-compensation, and fiducial operation.
    return chart.raw_mosaic(dict(card, patches=[background] + card['patches']))


if __name__ == '__main__':
    from tiff_io import Tiff
    for band in range(4):
        card = design(Tiff(common.GR3.read_bytes()), band)
        dense.dump(dense.LOCAL / 'designs' / f'band{band+1}.json', card)
        print(f'band {band+1}: {len(card["patches"])} patches')
