#!/usr/bin/env python3
"""Decode primary-author dtstyle data and measure the supplied GR III color chart."""
import base64
import hashlib
import json
from pathlib import Path
import runpy
import struct
import xml.etree.ElementTree as ET
import zlib

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REF = HERE / 'references'
lab = runpy.run_path(str(HERE / 'analyze_capture.py'))['lab']
COLORS = ['orange', 'green', 'blue', 'red', 'magenta']
CENTERS = np.array([65, 145, 280, 25, 335])


def describe_color_transform(source, target):
    cs = np.linalg.norm(source[:, 1:], axis=1)
    ct = np.linalg.norm(target[:, 1:], axis=1)
    hs = np.degrees(np.arctan2(source[:, 2], source[:, 1])) % 360
    ht = np.degrees(np.arctan2(target[:, 2], target[:, 1])) % 360
    # Analyst-defined grouping in Lab hue space. This does NOT establish the
    # camera's 24 sector angles or equate Lab C* to ISP coefficient magnitude.
    distance = np.abs((hs[:, None] - CENTERS[None, :] + 180) % 360 - 180)
    nearest = distance.argmin(axis=1)
    records = []
    for i, color in enumerate(COLORS):
        include = (cs > 15) & (source[:, 0] <= 100) & (source[:, 0] >= 0) & (nearest == i)
        ids = np.flatnonzero(include)
        ratio = ct[include] / cs[include]
        shifts = (ht[include] - hs[include] + 180) % 360 - 180
        records.append({'color': color, 'patch_indices': ids.tolist(), 'n': int(include.sum()),
                        'median_chroma_ratio': float(np.median(ratio)) if len(ratio) else None,
                        'observed_ratio_min_max': [float(ratio.min()), float(ratio.max())] if len(ratio) else None,
                        'median_hue_shift_degrees': float(np.median(shifts)) if len(shifts) else None})
    return records


