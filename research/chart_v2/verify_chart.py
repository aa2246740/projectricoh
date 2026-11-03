#!/usr/bin/env python3
"""Artifact self-check only. Not a parser for real photographs or DNG files."""
import collections
import contextlib
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageCms, ImageDraw
from scipy import ndimage

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


g = load('chart_v2_generator', HERE / 'make_chart.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(v):
    v = np.asarray(v, dtype=float)
    return np.where(v <= .04045, v / 12.92, ((v + .055) / 1.055) ** 2.4)


def encode(v):
    return np.where(v <= .0031308, v * 12.92, 1.055 * np.maximum(v, 0.) ** (1 / 2.4) - .055)


def gamut_and_layout(meta, profile):
    # Independent numeric matrix, not the generator's inverse/forward functions.
    matrix = np.array([[.4865709486482162, .2656676931690931, .1982172852343625],
                       [.2289745640697488, .6917385218365064, .0792869140937450],
                       [0., .0451133818589026, 1.0439443689009760]])
    white = np.array([.9504559270516716, 1., 1.0890577507598784])
    all_patches = meta['patches']
    chart = [p for p in all_patches if p['page'] > 0]
    assert len(chart) == 696 and len(all_patches) == 697
    grid = [p for p in chart if p['category'] == 'hue_grid']
    assert len(grid) == 576 and len({p['sample_key'] for p in grid}) == 576
    expect = {(h, L, c) for h in np.arange(3.75, 360., 7.5) for L in (18., 38., 58., 78.) for c in (.25, .60, .97)}
    actual = {(p['target_hue_deg'], p['target_lab_d65'][0], p['chroma_fraction_of_safe_max']) for p in grid}
    # atan2 may differ from the design hue by a few ulps.
    actual = {(round(h, 7), L, c) for h, L, c in actual}
    assert actual == expect
    gray = [p for p in chart if p['category'] == 'gray']
    assert len(gray) == 21 and len({tuple(p['p3_8bit']) for p in gray}) == 21
    assert collections.Counter(p['category'] for p in chart) == {'hue_grid': 576, 'gray': 21, 'skin': 12, 'memory': 15, 'anchor': 72}
    max_xyz_error, max_lab_error, max_linear_error = 0., 0., 0.
    for p in all_patches:
        code = np.array(p['p3_8bit'])
        assert code.min() >= 4 and code.max() <= 251
        lin = decode(code / 255.)
        xyz = matrix @ lin
        t = xyz / white
        d = 6. / 29.
        f = np.where(t > d ** 3, np.cbrt(t), t / (3. * d * d) + 4. / 29.)
        lab = np.array([116. * f[1] - 16., 500. * (f[0] - f[1]), 200. * (f[1] - f[2])])
        max_linear_error = max(max_linear_error, float(np.max(np.abs(lin - p['linear_p3']))))
        max_xyz_error = max(max_xyz_error, float(np.max(np.abs(xyz - p['xyz_d65_Y1']))))
        max_lab_error = max(max_lab_error, float(np.max(np.abs(lab - p['lab_d65']))))
    assert max(max_xyz_error, max_lab_error, max_linear_error) < 1e-7
    anchors = collections.defaultdict(list)
    for p in chart:
        if p['category'] == 'anchor':
            anchors[p['sample_key']].append(p)
    for key, ps in anchors.items():
        assert len(ps) == 6, key
        assert len({tuple(p['bbox_px']) for p in ps}) == 6, key
        assert len({tuple(p['p3_8bit']) for p in ps}) == 1, key
    for page in meta['pages']:
        im = Image.open(HERE / page['file'])
        assert im.size == (3456, 2234) and im.mode == 'RGB'
        assert im.info['icc_profile'] == profile
        arr = np.asarray(im)
        pats = [p for p in all_patches if p['page'] == page['page']]
        assert len(pats) == page['patch_count']
        for p in pats:
            x0, y0, x1, y1 = p['bbox_px']
            assert (arr[y0:y1, x0:x1] == p['p3_8bit']).all(), p['sample_key']
            if page['page']:
                assert x0 >= 184 and y0 >= 193 and x1 <= 3272 and y1 <= 2041
        extreme = np.any((arr == 0) | (arr == 255), axis=2)
        for m in page['markers']:
            x0, y0, x1, y1 = m['bbox_px']
            extreme[y0:y1, x0:x1] = False
        assert not extreme.any(), '0/255 outside corner markers'
    def counts(field):
        out = collections.Counter(p[field] for p in grid)
        assert set(out) == set(range(24)) and min(out.values()) >= 2
        return [out[i] for i in range(24)]
    qlab = collections.Counter(int(p['quantized_hue_deg'] // 15.) for p in grid)
    assert set(qlab) == set(range(24)) and min(qlab.values()) >= 2
    cstars = [math.hypot(p['lab_d65'][1], p['lab_d65'][2]) for p in grid]
    codes = np.array([p['p3_8bit'] for p in chart])
    return {'status': 'PASS', 'chart_patches': len(chart), 'grid_patches': len(grid),
            'gray_levels': len(gray), 'anchor_keys': len(anchors),
            'anchor_positions_distinct_per_key': 6, 'code_min_max': [int(codes.min()), int(codes.max())],
            'max_linear_metadata_error': max_linear_error, 'max_xyz_metadata_error': max_xyz_error,
            'max_lab_metadata_error': max_lab_error,
            'target_lab_sector_counts': counts('target_sector_15deg'),
            'quantized_lab_sector_counts': [qlab[i] for i in range(24)],
            'reference_srgb_bt601_sector_counts': counts('reference_srgb_bt601_sector_15deg'),
            'grid_chroma_min_max': [min(cstars), max(cstars)],
            'grid_chroma_above_31': sum(C > 31. for C in cstars),
            'grid_patches_outside_srgb': sum(p['outside_srgb'] for p in grid),
            'gray_target_L_min_max': [min(p['target_lab_d65'][0] for p in gray), max(p['target_lab_d65'][0] for p in gray)],
            'quantization_delta_e76_max': max(p['quantization_delta_e76'] for p in chart),
            'camera_actual_sector_coverage': 'UNKNOWN until real photographs are measured'}


def simulate(im, H, size):
    """Linear-light Gaussian defocus, then scaled projective resampling."""
    rgb = np.asarray(im)
    inv = np.linalg.inv(H)
    inv /= inv[2, 2]
    coeff = inv.ravel()[:8]
    result = np.empty((size[1], size[0], 3), np.float32)
    for ch in range(3):
        linear = decode(rgb[..., ch] / 255.).astype(np.float32)
        blurred = ndimage.gaussian_filter(linear, 6., mode='nearest', truncate=5.)
        warped = Image.fromarray(blurred).transform(size, Image.Transform.PERSPECTIVE,
                                                   coeff, Image.Resampling.BILINEAR, fillcolor=.01)
        result[..., ch] = encode(np.asarray(warped)) * 255.
    return result


def sample_cell(a, image, H, box):
    x0, y0, x1, y1 = box
    xs = np.linspace(x0 + .35 * (x1 - x0), x1 - .35 * (x1 - x0), 5)
    ys = np.linspace(y0 + .35 * (y1 - y0), y1 - .35 * (y1 - y0), 5)
    xx, yy = np.meshgrid(xs, ys)
    pos = a.apply_h(H, np.stack([xx, yy], -1))
    return float(a.sample_bilinear(image, pos).mean())


def simulation_checks(meta, local):
    a = load('chart_v2_existing_ring', ROOT / 'research/hue_ring/analyze_ring.py')
    robust = load('chart_v2_existing_geometry', ROOT / 'research/t1_probe/probe2/calibration_geometry.py')
    layout = {'markers': {m['corner']: m for m in meta['markers']}}
    src = [[0., 0.], [3456., 0.], [3456., 2234.], [0., 2234.]]
    dst = [[170., 155.], [2115., 108.], [2190., 1435.], [120., 1490.]]
    known = a.dlt(src, dst)
    probes = np.array([[x, y] for y in np.linspace(250., 2000., 7) for x in np.linspace(250., 3200., 9)])
    reports = []
    failures = []
    for page in meta['pages'][1:]:
        pnum = page['page']
        floating = simulate(Image.open(HERE / page['file']), known, (2400, 1600))
        photo = np.rint(np.clip(floating, 0, 255)).astype(np.uint8)
        # Preserve real exceptions. Both functions remain untouched and run unseeded.
        candidates = []
        for name, locate in [('analyze_ring.locate_screen', lambda: a.locate_screen(photo, layout)),
                             ('calibration_geometry.locate', lambda: robust.locate(a, photo, layout))]:
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    found = locate()
                err = np.linalg.norm(a.apply_h(found['H'], probes) - a.apply_h(known, probes), axis=1)
                candidates.append({'method': name, 'geometry': found, 'max_error_px': float(err.max()),
                                   'rms_error_px': float(np.sqrt(np.mean(err ** 2)))})
            except Exception as exc:
                failures.append({'page': pnum, 'method': name, 'error': f'{type(exc).__name__}: {exc}'})
        assert candidates, f'No existing locator succeeded on page {pnum}: {failures}'
        chosen = min(candidates, key=lambda x: x['max_error_px'])
        geo = chosen['geometry']
        assert chosen['max_error_px'] < 2., chosen
        assert geo['marker_cells'] == {'TL': 3, 'TR': 4, 'BR': 6, 'BL': 8}
        gray = a.gray_of(photo)
        cells = page['page_code']['cells']
        values = np.array([sample_cell(a, gray, geo['H'], c['bbox_px']) for c in cells])
        threshold = .5 * (np.percentile(values, 10) + np.percentile(values, 90))
        bits = (values > threshold).astype(int).tolist()
        assert bits == [c['bit'] for c in cells], f'Page code failed on page {pnum}'
        # Read only the nibble for this synthetic self-check, not real capture parsing.
        word = bits[4:12]
        page_read = word[2] + 2 * word[4] + 4 * word[5] + 8 * word[6]
        assert page_read == pnum and bits[12:] == [1 - b for b in bits[:12]]
        max_error, max_mean, good, total, min_pixels = 0., 0., 0, 0, 10 ** 9
        for patch in [p for p in meta['patches'] if p['page'] == pnum]:
            region = a.roi_mask(geo, patch['roi_bbox_px'], photo.shape)
            assert region is not None
            ya, yb, xa, xb, mask, _ = region
            values = floating[ya:yb, xa:xb][mask]
            assert len(values) >= 100
            error = np.abs(values - patch['p3_8bit'])
            max_error = max(max_error, float(error.max()))
            max_mean = max(max_mean, float(np.max(np.abs(values.mean(0) - patch['p3_8bit']))))
            good += int(np.count_nonzero((error <= 1.).all(axis=1)))
            total += len(values)
            min_pixels = min(min_pixels, len(values))
        assert max_error <= 1. and good == total
        Image.fromarray(photo).save(local / f'simulation_{pnum:02d}.png', icc_profile=Image.open(HERE / page['file']).info['icc_profile'])
        reports.append({'page': pnum, 'status': 'PASS', 'chosen_locator': chosen['method'],
                        'locators': [{'method': c['method'], 'max_error_px': c['max_error_px'],
                                      'rms_error_px': c['rms_error_px']} for c in candidates],
                        'marker_cells': geo['marker_cells'], 'page_code_read': page_read,
                        'max_abs_code_error_float': max_error, 'max_patch_mean_code_error': max_mean,
                        'roi_pixels_with_all_channels_within_1_code_fraction': good / total,
                        'min_roi_pixels': min_pixels, 'total_roi_pixels': total})
        print(f'page {pnum}: locator={chosen["method"]}, geometry_max={chosen["max_error_px"]:.3f}px, purity={good / total:.6f}', flush=True)
    return {'status': 'PASS', 'source_blur_sigma_px': 6., 'source_blur_fwhm_px': 6. * 2.35482,
            'simulation_color_mixing': 'linear-light Display P3; no sensor/display spectral model, noise, glare or temporal flicker',
            'source_canvas_px': [3456, 2234], 'output_canvas_px': [2400, 1600],
            'projected_screen_corners_px': dst, 'source_to_output_homography': known.tolist(),
            'central_scale': float(math.sqrt(abs(np.linalg.det(a.local_jacobian(known, 1728, 1117))))),
            'roi': 'center 40% in each dimension; all mapped pixel centers tested using recovered geometry',
            'existing_locator_failures': failures, 'pages': reports}


def contact_sheet(meta, local):
    profile = ImageCms.ImageCmsProfile(str(g.ICC))
    srgb = ImageCms.createProfile('sRGB')
    sheet = Image.new('RGB', (1440, 1214), (235, 235, 235))
    draw = ImageDraw.Draw(sheet)
    for i, page in enumerate(meta['pages']):
        im = Image.open(HERE / page['file'])
        im = ImageCms.profileToProfile(im, profile, srgb, outputMode='RGB')
        im.thumbnail((680, 440), Image.Resampling.LANCZOS)
        # White page gets a compact preview; all six chart pages are large peers.
        if i == 0:
            continue
        index = i - 1
        x, y = 20 + (index % 2) * 720, 20 + (index // 2) * 396
        im.thumbnail((680, 358), Image.Resampling.LANCZOS)
        sheet.paste(im, (x, y + 24))
        draw.text((x, y), f'Page {page["page"]} / 6', fill=(30, 30, 30))
    sheet.save(local / 'contact_sheet.png', icc_profile=ImageCms.ImageCmsProfile(srgb).tobytes())


def main():
    g.guard()
    local = g.output_dir(HERE / 'local')
    metadata_path = HERE / 'patches.json'
    meta = json.loads(metadata_path.read_text())
    report = {'schema': 'ricoh.chart_v2.validation.v1', 'status': 'RUNNING',
              'runtime': {'python': sys.version.split()[0], 'numpy': np.__version__, 'pillow': Image.__version__},
              'validation_input_sha256': {p: sha(HERE / p) for p in ['make_chart.py', 'verify_chart.py', 'patches.json']},
              'read_only_reference_sha256': {p: sha(ROOT / p) for p in ['research/hue_ring/analyze_ring.py', 'research/t1_probe/probe2/calibration_geometry.py']}}
    try:
        profile = g.ICC.read_bytes()
        assert ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(str(g.ICC))).strip() == 'Display P3'
        profiles = subprocess.run(['sips', '-g', 'profile'] + [str(HERE / p['file']) for p in meta['pages']],
                                  capture_output=True, text=True, check=True).stdout
        (local / 'icc_profiles.txt').write_text(profiles)
        assert profiles.count('profile: Display P3') == 7
        report['icc'] = {'status': 'PASS', 'sha256': hashlib.sha256(profile).hexdigest(),
                         'system_sips_display_p3_pages': 7}
        ignore = subprocess.run(['git', 'check-ignore', '-v', 'research/chart_v2/pages/01_chart.png',
                                 'research/chart_v2/local/validation.json'], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout
        (local / 'ignore-check.txt').write_text(ignore)
        assert 'research/chart_v2/.gitignore:1:/pages/' in ignore and 'research/chart_v2/.gitignore:2:/local/' in ignore
        report['git_ignore'] = 'PASS'
        repeat = subprocess.run(['python3', '-I', '-B', str(HERE / 'make_chart.py'), '--out', str(local / 'repeat')],
                                capture_output=True, text=True, check=True)
        (local / 'repeat-generation.txt').write_text(repeat.stdout + repeat.stderr)
        paths = ['patches.json'] + [p['file'] for p in meta['pages']]
        matches = {p: sha(HERE / p) == sha(local / 'repeat' / p) for p in paths}
        assert all(matches.values()), matches
        report['determinism'] = {'status': 'PASS', 'second_process_same_bytes': matches}
        report['gamut_and_layout'] = gamut_and_layout(meta, profile)
        contact_sheet(meta, local)
        report['simulation'] = simulation_checks(meta, local)
        # Existing source files were imported read-only; verify no source edit happened.
        assert all(sha(ROOT / p) == value for p, value in report['read_only_reference_sha256'].items())
        report['status'] = 'PASS'
        g.write_json(local / 'validation.json', report)
        ready = {'schema': 'ricoh.chart_v2.ready.v1', 'status': 'CHART_READY',
                 'scope': 'host-validated PNG targets and metadata; real-camera acceptance not performed; no capture parser',
                 'chart_pages': 6, 'white_pages': 1, 'chart_patch_instances': 696,
                 'validation_file': 'local/validation.json', 'validation_sha256': sha(local / 'validation.json'),
                 'sha256': {p: sha(HERE / p) for p in paths},
                 'generator_sha256': sha(HERE / 'make_chart.py'), 'verifier_sha256': sha(HERE / 'verify_chart.py')}
        g.write_json(HERE / 'CHART_READY.json', ready)
        print('PASS: ICC, determinism, gamut, all-page linear-light defocus/projective purity, existing locators, page codes')
    except Exception as exc:
        report['status'] = 'FAIL'
        report['error'] = f'{type(exc).__name__}: {exc}'
        g.write_json(local / 'validation.json', report)
        raise


if __name__ == '__main__':
    main()
