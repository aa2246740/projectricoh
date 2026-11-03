#!/usr/bin/env python3
"""Read SD photos only, copy with digest checks, and measure the screen chart.

Source photo files are opened only with mode rb. All output stays in OUT or
the two named capture-analysis report files in AUDIT. No card mutation or eject.
Run with python3 -B; imports from the existing project are read-only.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import map_coordinates

sys.dont_write_bytecode = True
ROOT = Path('/Users/wu/.t3/projects/projectricoh')
SOURCE = Path('/Volumes/RICOHDCX/DCIM/100RICOH')
OUT = ROOT / 'captures/a12-50/2026-10-16/macbook-screen-chart'
AUDIT = ROOT / 'research/ui_bug_audit'
REF = ROOT / 'research/color_references'
sys.path.insert(0, str(REF))
from tiff_read import Tiff, jpeg_exif, exif_summary, unpack_raw, crop_info
from colour_math import (srgb_decode, srgb_encode, rgb_lab, delta_e00,
                         common_white_sensor_bridge, D65)

# Manually read from the actual photographs at 1286 x 854, not the browser
# viewport. The four anchors are the outermost patch corners, TL/TR/BR/BL.
# Small lens distortion is not solved by this projective approximation; the
# centre samples remain far inside every patch, as shown in the overlays.
GEOMETRY = {
    'R8051138': ('T1', [[44, 81], [1222, 65], [1214, 788], [61, 788]]),
    'R8051139': ('T1', [[12, 72], [1271, 72], [1257, 842], [24, 832]]),
    'R8051140': ('T1', [[29, 20], [1247, 19], [1230, 771], [36, 752]]),
    'R8051141': ('T2', [[14, 41], [1239, 37], [1227, 790], [27, 782]]),
    'R8051142': ('T3', [[18, 34], [1242, 27], [1233, 775], [34, 773]]),
    'R8051143': ('T4', [[10, 49], [1248, 28], [1246, 785], [32, 792]]),
}
PARAMS = ['contrast', 'sharpness', 'vividness',
          'orange_vividness', 'green_vividness', 'blue_vividness',
          'red_vividness', 'magenta_vividness', 'orange_hue', 'green_hue',
          'blue_hue', 'red_hue', 'magenta_hue']
RICOH_DEFINITION_SOURCE = Path('/tmp/gxr_color_refs/downloads/exiftool_ricoh_definition/Ricoh.pm')
RICOH_DEFINITION_DURABLE = OUT/'provenance/Ricoh.pm'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while block := f.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    if not (path.is_relative_to(OUT) or path in (
            AUDIT / 'capture_verification.json',
            AUDIT / 'MACBOOK_CAPTURES_REPORT.md')):
        raise ValueError(f'Output outside capture-analysis ownership: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def copy_new():
    OUT.mkdir(parents=True, exist_ok=True)
    files = []
    for p in sorted(SOURCE.iterdir()):
        m = re.fullmatch(r'R805(\d{4})\.(DNG|JPG)', p.name)
        if m and int(m[1]) > 1137:
            if p.is_symlink() or not p.is_file():
                raise ValueError(f'Refusing non-regular source: {p}')
            files.append(p)
    records = []
    for source in files:
        dest = OUT / source.name
        before = digest(source)
        source_stat = source.stat()
        if not dest.exists():
            with source.open('rb') as src, dest.open('xb') as dst:
                while block := src.read(1024 * 1024):
                    dst.write(block)
        after = digest(source)
        copied = digest(dest)
        if before != after or before != copied:
            raise ValueError(f'Source/copy digest mismatch: {source.name}')
        records.append({
            'name': source.name, 'bytes': source_stat.st_size,
            'source': str(source), 'copy': str(dest),
            'source_sha256_before_copy': before,
            'source_sha256_after_copy': after,
            'copy_sha256': copied, 'sha256_match': True,
            'source_mtime_ns': source_stat.st_mtime_ns,
        })
    result = {
        'schema': 'gxr-screen-chart-read-only-copy-v1',
        'source_access_mode': 'rb only for file contents; listing/stat read-only',
        'source_mutations': [], 'eject_called': False,
        'selection': 'R805*.DNG/JPG number strictly after R8051137',
        'count': len(records), 'total_bytes': sum(r['bytes'] for r in records),
        'files': records,
    }
    save(OUT / 'copy_manifest.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--copy-only', action='store_true')
    parser.add_argument('--offline', action='store_true', help='Use copied files; do not access the SD card')
    args = parser.parse_args()
    if args.offline:
        copied = json.loads((OUT / 'copy_manifest.json').read_text())
        for row in copied['files']:
            if digest(Path(row['copy'])) != row['copy_sha256']:
                raise ValueError('Copy changed since import: ' + row['name'])
    else:
        copied = copy_new()
    print(json.dumps({'copies': copied['count'], 'bytes': copied['total_bytes'],
                      'all_hashes_match': all(r['sha256_match'] for r in copied['files'])}))
    if not args.copy_only:
        analyze(copied)


def analyze(copied):
    persist_metadata_definition()
    numeric_input_paths = [REF/'tiff_read.py', REF/'colour_math.py',
                           ROOT/'research/gr_complete_pipeline/pipeline_math.py',
                           ROOT/'research/gr_complete_pipeline/colour_math_frozen.py',
                           ROOT/'research/gr_complete_pipeline/arm_color_analysis.json',
                           ROOT/'research/gr_complete_pipeline/gr3_gr4_effective_curves.json',
                           ROOT/'research/gr_complete_pipeline/grd4_positive_film_tables.json']
    numeric_inputs = {str(p): digest(p) for p in numeric_input_paths}
    chart_file = REF / 'screen_chart.json'
    chart = json.loads(chart_file.read_text())
    html = (REF / 'screen_chart.html').read_text()
    embedded, _ = json.JSONDecoder().raw_decode(html.split('const data=', 1)[1])
    assert embedded == chart, 'HTML and JSON chart versions differ'
    pages = {p['id']: p for p in chart['pages']}
    results = []
    for dng_path in sorted(OUT.glob('R805*.DNG')):
        if dng_path.stem not in GEOMETRY:
            raise ValueError('New capture needs independent page/geometry identification: ' + dng_path.stem)
        jpeg_path = dng_path.with_suffix('.JPG')
        t = Tiff(dng_path.read_bytes())
        raw, d = unpack_raw(t)
        ox, oy, cw, ch = crop_info(d)
        with Image.open(jpeg_path) as img:
            img.load()
            jpeg = np.asarray(img.convert('RGB'))
        assert jpeg.shape == (ch, cw, 3) == (2848, 4288, 3)
        assert raw.shape == (2862, 4304)
        assert d[258]['value'] == [12] and d[259]['value'] == [1]
        assert d[33422]['raw'] == bytes([0, 1, 1, 2])
        black = float(np.mean(d[50714]['value']))
        white = float(d[50717]['value'][0])
        raw_check = verify_packed_raw(t, d, raw)
        md = read_metadata(t)
        mj = read_metadata(jpeg_exif(jpeg_path.read_bytes()))
        same_fields = ['datetime', 'iso', 'exposure', 'f_number', 'image_mode',
                       'raw13', 'display13', 'wb_mode_byte', 'iso_setting_byte']
        assert all(md[k] == mj[k] for k in same_fields)
        page_id, anchor1286 = GEOMETRY[dng_path.stem]
        corners = np.array(anchor1286, float) * np.array([cw / 1286, ch / 854])
        H = homography(corners)
        item = {
            'shot': dng_path.stem, 'page': page_id,
            'page_identification': {
                'method': 'Human visual reading of printed page/patch labels, cross-checked with JSON patch arrangement; not filename order',
                'observed_top_left_patch': pages[page_id]['patches'][0]['id'],
                'observed_next_patch': pages[page_id]['patches'][1]['id'],
                'header': pages[page_id]['title'],
                'confidence': 'confirmed by visible text and colour arrangement',
            },
            'dng_sha256': digest(dng_path), 'jpeg_sha256': digest(jpeg_path),
            'metadata_dng': md, 'metadata_jpeg': mj,
            'paired_metadata_fields_match': same_fields,
            'raw': {'stored_wh': [raw.shape[1], raw.shape[0]],
                    'crop_xywh': [ox, oy, cw, ch], 'bits': 12,
                    'compression': 'uncompressed MSB-packed TIFF FillOrder=1',
                    'black_level': black, 'white_level': white,
                    'stored_CFA': 'RGGB', 'cropped_CFA': 'GBRG',
                    'byte_roundtrip': raw_check,
                    'all_active_pixels_at_white_fraction': float(np.mean(raw[oy:oy+ch, ox:ox+cw] >= white))},
            'geometry': {'outer_patch_corners_jpeg_xy': corners.tolist(),
                         'homography_unit_grid_to_jpeg': H.tolist(),
                         'anchor_space_wh': [1286, 854],
                         'method': 'Outer corners seed the search. Each patch edge is independently located on photographed gradients; each patch has its own four corners, homography and binary ROI mask.',
                         'gutter_fraction_of_patch_xy': [8/204, 8/(1031/6)],
                         'center_fraction_xyxy': [.3, .3, .7, .7],
                         'limitation': 'Approximate patch geometry, no lens-distortion calibration; overlays expose all ROI positions'},
            'patches': [],
        }
        overlay = Image.fromarray(jpeg).resize((1286, 854))
        draw = ImageDraw.Draw(overlay)
        for patch in pages[page_id]['patches']:
            q = measure_patch(raw, jpeg, patch, H, ox, oy, black, white, dng_path.stem)
            item['patches'].append(q)
            polygon = np.array(q['roi_jpeg_polygon_xy']) * np.array([1286/cw, 854/ch])
            draw.line([tuple(x) for x in np.vstack([polygon, polygon[0]])], fill=(0, 255, 70), width=2)
            draw.text(tuple(polygon[0]), patch['id'], fill=(0, 255, 70))
        overlay.save(OUT / (dng_path.stem + '_roi_overlay.jpg'), quality=90)
        item['quality_summary'] = quality_summary(item)
        results.append(item)
        print(json.dumps({'measured': dng_path.stem, 'page': page_id,
                          'patches': len(item['patches']), 'quality': item['quality_summary']}), flush=True)

    transfer = measured_transfer(results)
    bridge = sensor_bridge(results)
    measurements = {
        'schema': 'gxr-macbook-screen-paired-patches-v1',
        'evidence': {'measured': 'Copied original DNG/JPEG bytes, EXIF/MakerNote and 288 paired ROI statistics',
                     'inferred': 'Projective ROI corners, empirical transfer interpolation, DNG ColorMatrix bridges and incomplete native CCM/gamma diagnostics',
                     'blocked': 'Calibrated GR III/IV/GRD IV camera-equivalent reference; GRD IV sensor bridge; 16-recipe control response; held-out physical-scene acceptance'},
        'copy_manifest': str(OUT / 'copy_manifest.json'),
        'chart': {'json': str(chart_file), 'sha256': digest(chart_file),
                  'html_sha256': digest(REF / 'screen_chart.html'),
                  'html_embedded_json_exactly_matches': True,
                  'nominal_CSS_is_measured_emitted_colour': False},
        'photometric_conventions': {
            'raw': '(mean channel DN - tagged black)/(tagged white-black); no demosaic, denoise, auto brightening or WB applied to primary samples',
            'jpeg': 'Full-resolution companion in-camera JPEG. Store encoded channel mean and per-pixel inverse-sRGB linear mean separately. Lab derives from linear-light mean.',
            'delta_e': 'CIEDE2000 kL=kC=kH=1, D50 Lab after Bradford adaptation of sRGB D65; model residual is not camera colour accuracy',
            'clipping_rule': 'Count raw DN>=WhiteLevel and JPEG code==255 separately by channel; report code==0 too. Mean below saturation does not rule out pixel clipping.',
        },
        'captures': results, 'measured_gxr_transfer': transfer,
        'cross_sensor_bridge': bridge,
        'numeric_inputs_before_after': {str(p): {'before': numeric_inputs[str(p)], 'after': digest(p),
                                                 'unchanged': numeric_inputs[str(p)] == digest(p)}
                                        for p in numeric_input_paths},
        'complete_calibration': False,
    }
    save(OUT / 'measurements.json', measurements)
    report(measurements, copied)
    verify_outputs(measurements, copied)


def read_metadata(t):
    out = exif_summary(t)
    root = t.ifd(t.root)
    exif = t.ifd(root[34665]['value'][0])
    note = exif[37500]
    maker = t.ifd(note['offset'] + 8, '>')
    rec = maker[0x1001]['raw']
    assert len(rec) == 224
    out.update(
        maker_firmware=maker[2]['value'], maker_record_sha256=hashlib.sha256(rec).hexdigest(),
        maker_record_hex=rec.hex(), maker_record_offset_in_tiff=maker[0x1001]['offset'],
        image_settings='Setting1' if rec[0x28] == 4 else 'other',
        setting1_fields=dict(zip(PARAMS, out['display13'])),
        wb_mode_byte=rec[0x26], wb_mode='Auto' if rec[0x26] == 0 else 'unresolved',
        wb_standard_exif=exif.get(41987, {}).get('value'),
        wb_user_axes=None, wb_user_axes_status='No verified metadata mapping; do not invert AsShotNeutral',
        iso_setting_byte=rec[0x27], iso_setting=800 if rec[0x27] == 7 else None,
        as_shot_neutral=root.get(50728, {}).get('value'),
        exposure_mode=exif.get(41986, {}).get('value'),
        lens=exif.get(42036, {}).get('value'),
        wb_iso_mapping_source=str(RICOH_DEFINITION_DURABLE),
        wb_iso_mapping_sha256=digest(RICOH_DEFINITION_DURABLE),
        wb_iso_mapping_definition='Ricoh::ImageInfo entries38 (WhiteBalance)/39 (ISOSetting), selected by MakerNote 0x1001',
        color_matrix1=root.get(50721, {}).get('value'), color_matrix2=root.get(50722, {}).get('value'),
        recipe_index=None, recipe_index_status='No unique recipe index is encoded in the verified fields; thirteen midpoint values alone do not prove slot identity',
    )
    return out


def persist_metadata_definition():
    RICOH_DEFINITION_DURABLE.parent.mkdir(parents=True, exist_ok=True)
    if RICOH_DEFINITION_SOURCE.exists():
        with RICOH_DEFINITION_SOURCE.open('rb') as f:
            content = f.read()
        if RICOH_DEFINITION_DURABLE.exists():
            assert RICOH_DEFINITION_DURABLE.read_bytes() == content
        else:
            RICOH_DEFINITION_DURABLE.write_bytes(content)
    assert RICOH_DEFINITION_DURABLE.is_file()
    save(OUT/'provenance/Ricoh_definition.json', {
        'upstream_url': 'https://raw.githubusercontent.com/exiftool/exiftool/master/lib/Image/ExifTool/Ricoh.pm',
        'original_download': str(RICOH_DEFINITION_SOURCE),
        'durable_copy': str(RICOH_DEFINITION_DURABLE),
        'sha256': digest(RICOH_DEFINITION_DURABLE),
        'source_kind': 'Local copy of ExifTool author definitions; data reference only, not executed',
        'used_definitions': ['ImageInfo WhiteBalance entry38 at source lines563..575',
                             'ImageInfo ISOSetting entry39 at source lines576..591'],
    })


def verify_packed_raw(t, d, raw):
    data = b''.join(t.data[o:o+n] for o, n in zip(d[273]['value'], d[279]['value']))
    b = np.frombuffer(data, np.uint8).reshape(-1, 3)
    v = raw.ravel()
    assert np.array_equal(v[::2] >> 4, b[:, 0])
    assert np.array_equal(((v[::2] & 15) << 4) | (v[1::2] >> 8), b[:, 1])
    assert np.array_equal(v[1::2] & 255, b[:, 2])
    # Independent scalar bit-unpack confirms endpoints and a fixed stride.
    samples = sorted(set([0, len(data)-3] + list(range(0, len(data)-3, 150003))))
    for p in samples:
        q = int.from_bytes(data[p:p+3], 'big')
        assert [q >> 12, q & 4095] == v[p//3*2:p//3*2+2].tolist()
    return {'all_strip_bytes_repack_exactly': True, 'scalar_24bit_crosschecks': len(samples),
            'bytes': len(data), 'raw_strip_sha256': hashlib.sha256(data).hexdigest(),
            'independent_external_RAW_decoder': False}


def homography(corners):
    A, b = [], []
    for (x, y), (u, v) in zip([[0, 0], [1, 0], [1, 1], [0, 1]], corners):
        A += [[x, y, 1, 0, 0, 0, -u*x, -u*y], [0, 0, 0, x, y, 1, -v*x, -v*y]]
        b += [u, v]
    return np.r_[np.linalg.solve(A, b), 1].reshape(3, 3)


def transform(H, xy):
    xyz = np.column_stack([np.asarray(xy), np.ones(len(xy))]) @ H.T
    return xyz[:, :2] / xyz[:, 2:]


def polygon_mask(poly):
    x0, y0 = np.floor(np.min(poly, axis=0)).astype(int)
    x1, y1 = np.ceil(np.max(poly, axis=0)).astype(int)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    inside = np.ones(xx.shape, bool)
    for a, b in zip(poly, np.roll(poly, -1, axis=0)):
        inside &= (b[0]-a[0])*(yy+.5-a[1]) - (b[1]-a[1])*(xx+.5-a[0]) >= -1e-8
    return [int(x0), int(y0), int(x1), int(y1)], xx, yy, inside


def periodic(profile, spacing=1):
    p = np.asarray(profile, float)
    p = p[np.isfinite(p)]
    center = float(np.mean(p))
    if len(p) < 20 or center <= 1e-9:
        return {'available': False}
    x = np.linspace(-1, 1, len(p))
    residual = p - np.polyval(np.polyfit(x, p, 2), x)
    window = np.hanning(len(p))
    amplitude = 2*np.abs(np.fft.rfft(residual * window))/window.sum()
    frequency = np.fft.rfftfreq(len(p), spacing)
    eligible = (frequency >= .03/spacing) & (frequency <= .45/spacing)
    k = np.flatnonzero(eligible)[np.argmax(amplitude[eligible])]
    base = float(np.median(amplitude[eligible]))
    return {'available': True, 'samples': len(p),
            'mean': center, 'quadratic_detrended_p95_p05_relative': float(np.ptp(np.percentile(residual, [5, 95]))/center),
            'peak_cycles_per_full_resolution_pixel': float(frequency[k]),
            'peak_period_full_resolution_pixels': float(1/frequency[k]),
            'sinusoid_peak_amplitude_relative': float(amplitude[k]/center),
            'peak_amplitude_to_median_spectral_bin': float(amplitude[k]/max(base, 1e-12)),
            'periodic_pattern_flag': bool(amplitude[k]/center > .005 and amplitude[k]/max(base, 1e-12) > 12),
            'threshold_is_diagnostic_not_vendor_specification': True}


def refine_patch_edges(jpeg, seed_corners):
    center = np.mean(seed_corners, axis=0)
    cx, cy = np.rint(center).astype(int)
    color = jpeg[cy-8:cy+9, cx-8:cx+9].mean((0, 1))
    edges = []
    line_eqs = []
    for a, b in zip(seed_corners, np.roll(seed_corners, -1, axis=0)):
        v = b-a
        inward = np.array([-v[1], v[0]])/np.linalg.norm(v)
        along = np.linspace(.20, .80, 25)
        offsets = np.arange(-34, 35, dtype=float)
        base = a + along[:, None]*v
        points = base[:, None, :] + offsets[None, :, None]*inward
        samples = np.stack([map_coordinates(jpeg[:, :, c], [points[:, :, 1], points[:, :, 0]],
                                          order=1, mode='nearest', output=np.float64)
                            for c in range(3)], axis=-1)
        strength = np.linalg.norm(samples[:, 4:]-samples[:, :-4], axis=2)/4
        position = offsets[2:-2]
        # Inside the desired patch should resemble its own centre more than
        # the gray gap does. This rejects the opposite edge of a gray gutter.
        candidates = np.arange(8, len(offsets)-8)
        inside_dist = np.linalg.norm(samples[:, candidates+8]-color, axis=2)
        outside_dist = np.linalg.norm(samples[:, candidates-8]-color, axis=2)
        improves = outside_dist-inside_dist
        score = strength[:, candidates-2] * np.exp(-position[candidates-2]**2/(2*25**2))
        score *= np.where(improves > .5, 1, .18)
        best = np.argmax(score, axis=1)
        chosen = candidates[best]
        selected_score = score[np.arange(len(along)), best]
        support = selected_score > 1.0
        observed_offsets = offsets[chosen]
        # The four photographed outer anchors already fix edge directions.
        # Locate each actual gray transition independently along its normal.
        # Requiring a coherent mode avoids fitting noisy/moire pixels as a
        # wildly sloping low-contrast patch edge.
        candidates_offset = np.arange(-26, 27)
        mode_weights = [np.sum(selected_score[support & (np.abs(observed_offsets-c) <= 3)])
                        for c in candidates_offset]
        mode = candidates_offset[int(np.argmax(mode_weights))]
        keep = support & (np.abs(observed_offsets-mode) <= 3)
        normal = inward
        if keep.sum() >= 9:
            shift = float(np.median(observed_offsets[keep]))
            constant = float(normal @ a + shift)
            rms = float(np.sqrt(np.mean((observed_offsets[keep]-shift)**2)))
            used = True
            n = int(keep.sum())
        else:
            normal = inward
            constant = float(inward @ a)
            rms = None
            used = False
            n = int(support.sum())
        line_eqs.append((normal, constant))
        edges.append({'gradient_fit_used': used, 'gradient_sample_support': n,
                      'line_normal_xy': normal.tolist(), 'line_constant': constant,
                      'fit_RMS_pixels': rms})
    corners = []
    for i in range(4):
        n1, c1 = line_eqs[(i-1) % 4]
        n2, c2 = line_eqs[i]
        corners.append(np.linalg.solve(np.array([n1, n2]), [c1, c2]))
    corners = np.array(corners)
    movement = np.linalg.norm(corners-seed_corners, axis=1)
    if np.max(movement) > 65:
        raise ValueError(f'Patch boundary fit escaped its search seed: {movement}')
    return corners, {'method': 'Photographed gray-separator gradients, 25 interior edge probes, coherent transition mode, robust normal-offset edge fit and adjacent-line intersections; directions fixed by photographed outer homography',
                     'edges_top_right_bottom_left': edges,
                     'seed_corner_adjustments_pixels': movement.tolist(),
                     'limitation': 'Straight-edge fit; low-contrast edges may retain projective seed and are explicitly flagged'}


def measure_patch(raw, jpeg, patch, H, ox, oy, black, white, shot):
    col, row = patch['col'], patch['row']
    gx, gy = 8/204, 8/(1031/6)
    u0 = col*(1+gx)/(8+7*gx)
    u1 = (col*(1+gx)+1)/(8+7*gx)
    v0 = row*(1+gy)/(6+5*gy)
    v1 = (row*(1+gy)+1)/(6+5*gy)
    seed = transform(H, [[u0, v0], [u1, v0], [u1, v1], [u0, v1]])
    patch_corners, boundary_fit = refine_patch_edges(jpeg, seed)
    patch_H = homography(patch_corners)
    poly = transform(patch_H, [[.3, .3], [.7, .3], [.7, .7], [.3, .7]])
    box, xx, yy, mask = polygon_mask(poly)
    x0, y0, x1, y1 = box
    assert 0 <= x0 < x1 <= jpeg.shape[1] and 0 <= y0 < y1 <= jpeg.shape[0]
    mask_dir = OUT/'roi_masks'
    mask_dir.mkdir(exist_ok=True)
    mask_path = mask_dir / (shot + '_' + patch['id'] + '.png')
    Image.fromarray(mask.astype(np.uint8)*255).save(mask_path, optimize=True)
    block = jpeg[y0:y1, x0:x1]
    pix = block[mask].astype(float)/255
    linear = srgb_decode(block.astype(float)/255)
    encoded_mean = pix.mean(0)
    linear_mean = linear[mask].mean(0)
    equivalent_encoded = srgb_encode(linear_mean)
    phase = np.array([[0, 1], [1, 2]])[(yy+oy) % 2, (xx+ox) % 2]
    mosaic = raw[y0+oy:y1+oy, x0+ox:x1+ox]
    means, channels = [], {}
    for c, name in enumerate(['R', 'G', 'B']):
        samples = mosaic[mask & (phase == c)].astype(float)
        means.append(samples.mean())
        channels[name] = {'count': len(samples), 'mean_DN': float(samples.mean()),
                          'std_DN': float(samples.std()),
                          'p01_p50_p99_DN': np.percentile(samples, [1, 50, 99]).tolist(),
                          'zero_fraction': float(np.mean(samples <= black)),
                          'at_white_fraction': float(np.mean(samples >= white)),
                          'near_white_fraction_DN4094': float(np.mean(samples >= white-1))}
    # Green samples only, binned over CFA pairs, avoid treating the Bayer
    # alternation itself as a display stripe.
    greens = mask & (phase == 1)
    raw_profiles = []
    for axis in [0, 1]:
        loc = ((yy-y0) if axis == 0 else (xx-x0))[greens] // 2
        sums = np.bincount(loc, weights=mosaic[greens].astype(float)-black)
        counts = np.bincount(loc)
        raw_profiles.append(np.divide(sums, counts, out=np.full_like(sums, np.nan), where=counts > 0))
    lum = linear @ np.array([.2126729, .7151522, .0721750])
    row_n, col_n = mask.sum(axis=1), mask.sum(axis=0)
    row_profile = np.divide(np.sum(lum*mask, axis=1), row_n, out=np.full(len(row_n), np.nan), where=row_n > 0)
    col_profile = np.divide(np.sum(lum*mask, axis=0), col_n, out=np.full(len(col_n), np.nan), where=col_n > 0)
    normalized = (np.array(means)-black)/(white-black)
    jp_white = np.mean(pix >= 1, axis=0)
    valid = bool(max(channels[c]['at_white_fraction'] for c in channels) < .001
                 and np.max(jp_white) < .001 and normalized.min() > 1/4095)
    return {
        'id': patch['id'], 'group': patch['group'], 'row': row, 'col': col,
        'nominal_CSS_srgb8': patch['rgb8_srgb'],
        'nominal_CSS_is_sensor_ground_truth': False,
        'photographed_patch_corners_jpeg_xy': patch_corners.tolist(),
        'patch_homography_unit_patch_to_jpeg': patch_H.tolist(),
        'boundary_fit': boundary_fit,
        'roi_jpeg_polygon_xy': poly.tolist(), 'roi_jpeg_bbox_xyxy': box,
        'roi_binary_mask': {'path': str(mask_path), 'sha256': digest(mask_path),
                            'bbox_jpeg_xyxy': box, 'inside_code': 255, 'outside_code': 0,
                            'coordinate_rule': 'Mask pixel [y,x] corresponds to JPEG [bbox_y0+y,bbox_x0+x] and RAW [bbox_y0+y+7,bbox_x0+x+8]'},
        'roi_raw_polygon_xy': (poly + [ox, oy]).tolist(),
        'pixels_jpeg': int(mask.sum()), 'raw_channels': channels,
        'raw_RGB_DN_mean': means,
        'raw_RGB_black_white_normalized': normalized.tolist(),
        'jpeg_srgb_encoded_mean': encoded_mean.tolist(),
        'jpeg_linear_srgb_mean': linear_mean.tolist(),
        'jpeg_linear_mean_as_encoded_srgb': equivalent_encoded.tolist(),
        'jpeg_Lab_D50_of_linear_mean': rgb_lab(equivalent_encoded[None, :])[0].tolist(),
        'jpeg_encoded_std': pix.std(0).tolist(),
        'jpeg_channel_at_255_fraction': jp_white.tolist(),
        'jpeg_channel_at_0_fraction': np.mean(pix <= 0, axis=0).tolist(),
        'spatial_quality': {'jpeg_linear_Y_row': periodic(row_profile),
                            'jpeg_linear_Y_column': periodic(col_profile),
                            'RAW_G_row': periodic(raw_profiles[0], 2),
                            'RAW_G_column': periodic(raw_profiles[1], 2)},
        'valid_for_empirical_transfer': valid,
    }


def quality_summary(item):
    p = item['patches']
    bright = [q for q in p if np.mean(q['jpeg_srgb_encoded_mean']) > .12]
    def stat(name, key):
        vals = [q['spatial_quality'][name][key] for q in bright if q['spatial_quality'][name]['available']]
        return np.percentile(vals, [50, 95, 100]).tolist()
    return {
        'patches': len(p), 'transfer_usable_patches': sum(q['valid_for_empirical_transfer'] for q in p),
        'RAW_clipped_patch_ids': [q['id'] for q in p if max(c['at_white_fraction'] for c in q['raw_channels'].values()) >= .001],
        'JPEG_255_clipped_patch_ids': [q['id'] for q in p if max(q['jpeg_channel_at_255_fraction']) >= .001],
        'RAW_G_periodic_column_flag_patch_ids': [q['id'] for q in bright if q['spatial_quality']['RAW_G_column'].get('periodic_pattern_flag')],
        'RAW_G_periodic_row_flag_patch_ids': [q['id'] for q in bright if q['spatial_quality']['RAW_G_row'].get('periodic_pattern_flag')],
        'JPEG_column_sinusoid_amplitude_relative_p50_p95_max': stat('jpeg_linear_Y_column', 'sinusoid_peak_amplitude_relative'),
        'JPEG_row_sinusoid_amplitude_relative_p50_p95_max': stat('jpeg_linear_Y_row', 'sinusoid_peak_amplitude_relative'),
        'reflection_observed_visually': True,
        'refresh_banding_proven': False,
        'refresh_banding_limit': 'Single photographs at 1/100..1/250s cannot separate display refresh/PWM from optical moire or reflection. Profiles quantify spatial structure only.',
    }


def model_features(x, kind):
    if kind == 'affine_linear':
        return np.column_stack([np.ones(len(x)), x])
    r, g, b = np.cbrt(np.maximum(x, 0)).T
    return np.column_stack([np.ones(len(x)), r, g, b, r*r, g*g, b*b, r*g, r*b, g*b])


def fit_model(x, y, kind):
    a = model_features(x, kind)
    reg = np.eye(a.shape[1])*1e-6
    reg[0, 0] = 0
    return np.linalg.solve(a.T@a+reg, a.T@y)


def metric(pred, actual):
    pred = np.clip(pred, 0, 1)
    de = delta_e00(rgb_lab(pred), rgb_lab(actual))
    return {'patches': len(de), 'deltaE00_p50_p90_max': np.percentile(de, [50, 90, 100]).tolist(),
            'encoded_RGB8_RMSE': float(np.sqrt(np.mean((pred-actual)**2))*255)}


def measured_transfer(items):
    canonical = ['R8051140', 'R8051141', 'R8051142', 'R8051143']
    data = []
    for item in items:
        neutral = np.array(item['metadata_dng']['as_shot_neutral'])
        for p in item['patches']:
            if p['valid_for_empirical_transfer']:
                data.append((item['shot'], item['page'], p['id'],
                             np.array(p['raw_RGB_black_white_normalized'])/neutral,
                             np.array(p['jpeg_linear_mean_as_encoded_srgb']),
                             ','.join(map(str, p['nominal_CSS_srgb8']))))
    shot = np.array([v[0] for v in data])
    page = np.array([v[1] for v in data])
    x = np.array([v[3] for v in data]); y = np.array([v[4] for v in data])
    colour = np.array([v[5] for v in data])
    train = np.isin(shot, canonical)
    models = {}
    for kind in ['affine_linear', 'quadratic_cuberoot']:
        target = srgb_decode(y) if kind == 'affine_linear' else y
        B = fit_model(x[train], target[train], kind)
        def predict(xx, BB):
            q = model_features(xx, kind) @ BB
            return srgb_encode(q) if kind == 'affine_linear' else q
        folds = {}
        for pg in ['T1', 'T2', 'T3', 'T4']:
            te = train & (page == pg)
            test_colours = np.unique(colour[te])
            tr = train & (page != pg) & ~np.isin(colour, test_colours)
            BB = fit_model(x[tr], target[tr], kind)
            folds[pg] = metric(predict(x[te], BB), y[te])
            folds[pg].update(training_patches=int(tr.sum()),
                             training_unique_nominal_RGBs=int(len(np.unique(colour[tr]))),
                             identical_nominal_RGB_overlap_train_test=0)
        models[kind] = {'features': '1,R,G,B in WB-normalized linear RAW' if kind == 'affine_linear' else '1,cbrt(R/G/B), their squares and pair products',
                        'target': 'linear-sRGB mean' if kind == 'affine_linear' else 'encoded equivalent of linear-sRGB mean',
                        'coefficients_rows_features_cols_RGB': B.tolist(),
                        'training': metric(predict(x[train], B), y[train]),
                        'leave_one_page_out': folds,
                        'holdout_rule': 'Hold out the entire page AND exclude every identical nominal RGB occurring in its test patches from the other training pages; no repeated screen colour crosses train/test',
                        'T1_other_exposures_repeat_diagnostic': metric(predict(x[~train], B), y[~train]),
                        'not_a_general_ISP_or_recipe_control_model': True}
    ramps = []
    for item in items:
        if item['page'] != 'T1':
            continue
        neutral_patches = [p for p in item['patches'] if p['id'].startswith('TN')]
        raw_g = np.array([p['raw_RGB_DN_mean'][1] for p in neutral_patches])
        jpeg_Y = np.array([np.array(p['jpeg_linear_srgb_mean']) @ [.2126729, .7151522, .0721750] for p in neutral_patches])
        ramps.append({'shot': item['shot'], 'observed_neutral_pairs': [
            {'id': p['id'], 'nominal_gray8': p['nominal_CSS_srgb8'][0],
             'measured_RAW_RGB': p['raw_RGB_black_white_normalized'],
             'measured_JPEG_srgb': p['jpeg_linear_mean_as_encoded_srgb'],
             'clipping_free': p['valid_for_empirical_transfer']} for p in neutral_patches],
            'raw_G_nonincreasing_steps_in_nominal_gray_order': int(np.sum(np.diff([p['raw_RGB_DN_mean'][1] for p in neutral_patches]) <= 0)),
            'jpeg_linear_Y_nonincreasing_steps_in_nominal_gray_order': int(np.sum(np.diff([np.array(p['jpeg_linear_srgb_mean']) @ [.2126729, .7151522, .0721750] for p in neutral_patches]) <= 0)),
            'RAW_G_nonincreasing_transitions': [{'from': neutral_patches[k]['id'], 'to': neutral_patches[k+1]['id'],
                                                'DN_before_after': raw_g[k:k+2].tolist()}
                                               for k in np.flatnonzero(np.diff(raw_g) <= 0)],
            'JPEG_Y_nonincreasing_transitions': [{'from': neutral_patches[k]['id'], 'to': neutral_patches[k+1]['id'],
                                                 'linear_Y_before_after': jpeg_Y[k:k+2].tolist()}
                                                for k in np.flatnonzero(np.diff(jpeg_Y) <= 0)],
            'black_patch_TN01_RAW_RGB_DN': neutral_patches[0]['raw_RGB_DN_mean'],
            'white_patch_TN32_RAW_RGB_DN': neutral_patches[-1]['raw_RGB_DN_mean'],
            'black_to_white_RGB_ratio': (np.array(neutral_patches[0]['raw_RGB_DN_mean'])/np.array(neutral_patches[-1]['raw_RGB_DN_mean'])).tolist(),
            'black_patch_JPEG_encoded_RGB8_of_linear_mean': (np.array(neutral_patches[0]['jpeg_linear_mean_as_encoded_srgb'])*255).tolist(),
            'black_floor_interpretation': 'Measured screen-black ROI includes sensor offsets/noise, display black leakage, flare and room/person reflections; no dark frame or photometer separates them'})
    repeats = []
    reference = next(i for i in items if i['shot'] == 'R8051140')
    ref_p = {p['id']: p for p in reference['patches']}
    ref_t = reference['metadata_dng']['exposure'][0]
    ref_black = np.array(ref_p['TN01']['raw_RGB_DN_mean'])
    for item in items:
        if item['page'] != 'T1' or item['shot'] == reference['shot']:
            continue
        actual_t = item['metadata_dng']['exposure'][0]
        actual_p = {p['id']: p for p in item['patches']}
        actual_black = np.array(actual_p['TN01']['raw_RGB_DN_mean'])
        ratios, signal_ratios, ids = [], [], []
        for p in item['patches']:
            r = ref_p[p['id']]
            if (p['valid_for_empirical_transfer'] and r['valid_for_empirical_transfer']
                    and np.min(np.array(r['raw_RGB_DN_mean'])-ref_black) > 40):
                a = np.array(p['raw_RGB_DN_mean']); b = np.array(r['raw_RGB_DN_mean'])
                ratios.append(a/b * ref_t/actual_t)
                signal_ratios.append((a-actual_black)/(b-ref_black) * ref_t/actual_t)
                ids.append(p['id'])
        ratios = np.array(ratios); signal_ratios = np.array(signal_ratios)
        repeats.append({'shot': item['shot'], 'reference': reference['shot'],
                        'expected_RAW_scale_from_shutter': actual_t/ref_t,
                        'patch_count': len(ids), 'patch_ids': ids,
                        'RAW_RGB_exposure_normalized_ratio_p10_p50_p90': np.percentile(ratios, [10, 50, 90], axis=0).tolist(),
                        'black_subtracted_RAW_RGB_exposure_normalized_ratio_p10_p50_p90': np.percentile(signal_ratios, [10, 50, 90], axis=0).tolist(),
                        'RAW_RGB_exposure_normalized_abs_relative_error_p50_p90': np.percentile(np.abs(ratios-1), [50, 90]).tolist(),
                        'per_patch_RAW_RGB_exposure_normalized_ratio': ratios.tolist(),
                        'limit': 'Same CSS colours, different photographed screen positions/reflections and shutter periods. Exposure normalization is a consistency diagnostic, not a fitted correction used in model holdout.'})
    return {'evidence_level': 'Measured paired samples; regression is an empirical approximation',
            'canonical_training_shots': canonical, 'canonical_training_reason': 'Same ISO800/F4/1/200s; T1 repeat exposures are evaluated separately',
            'training_patch_count_after_clipping_filter': int(train.sum()),
            'other_exposure_T1_patch_count_after_filter': int((~train).sum()),
            'WB_handling': 'Divide primary RAW means by each DNG AsShotNeutral, preserving actual Auto-WB variation; no fitted per-image exposure correction',
            'models': models, 'neutral_transfer_ramps': ramps,
            'T1_exposure_normalized_repeat_consistency': repeats,
            'interpretation': 'Residuals quantify these paired photos only. Reflection, Auto WB, short shutter, single control state and no held-out V/physical scenes prevent full recipe response or cross-camera visual acceptance.'}


def sensor_bridge(items):
    prior_path = REF / 'common_white_sensor_bridges.json'
    prior = json.loads(prior_path.read_text())
    first = Tiff((OUT / (items[0]['shot'] + '.DNG')).read_bytes()).tags()
    result = {'evidence_level': 'INFERRED_COLORIMETRIC_BRIDGE_NOT_MEASURED_CROSS_SENSOR',
              'common_white_xyz': D65.tolist(),
              'common_white_status': 'Fixed D65 assumption; emitted screen white/spectrum not measured',
              'global_exposure_scale': None, 'actual_GR_equivalent_target_available': False,
              'GR_III_GR_IV': {}, 'GRD_IV': {
                  'native_table_file': str(ROOT / 'research/gr_complete_pipeline/grd4_positive_film_tables.json'),
                  'native_table_sha256': digest(ROOT / 'research/gr_complete_pipeline/grd4_positive_film_tables.json'),
                  'native_sensor_ColorMatrix': None, 'measured_sensor_bridge': None,
                  'target_JPEG': None, 'status': 'BLOCKED: native A/B/type23/type28 table bytes do not identify GRD IV spectral sensor mapping or complete pixel pipeline. No original GRD IV DNG paired with these screen captures exists.'}}
    for model in ['GR III', 'GR IV']:
        src = prior['inputs'][model]
        path = Path(src['path'])
        tag_path = OUT/'provenance'/('gr3_bridge_dng_tags.json' if model == 'GR III' else 'gr4_bridge_dng_tags.json')
        if path.is_file():
            assert digest(path) == src['sha256']
            source_tags = Tiff(path.read_bytes()).tags()
            needed = [50721, 50722, 50723, 50724, 50727, 50728, 50778, 50779, 50931, 50932]
            tags = {k: source_tags[k] for k in needed if k in source_tags}
            save(tag_path, {'source': src, 'tags': {str(k): v for k, v in tags.items()},
                            'meaning': 'Exact decoded DNG metadata from the hash-verified original local input, retained to rerun the matrix calculation without preserving a second large RAW copy'})
        else:
            saved = json.loads(tag_path.read_text())
            assert saved['source']['sha256'] == src['sha256']
            tags = {int(k): v for k, v in saved['tags'].items()}
        assert all(i['metadata_dng']['color_matrix1'] == first[50721]
                   and i['metadata_dng']['color_matrix2'] == first[50722] for i in items)
        B, desc = common_white_sensor_bridge(first, tags, D65)
        old = next(x for x in prior['bridges'] if x['model'] == model)
        assert np.max(np.abs(B - np.array(old['B_unscaled_gxr_to_gr']))) < 1e-12
        rows = []
        for item in items:
            for patch in item['patches']:
                rows.append({'shot': item['shot'], 'patch': patch['id'],
                             'native_camera_RGB_unscaled': (B @ np.array(patch['raw_RGB_black_white_normalized'])).tolist()})
        result['GR_III_GR_IV'][model] = {**desc, 'source': src,
            'persistent_source_tags': {'path': str(tag_path), 'sha256': digest(tag_path)},
            'source_note': 'GR III original-camera DNG matrices' if model == 'GR III' else 'GR IV Lightroom-written DNG matrices are auxiliary and not independently verified native Ricoh matrices',
            'new_GXR_ColorMatrix_matches_prior': True, 'patch_coordinates': rows}
    result['native_partial_CCM_gamma_diagnostics'] = native_diagnostics(items, result)
    save(OUT / 'cross_sensor_bridge.json', result)
    return result


def native_diagnostics(items, bridges):
    pipeline = ROOT / 'research/gr_complete_pipeline'
    sys.path.insert(0, str(pipeline))
    from pipeline_math import compose_q13, compose_q13_i32, front_q8, curve_lookup
    colors = json.loads((pipeline / 'arm_color_analysis.json').read_text())
    curves = json.loads((pipeline / 'gr3_gr4_effective_curves.json').read_text())
    answer = {'complete_target': False,
              'parameters': {'runtime_gamma_gain': 8192, 'flag': 0, 'input_exposure_scale': 1,
                             'ColorMatrix_gain_scalar': 128, 'white_balance': 'common D65 matrix neutral scaled to green=1'},
              'parameter_status': 'Explicit diagnostic assumptions, not measured camera runtime state or defaults',
              'missing_stages': ['sensor spectral/photometric calibration', 'actual runtime gain and exposure scale',
                                 'hardware MultiAxial pixel operation', 'ToneControlTuning/shadow corrections',
                                 'highlight gamut handling', 'demosaic and spatial processing', 'exact final YCC/output transfer'],
              'HiContrastBW': 'Not rendered: native grayscale/filter/toning pixel stages are not closed',
              'inputs': {n: digest(pipeline/n) for n in ['arm_color_analysis.json', 'gr3_gr4_effective_curves.json', 'pipeline_math.py']},
              'modes': []}
    for mk, model in [('gr3', 'GR III'), ('gr4', 'GR IV')]:
        bridge = bridges['GR_III_GR_IV'][model]
        B = np.array(bridge['B_unscaled_gxr_to_gr'])
        neutral = np.array(bridge['M_gr_xyz_to_camera']) @ D65
        neutral /= neutral[1]
        for mode, curve_name in [('Standard', 'Standard'), ('Positive Film', 'PositiveFilm'), ('Negative Film', 'NegativeFilm')]:
            m = colors['models'][mk]['modes'][mode]
            sat = np.array(m['saturation_matrices'][m['neutral_sat_array_index']]['Q13'])
            combined = compose_q13_i32(compose_q13(sat, m['look_matrix']['Q13']), m['sensor_ccm']['Q13'])
            matrix = front_q8(combined)
            c = next(c for c in curves['effective_curves'] if c['id'] == f'{mk}-{curve_name}-gain8192')
            predicted = []
            for item in items:
                for p in item['patches']:
                    x = B @ np.array(p['raw_RGB_black_white_normalized'])
                    lin = (matrix/256) @ (x/neutral)
                    out = np.clip(curve_lookup(c['curve_u16_256'], np.clip(lin, 0, 1)*4095)/16384, 0, 1)
                    predicted.append({'shot': item['shot'], 'patch': p['id'],
                                      'partial_predicted_encoded_RGB': out.tolist()})
            answer['modes'].append({'model': model, 'mode': mode,
                                    'curve_id': c['id'], 'curve_state_kind': c['state_kind'],
                                    'front_signed_Q8': matrix.tolist(),
                                    'defaults_status': m['factory_default_status'],
                                    'predictions_not_camera_equivalent_targets': predicted})
    return answer


def report(data, copied):
    lines = ['# MacBook 屏幕色卡照片分析', '',
             '12 个新原片已复制并逐份核对 SHA-256。6 对照片覆盖 T1 三次、T2/T3/T4 各一次，共提取 288 组同位置 RAW/JPEG 色块。SD 卡只读访问，未写入、删除或弹出。', '',
             '这批可测量当前 Setting1 基准的 DNG→JPEG 关系，不能校准 16 个配方，也不能作为完整 GR 相机等效验收。实际拍摄为 ISO800、Auto WB、短快门，画面有反射及空间细纹；GR III/IV 原生参考仍缺像素处理环节，GRD IV 缺传感器桥接。', '',
             '| 照片 | 页面 | EXIF 时间 | ISO | 快门 | 光圈 | WB | RAW/JPEG 可用色块 |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for item in data['captures']:
        m = item['metadata_dng']
        lines.append(f"| {item['shot']} | {item['page']} | {m['datetime']} | {m['iso'][0]} | 1/{round(1/m['exposure'][0])}s | F{m['f_number'][0]:g} | {m['wb_mode']} | {item['quality_summary']['transfer_usable_patches']}/48 |")
    lines += ['', '页面以实拍角标与色块 ID 识别，未按文件编号推测。模板是 `research/color_references/screen_chart.json`；HTML 内嵌的全部 JSON 与它完全一致。原片保留原名。源与副本完整哈希见 [copy_manifest.json](../../captures/a12-50/2026-10-16/macbook-screen-chart/copy_manifest.json)。', '',
              '全部 MakerNote `R+0x28=0x04`，对应 Setting1；`R+0x31..33` 与 `R+0x78..81` 共 13 字节全部为 raw3，显示值全部为 5。DNG 和 JPEG 一致。WB `R+0x26=0`，EXIF WhiteBalance=0，均为 Auto；ISOSetting `R+0x27=7`，对应 ISO800。WB 两轴偏移和唯一配方槽号没有已验证的元数据映射，保留 null，不从最终白平衡增益反推。', '',
              'RAW 存储为 4304×2862 的 12-bit 无压缩 RGGB，裁切 `(8,7,4288,2848)`。裁切后 CFA 相位为 GBRG。脚本逐字节回打包全部 RAW strip，并以独立的 24-bit 标量解包交叉核对固定样本；这证明字节覆盖正确，不冒充第二套外部 RAW 解码器。', '',
              '外框投影仅用于定位搜索范围。每块四边各取 25 个内部探针，在实拍灰色隔条的梯度上找一致边界，再拟合平行于实拍外框的边线并求四角；低对比边界保留 seed 并逐边标记。每块独立保存四角、homography 与中央 40%×40% 的二值 PNG mask，`roi_masks/` 的 bbox 说明可直接重建取样。没有镜头畸变标定，几何仍是近似。每张 `_roi_overlay.jpg` 展示全部取样位置。RAW 三通道分别保留样本数、均值、标准差、分位数及白端/黑端比例；JPEG 同时保留编码均值与逐像素逆 sRGB 后的线性均值。Lab 用线性均值。', '',
              '| 照片 | RAW 截断块数 | JPEG 255 截断块数 | RAW G 列方向周期结构块数 | RAW G 行方向周期结构块数 |',
              '| --- | --- | --- | --- | --- |']
    for item in data['captures']:
        q = item['quality_summary']
        lines.append(f"| {item['shot']} | {len(q['RAW_clipped_patch_ids'])} | {len(q['JPEG_255_clipped_patch_ids'])} | {len(q['RAW_G_periodic_column_flag_patch_ids'])} | {len(q['RAW_G_periodic_row_flag_patch_ids'])} |")
    lines += ['', '截断表的阈值是某通道至少 0.1% ROI 像素达到 RAW WhiteLevel=4095 或 JPEG=255。两个域分别统计，不能用 JPEG 看似正常推断 RAW 未截断。周期结构用去二次趋势的行/列均值 FFT 检查，阈值为相对幅度>0.5%且峰值>频带中位数12倍。RAW 只用绿色 CFA 样本并按 2×2 位置分箱，避开 Bayer 自身的交替。该阈值是诊断规则；单张照片不能把摩尔纹、反射和刷新/PWM 条纹完全区分。短快门与反射足以阻止把本批宣称为清洁标定数据。', '',
              'DNG→JPEG 的 288 个实测 RGB 对与三条 T1 中性灰阶记录位于 `measurements.json`。固定 1/200s 的 R8051140–1143 为 192 块候选训练样本，其余两张 T1 只作不同曝光重复诊断。每张先按其 DNG AsShotNeutral 处理 Auto WB；没有为每张额外拟合曝光。经验模型分别为线性 RAW→线性 sRGB 仿射，以及立方根 RAW 的二次式→编码 sRGB。留一整页时，还从其他训练页剔除与测试页相同 nominal RGB 的全部重复色块，训练/测试相同 RGB 交集为零。其残差不是相机准确度或 16 个控件的响应。', '',
              '| 经验模型 | 训练 ΔE00 P50/P90 | 留一页 ΔE00 P90，T1/T2/T3/T4 | 其他曝光 T1 ΔE00 P90 |',
              '| --- | --- | --- | --- |']
    for name, model in data['measured_gxr_transfer']['models'].items():
        tr = model['training']['deltaE00_p50_p90_max']
        folds = '/'.join(f"{model['leave_one_page_out'][p]['deltaE00_p50_p90_max'][1]:.2f}" for p in ['T1', 'T2', 'T3', 'T4'])
        other = model['T1_other_exposures_repeat_diagnostic']['deltaE00_p50_p90_max'][1]
        lines.append(f'| {name} | {tr[0]:.2f}/{tr[1]:.2f} | {folds} | {other:.2f} |')
    lines += ['', '| T1 照片 | 黑块 RAW G DN | 黑/白 RAW G | RAW G 非递增步数 | JPEG线性Y 非递增步数 |',
              '| --- | --- | --- | --- | --- |']
    for ramp in data['measured_gxr_transfer']['neutral_transfer_ramps']:
        lines.append(f"| {ramp['shot']} | {ramp['black_patch_TN01_RAW_RGB_DN'][1]:.2f} | {ramp['black_to_white_RGB_ratio'][1]*100:.2f}% | {ramp['raw_G_nonincreasing_steps_in_nominal_gray_order']}/31 | {ramp['jpeg_linear_Y_nonincreasing_steps_in_nominal_gray_order']}/31 |")
    lines += ['', '黑块 DN 包含传感器偏置/噪声、屏幕黑位、眩光和环境反射，没有暗场或光度计，不能单独分解。灰阶反向步的色块 ID 与前后数值已列在 JSON；网页 nominal Gray 并非屏幕实际发光强度。', '',
              '| 重复照片，对照 R8051140 | 按快门归一的 RAW RGB 相对误差 P50 | P90 |',
              '| --- | --- | --- |']
    for repeat in data['measured_gxr_transfer']['T1_exposure_normalized_repeat_consistency']:
        e = repeat['RAW_RGB_exposure_normalized_abs_relative_error_p50_p90']
        lines.append(f"| {repeat['shot']} | {e[0]*100:.2f}% | {e[1]*100:.2f}% |")
    lines += ['', '重复比较仅使用参考帧扣除自身黑块后各通道均超过 40 DN 的色块。JSON 同时保存不扣黑与逐张扣黑后的通道比值。此比较量化同一页面在不同快门/机位的漂移，不把漂移拟合回训练数据。', '',
              'WB/ISO 的 ExifTool 作者定义已持久复制到 `captures/a12-50/2026-10-16/macbook-screen-chart/provenance/Ricoh.pm`，保留原始版权与许可。它只作定义数据，没有执行。SHA-256：`' + digest(RICOH_DEFINITION_DURABLE) + '`。原始 URL、实际本地下载位置和使用条目见同目录 `Ricoh_definition.json`。']
    lines += ['', 'GR III 与 GR IV 逐块桥接数值已写入 `cross_sensor_bridge.json`，并核对本批 GXR ColorMatrix 与既有基准完全一致。采用同一 D65 白点、`B=M_GR·inv(M_GXR)`，不使用两张照片各自的 WB，也不使用 DCP。它是 ColorMatrix 近似，曝光标度尚未知，不能称为实测跨传感器映射。GR III 的来源是原机 DNG；GR IV 来源是 Lightroom 写出的 DNG，矩阵仅作辅助证据，不能称为已核实的原机矩阵。', '',
              '另对 GR III/IV 的 Standard、Positive Film、Negative Film 计算了静态 CCM＋Gamma 部分诊断，显式设 gain8192、flag0、输入曝光1及 D65 中性 WB。这些 RGB 数值不是完整目标 JPEG：MultiAxial、运行时增益、ToneControl、色域/高光及空间处理尚未闭合。Hi-Contrast B&W 的灰度/滤镜/调色路径未闭合，未伪造黑白渲染。GRD IV 只有原生 A/B/type23/type28 输入，缺可追溯原始传感器颜色矩阵，桥接及 JPEG 目标保持 null。', '',
              '下一批应先修好 ISO/ADJ，再以 ISO200、固定日光 WB、固定曝光和约 1/5s 的慢快门复拍，轻微失焦并遮挡拍摄者/相机反射。至少需要真实变化的控件状态，才能估计各控件响应。V 页与新实物场景留作之后的独立验收。', '',
              '复跑只读本地副本：', '', '```sh',
              'python3 -B research/ui_bug_audit/capture_analysis.py --offline', '```', '',
              '重新从卡读取并核对的命令是不加 `--offline`；脚本只以 rb 打开卡上原片，已存在的副本必须匹配哈希才继续。', '']
    path = AUDIT / 'MACBOOK_CAPTURES_REPORT.md'
    path.write_text('\n'.join(lines))


def verify_outputs(data, copied):
    assert len(data['captures']) == 6
    assert sum(len(i['patches']) for i in data['captures']) == 288
    assert set(i['page'] for i in data['captures']) == {'T1', 'T2', 'T3', 'T4'}
    assert all(len(i['patches']) == 48 for i in data['captures'])
    assert all(i['raw']['byte_roundtrip']['all_strip_bytes_repack_exactly'] for i in data['captures'])
    assert all(v['unchanged'] for v in data['numeric_inputs_before_after'].values())
    masks_checked = 0
    saved_mask_jpeg_means_checked = 0
    for item in data['captures']:
        with Image.open(OUT/(item['shot']+'.JPG')) as img:
            img.load()
            image = np.asarray(img.convert('RGB'))
        for patch in item['patches']:
            mask_path = Path(patch['roi_binary_mask']['path'])
            assert digest(mask_path) == patch['roi_binary_mask']['sha256']
            with Image.open(mask_path) as im:
                mask = np.asarray(im) == 255
            assert int(mask.sum()) == patch['pixels_jpeg']
            x0, y0, x1, y1 = patch['roi_jpeg_bbox_xyxy']
            assert mask.shape == (y1-y0, x1-x0)
            saved_mean = image[y0:y1, x0:x1][mask].mean(0)/255
            assert np.max(np.abs(saved_mean - np.array(patch['jpeg_srgb_encoded_mean']))) < 1e-11
            masks_checked += 1
            saved_mask_jpeg_means_checked += 1
    for model in data['measured_gxr_transfer']['models'].values():
        assert all(f['identical_nominal_RGB_overlap_train_test'] == 0
                   for f in model['leave_one_page_out'].values())
    for row in copied['files']:
        assert digest(Path(row['copy'])) == row['copy_sha256']
    outputs = [OUT/'copy_manifest.json', OUT/'measurements.json', OUT/'cross_sensor_bridge.json',
               AUDIT/'MACBOOK_CAPTURES_REPORT.md', Path(__file__).resolve(),
               RICOH_DEFINITION_DURABLE, OUT/'provenance/Ricoh_definition.json',
               OUT/'provenance/gr3_bridge_dng_tags.json', OUT/'provenance/gr4_bridge_dng_tags.json']
    outputs += sorted(OUT.glob('R805*_roi_overlay.jpg'))
    checks = {'copy_files': 12, 'pairs_decoded': 6, 'patch_pairs': 288,
              'source_before_after_copy_SHA256_match': True,
              'copied_files_SHA256_match_after_analysis': True,
              'all_RAW_bytes_repack_identically': True,
              'HTML_and_JSON_chart_identical': True,
              'paired_metadata_equal': True,
              'persisted_ROI_binary_masks_verified': masks_checked,
              'JPEG_means_remeasured_from_saved_binary_masks': saved_mask_jpeg_means_checked,
              'all_model_colour_holdout_train_test_intersections_zero': True,
              'numeric_input_hashes_before_after_unchanged': True,
              'WB_ISO_definition_persisted_with_SHA256': True,
              'GR_III_GR_IV_bridge_matrices_recomputed': True,
              'complete_GR_reference_or_16_recipe_calibration_pass': False}
    save(AUDIT/'capture_verification.json', {
        'integrity_status': 'PASS', 'calibration_status': 'PARTIAL_NOT_ACCEPTED',
        'checks': checks,
        'source_access': 'Only listing/stat and rb file opens; no card writes/deletes/eject operations',
        'write_scope': [str(OUT), str(AUDIT/'MACBOOK_CAPTURES_REPORT.md'),
                        str(AUDIT/'capture_verification.json'), str(Path(__file__).resolve())],
        'outputs': {str(p): {'sha256': digest(p), 'bytes': p.stat().st_size} for p in outputs},
        'blockers': ['ISO800 and Auto WB instead of fixed ISO200/daylight',
                     '1/100..1/250s shutter, reflection and spatial periodic structure',
                     'single Setting1 midpoint state, no measured 16-recipe response',
                     'no V-page/physical-scene held-out captures',
                     'native GR III/IV full pixel pipelines not closed; GR IV auxiliary ColorMatrix provenance',
                     'GRD IV native sensor bridge unavailable'],
    })


if __name__ == '__main__':
    main()