def decode_style(path):
    result = {'name': ET.parse(path).findtext('.//info/name'), 'file': str(path.relative_to(HERE)),
              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    for plugin in ET.parse(path).findall('.//plugin'):
        encoded = plugin.findtext('op_params')
        assert encoded.startswith('gz')
        blob = zlib.decompress(base64.b64decode(encoded[4:]))
        operation, version = plugin.findtext('operation'), int(plugin.findtext('module'))
        if operation == 'colorchecker':
            assert version == 2 and len(blob) == 1180
            values = np.frombuffer(blob[:1176], dtype='<f4').astype(float).reshape(6, 49)
            n = struct.unpack_from('<i', blob, 1176)[0]
            assert 1 <= n <= 49
            source, target = values[:3, :n].T, values[3:, :n].T
            result['colorchecker'] = {'module_version': version, 'params_bytes': len(blob), 'patches': n,
                                      'source_Lab': source.tolist(), 'target_Lab': target.tolist(),
                                      'synthetic_source_L_above_100': np.flatnonzero(source[:, 0] > 100).tolist(),
                                      'groups': describe_color_transform(source, target),
                                      'layout_source': 'colorchecker-darktable-4.8.0.c:160-169'}
        elif operation == 'tonecurve':
            assert version == 4 and len(blob) == 516
            a = np.frombuffer(blob[:480], dtype='<f4').astype(float).reshape(3, 20, 2)
            ints = struct.unpack_from('<9i', blob, 480)
            result['tonecurve'] = {'module_version': version, 'params_bytes': len(blob),
                                   'nodes': [a[i, :ints[i]].tolist() for i in range(3)],
                                   'node_counts': list(ints[:3]), 'interpolator_ids': list(ints[3:6]),
                                   'autoscale': ints[6], 'preset': ints[7], 'unbound_ab': ints[8],
                                   'layout_source': 'tonecurve-darktable-4.8.0.c:281-289',
                                   'domain': 'author darktable pipeline after Sigmoid contrast 1.5, skew 0, per-channel, preserve hue 50%; not RAW or a standalone sRGB LUT'}
        else:
            raise ValueError(f'Unexpected module: {operation}')
    return result


def main():
    styles = {p.stem: decode_style(p) for p in sorted(REF.glob('*.dtstyle'))}
    shots, patches = {}, {}
    # Manually inspected centers, recorded in full-resolution image coordinates.
    # Bilinear interpolation follows the four corners of the chart patch grid.
    corners = np.array([[1674, 1371], [4118, 1403], [1667, 2888], [4137, 2856]])
    rois = []
    for row in range(4):
        v = row / 3
        for col in range(6):
            u = col / 5
            x, y = (1 - v) * ((1 - u) * corners[0] + u * corners[1]) + v * ((1 - u) * corners[2] + u * corners[3])
            x, y = int(round(x)), int(round(y))
            rois.append({'label': 'DCBA'[row] + str(6 - col), 'row': row, 'col': col,
                         'box_xyxy': [x - 90, y - 90, x + 90, y + 90]})
    for mode in ['standard', 'positive', 'negative']:
        p = REF / f'reference_ricoh_{mode}.JPG'
        im = Image.open(p)
        e = im.getexif()
        ee = e.get_ifd(34665)
        assert im.size == (6000, 4000) and e.get(274) == 1
        assert 'RICOH GR III' in e.get(272)
        assert ee[40961] == 1
        if mode == 'standard':
            thumbnail = im.copy()
            thumbnail.thumbnail((950, 650))
            thumbnail.save(HERE / 'reference_chart_thumbnail.jpg')
        a = np.asarray(im, dtype=float) / 255
        values = []
        for roi in rois:
            x0, y0, x1, y1 = roi['box_xyxy']
            data = a[y0:y1, x0:x1]
            values.append({'label': roi['label'], 'rgb_mean': data.mean(axis=(0, 1)).tolist(),
                           'rgb_std': data.std(axis=(0, 1)).tolist(),
                           'clipped_pixel_fraction': float(np.mean((data <= 0).any(axis=2) | (data >= 1).any(axis=2)))})
        patches[mode] = values
        shots[mode] = {'file': str(p.relative_to(HERE)), 'camera': e.get(272).strip(), 'size': list(im.size),
                       'date': ee[36867], 'iso': ee[34855], 'exposure': float(ee[33434]),
                       'aperture': float(ee[33437]), 'color_space_exif': ee[40961],
                       'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    assert len({s['date'] for s in shots.values()}) == 1
    assert len({(s['iso'], s['exposure'], s['aperture']) for s in shots.values()}) == 1
    standard = np.array([p['rgb_mean'] for p in patches['standard']])
    mappings = {}
    luma = np.array([0.2126, 0.7152, 0.0722])
    for mode in ['positive', 'negative']:
        target = np.array([p['rgb_mean'] for p in patches[mode]])
        order = np.argsort(standard[:6] @ luma)
        mappings['ricoh_gr3_' + mode] = {
            'source_kind': 'measured_same_chart_GR_III_Standard_to_' + mode,
            'reference_camera': 'RICOH GR III (EXIF); firmware and mode slider settings unspecified',
            'tone_input_encoded_luma': (standard[:6] @ luma)[order].tolist(),
            'tone_output_encoded_luma': (target[:6] @ luma)[order].tolist(),
            'groups': describe_color_transform(lab(standard), lab(target)),
            'clipping_max_over_patch_rois': max(p['clipped_pixel_fraction'] for p in patches[mode]),
            'limits': ['one author chart under one light', 'author mode labels, no complete camera settings dump',
                       'matched size/time/exposure and shared chart geometry; raw identity not independently proved',
                       'relative rendering, not absolute reflectance or GXR calibration']}
    for key in ['fuji_classic_neg', 'fuji_nostalgic_neg', 'fuji_classic_chrome']:
        style = styles[key]
        nodes = np.array(style['tonecurve']['nodes'][0])
        mappings[key] = {'source_kind': 'decoded_author_darktable_chart_fit',
                         'reference_camera': None, 'reference_firmware': None,
                         'tone_input_normalized': nodes[:, 0].tolist(), 'tone_output_normalized': nodes[:, 1].tolist(),
                         'groups': style['colorchecker']['groups'], 'style': style['file'],
                         'limits': ['style approximation, not official algorithm', 'camera model/firmware not identified for these three styles',
                                    'post-Sigmoid working RGB tone domain is not GXR sensor or JPEG domain',
                                    'node extraction only; darktable runtime and module interpolation not executed']}
    result = {'schema': 'gxr-independent-reference-evidence-v1',
              'repository': 'https://github.com/bastibe/Darktable-Film-Simulation-Panel',
              'commit': 'd6effd55cf37ce208c24cf8d072ac14028ca289b', 'styles': styles,
              'reference_shots': shots, 'chart_roi_method': 'manual four-corner center grid, central 180x180 px per patch',
              'chart_patch_center_corners_xy': corners.tolist(), 'chart_rois': rois, 'chart_samples': patches,
              'relative_mappings': mappings, 'gxr_brand_match_measured': False,
              'license': 'Author dedicates code to public domain; source photographs retain attribution to author; research inputs, no product redistribution claim.'}
    (HERE / 'reference_analysis.json').write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    swatches = Image.new('RGB', (720, 24 * 24 + 34), 'white')
    draw = ImageDraw.Draw(swatches)
    for i, mode in enumerate(['standard', 'positive', 'negative']):
        draw.text((i * 240 + 45, 10), 'GR III ' + mode, fill='black')
        for j, p in enumerate(patches[mode]):
            color = tuple(int(round(x * 255)) for x in p['rgb_mean'])
            draw.rectangle((i * 240 + 42, j * 24 + 34, (i + 1) * 240 - 12, j * 24 + 56), fill=color)
            draw.text((i * 240 + 8, j * 24 + 39), p['label'], fill='black')
    swatches.save(HERE / 'reference_patch_comparison.png')
    print(json.dumps({'styles_decoded': len(styles), 'chart_camera': shots['standard']['camera'],
                      'numeric_target_references': list(mappings)}))


if __name__ == '__main__':
    main()
