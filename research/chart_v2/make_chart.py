#!/usr/bin/env python3
"""Deterministic Display P3 camera target; writes only inside research/chart_v2."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import plistlib
import random
import subprocess

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ICC = Path('/System/Library/ColorSync/Profiles/Display P3.icc')
EXPECTED_UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
W, H = 3456, 2234
COLS, ROWS = 12, 10
PW, PH, GAP = 228, 156, 32
X0, Y0 = (W - (COLS * PW + (COLS - 1) * GAP)) // 2, (H - (ROWS * PH + (ROWS - 1) * GAP)) // 2
LIGHTNESS = (18., 38., 58., 78.)
FRACTIONS = (.25, .60, .97)
CODE_LO, CODE_HI = 4, 251
BACKGROUND = (60, 60, 60)
MARKER_SLOTS = {'TL': (0, 0), 'TR': (0, 11), 'BR': (9, 11), 'BL': (9, 0)}
MARKER_CELLS = {'TL': 3, 'TR': 4, 'BR': 6, 'BL': 8}
ANCHOR_SLOTS = ((0, 2), (0, 6), (0, 9), (2, 0), (2, 11), (4, 3),
                (4, 8), (6, 0), (6, 11), (8, 2), (9, 5), (9, 9))
WHITE = np.array([.3127 / .3290, 1., (1. - .3127 - .3290) / .3290])


def matrix(primaries):
    p = np.array([[x / y, 1., (1. - x - y) / y] for x, y in primaries]).T
    return p * np.linalg.solve(p, WHITE)


P3_XYZ = matrix(((.680, .320), (.265, .690), (.150, .060)))
XYZ_P3 = np.linalg.inv(P3_XYZ)
SRGB_XYZ = matrix(((.640, .330), (.300, .600), (.150, .060)))
XYZ_SRGB = np.linalg.inv(SRGB_XYZ)


def guard():
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info.get('MountPoint') == '/Volumes/Workspace', 'Workspace is not mounted'
    assert info.get('VolumeUUID') == EXPECTED_UUID, 'Wrong Workspace UUID'
    assert info.get('FilesystemType') == 'apfs' and info.get('WritableVolume'), 'Need writable APFS'
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/chart_v2'), 'Unexpected task directory'


def output_dir(path):
    path = Path(path).resolve()
    assert path == HERE or HERE in path.parents, 'Output must stay inside chart_v2'
    path.mkdir(parents=True, exist_ok=True)
    return path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def decode(v):
    v = np.asarray(v, dtype=float)
    return np.where(v <= .04045, v / 12.92, ((v + .055) / 1.055) ** 2.4)


def encode(v):
    v = np.asarray(v, dtype=float)
    return np.where(v <= .0031308, 12.92 * v, 1.055 * np.maximum(v, 0.) ** (1. / 2.4) - .055)


def lab_xyz(lab):
    L, a, b = lab
    fy = (L + 16.) / 116.
    f = np.array([fy + a / 500., fy, fy - b / 200.])
    d = 6. / 29.
    return WHITE * np.where(f > d, f ** 3, 3. * d * d * (f - 4. / 29.))


def xyz_lab(xyz):
    t = np.asarray(xyz) / WHITE
    d = 6. / 29.
    f = np.where(t > d ** 3, np.cbrt(t), t / (3. * d * d) + 4. / 29.)
    return np.array([116. * f[1] - 16., 500. * (f[0] - f[1]), 200. * (f[1] - f[2])])


def lch_lab(L, C, h):
    r = math.radians(h)
    return np.array([L, C * math.cos(r), C * math.sin(r)])


def max_chroma(L, h, lo=0., hi=1.):
    """First P3 boundary along this Lab hue ray, relative to D65."""
    a, b = 0., 1.
    def inside(C):
        rgb = XYZ_P3 @ lab_xyz(lch_lab(L, C, h))
        return bool((rgb >= lo - 1e-12).all() and (rgb <= hi + 1e-12).all())
    assert inside(0.)
    while inside(b):
        a, b = b, b * 2.
        assert b <= 1024.
    for _ in range(48):
        c = (a + b) * .5
        if inside(c):
            a = c
        else:
            b = c
    return a


SAFE_LO, SAFE_HI = decode(np.array([CODE_LO, CODE_HI]) / 255.)


def rounded(v):
    return np.round(v, 10).tolist()


def color(name, category, lab, **extra):
    lin = XYZ_P3 @ lab_xyz(lab)
    assert (lin >= SAFE_LO - 1e-9).all() and (lin <= SAFE_HI + 1e-9).all(), name
    code = np.floor(encode(lin) * 255. + .5).astype(int)
    assert code.min() >= CODE_LO and code.max() <= CODE_HI
    actual_lin = decode(code / 255.)
    xyz = P3_XYZ @ actual_lin
    actual_lab = xyz_lab(xyz)
    C = float(np.hypot(lab[1], lab[2]))
    hue = math.degrees(math.atan2(lab[2], lab[1])) % 360. if C > 1e-7 else None
    actual_hue = math.degrees(math.atan2(actual_lab[2], actual_lab[1])) % 360. if C > 1e-7 else None
    # A reference for coverage, NOT the unknown camera's rendered JPEG hue.
    srgb_lin = XYZ_SRGB @ xyz
    srgb = encode(np.clip(srgb_lin, 0., 1.)) * 255.
    cb = float(srgb @ np.array([-.168736, -.331264, .5]))
    cr = float(srgb @ np.array([.5, -.418688, -.081312]))
    ref_h = math.degrees(math.atan2(cr, cb)) % 360. if C > 1e-7 else None
    return {'sample_key': name, 'category': category, 'p3_8bit': code.tolist(),
            'linear_p3': rounded(actual_lin), 'xyz_d65_Y1': rounded(xyz),
            'lab_d65': rounded(actual_lab), 'target_lab_d65': rounded(lab),
            'target_hue_deg': hue, 'target_sector_15deg': int(hue // 15.) if hue is not None else None,
            'quantized_hue_deg': actual_hue,
            'reference_srgb_bt601_hue_deg': ref_h,
            'reference_srgb_bt601_sector_15deg': int(ref_h // 15.) if ref_h is not None else None,
            'outside_srgb': bool((srgb_lin < -1e-7).any() or (srgb_lin > 1. + 1e-7).any()),
            'quantization_delta_e76': round(float(np.linalg.norm(lab - actual_lab)), 7), **extra}


def lch_color(name, category, L, h, fraction):
    full = max_chroma(L, h)
    safe = max_chroma(L, h, SAFE_LO, SAFE_HI)
    return color(name, category, lch_lab(L, safe * fraction, h),
                 cmax_p3=round(full, 8), cmax_p3_with_headroom=round(safe, 8),
                 chroma_fraction_of_safe_max=fraction)


def samples():
    pages = [[] for _ in range(6)]
    combinations = [(L, f) for L in LIGHTNESS for f in FRACTIONS]
    for hi in range(48):
        hue = hi * 7.5 + 3.75
        for page in range(6):
            for j in range(2):
                k = (page * 2 + j + 2 * (hi % 6)) % 12
                L, f = combinations[k]
                pages[page].append(lch_color(f'H{hi:02d}_L{int(L):02d}_C{int(f * 100):02d}',
                                             'hue_grid', L, hue, f))
    extra = []
    for i, L in enumerate(np.linspace(5., 97., 21)):
        extra.append(color(f'GRAY_{i:02d}', 'gray', np.array([L, 0., 0.])))
    # Synthetic warm/cool skin samples; not measurements of a physical card/person.
    for i, L in enumerate((25., 36., 47., 58., 69., 80.)):
        for tone, h, C in (('warm', 54., 22.), ('cool', 37., 15.)):
            extra.append(color(f'SKIN_{i:02d}_{tone}', 'skin', lch_lab(L, C, h)))
    memories = [('sky_light', 78., 255., .35), ('sky_blue', 58., 265., .65),
                ('sky_deep', 38., 275., .75), ('foliage', 38., 135., .55),
                ('grass', 58., 125., .65), ('leaf_light', 78., 115., .55),
                ('earth', 38., 65., .40), ('sand', 78., 80., .25),
                ('brick', 48., 40., .60), ('orange', 68., 65., .85),
                ('lemon', 85., 100., .85), ('rose', 58., 10., .70),
                ('violet', 48., 315., .70), ('sea', 58., 215., .70),
                ('cyan', 78., 195., .80)]
    for name, L, h, f in memories:
        extra.append(lch_color('MEM_' + name, 'memory', L, h, f))
    assert len(extra) == 48
    for i, p in enumerate(extra):
        pages[i % 6].append(p)
    anchors = [color('ANCHOR_white', 'anchor', np.array([97., 0., 0.])),
               color('ANCHOR_lightgray', 'anchor', np.array([75., 0., 0.])),
               color('ANCHOR_midgray', 'anchor', np.array([50., 0., 0.])),
               color('ANCHOR_darkgray', 'anchor', np.array([12., 0., 0.]))]
    for name, L, h in [('red', 58., 35.), ('yellow', 78., 100.), ('green', 58., 145.),
                       ('cyan', 58., 205.), ('blue', 38., 290.), ('magenta', 58., 330.),
                       ('orange', 68., 65.), ('foliage', 38., 130.)]:
        anchors.append(lch_color('ANCHOR_' + name, 'anchor', L, h, .90))
    return pages, anchors


def bbox(row, col):
    x, y = X0 + col * (PW + GAP), Y0 + row * (PH + GAP)
    return [x, y, x + PW, y + PH]


def markers():
    out = []
    for corner, (r, c) in MARKER_SLOTS.items():
        x, y, _, _ = bbox(r, c)
        x += (PW - PH) // 2
        n = MARKER_CELLS[corner]
        b, inner = 18, 120
        cell = inner // n
        out.append({'corner': corner, 'bbox_px': [x, y, x + PH, y + PH],
                    'center_px': [x + PH / 2., y + PH / 2.], 'white_border_px': b,
                    'checker_bbox_px': [x + b, y + b, x + b + inner, y + b + inner],
                    'n_cells': n, 'cell_px': cell, 'top_left_cell': 'black',
                    'inner_corners_px': [[x + b + j * cell, y + b + i * cell]
                                         for i in range(1, n) for j in range(1, n)]})
    return out


def rectangle(draw, box, fill):
    x0, y0, x1, y1 = box
    draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=fill)


def paint_markers(draw, marks):
    for m in marks:
        rectangle(draw, m['bbox_px'], (255, 255, 255))
        x, y, _, _ = m['checker_bbox_px']
        s, n = m['cell_px'], m['n_cells']
        for i in range(n):
            for j in range(n):
                rectangle(draw, [x + j * s, y + i * s, x + (j + 1) * s, y + (i + 1) * s],
                          (0, 0, 0) if (i + j) % 2 == 0 else (255, 255, 255))


DIGITS = {'P': ['11110', '10001', '10001', '11110', '10000', '10000', '10000'],
          '/': ['00001', '00001', '00010', '00100', '01000', '10000', '10000'],
          '1': ['00100', '01100', '00100', '00100', '00100', '00100', '01110'],
          '2': ['01110', '10001', '00001', '00010', '00100', '01000', '11111'],
          '3': ['11110', '00001', '00001', '01110', '00001', '00001', '11110'],
          '4': ['00010', '00110', '01010', '10010', '11111', '00010', '00010'],
          '5': ['11111', '10000', '10000', '11110', '00001', '00001', '11110'],
          '6': ['01110', '10000', '10000', '11110', '10001', '10001', '01110']}


def paint_label(draw, page):
    text, s = f'P{page}/6', 8
    x0, y0 = (W - (len(text) * 6 - 1) * s) // 2, 112
    for c, ch in enumerate(text):
        for y, row in enumerate(DIGITS[ch]):
            for x, bit in enumerate(row):
                if bit == '1':
                    rectangle(draw, [x0 + (c * 6 + x) * s, y0 + y * s,
                                     x0 + (c * 6 + x + 1) * s, y0 + (y + 1) * s], (200, 200, 200))


def hamming(page):
    d0, d1, d2, d3 = [(page >> k) & 1 for k in range(4)]
    bits = [d0 ^ d1 ^ d3, d0 ^ d2 ^ d3, d0, d1 ^ d2 ^ d3, d1, d2, d3]
    return bits + [sum(bits) % 2]


def paint_page_code(draw, page):
    bits = [1, 1, 0, 1] + hamming(page)
    size, x0, y0 = 32, (W - 12 * 32) // 2, 2070
    cells = []
    for r in range(2):
        for j, bit in enumerate(bits):
            val = bit if r == 0 else 1 - bit
            box = [x0 + j * size, y0 + r * size, x0 + (j + 1) * size, y0 + (r + 1) * size]
            rectangle(draw, box, (180, 180, 180) if val else (80, 80, 80))
            cells.append({'bbox_px': box, 'bit': val})
    return {'encoding': 'sync 1101 + extended Hamming(8,4), LSB-first page nibble; second row complement',
            'page_number': page, 'codeword': bits, 'low_code': 80, 'high_code': 180,
            'bbox_px': [x0, y0, x0 + 12 * size, y0 + 2 * size], 'cells': cells}


def generate(out):
    out = output_dir(out)
    page_dir = output_dir(out / 'pages')
    profile = ICC.read_bytes()
    sets, anchors = samples()
    marks = markers()
    metadata = {'schema': 'ricoh.chart_v2.v1', 'canvas_px': [W, H],
                'colorimetry': {'encoding': 'Display P3 RGB8; sRGB piecewise transfer function',
                               'primaries_xy': [[.680, .320], [.265, .690], [.150, .060]],
                               'whitepoint': 'D65; CIE 1976 Lab relative to D65, NOT ICC PCS D50',
                               'white_xy': [.3127, .3290], 'white_xyz_Y1': rounded(WHITE),
                               'linear_p3_to_xyz_d65': rounded(P3_XYZ),
                               'channel_headroom_inclusive': [CODE_LO, CODE_HI],
                               'icc_path': str(ICC), 'icc_sha256': digest(profile)},
                'sampling': {'hue_step_deg': 7.5, 'hue_offset_deg': 3.75, 'lightness': list(LIGHTNESS),
                             'chroma_fractions': list(FRACTIONS), 'gray_levels': 21,
                             'sector_convention': 'floor(hue/15), zero-based; target sectors are Lab hue; reference BT.601 uses clipped nominal sRGB; actual camera sectors unknown'},
                'layout': {'rows': ROWS, 'cols': COLS, 'patch_size_px': [PW, PH], 'gap_px': GAP,
                           'origin_px': [X0, Y0], 'background_p3_8bit': list(BACKGROUND),
                           'pixel_boxes': 'half-open [x0,y0,x1,y1], top-left origin',
                           'roi': 'central 40% of each dimension, 16% of area; exclude text/markers'},
                'markers': marks, 'pages': [], 'patches': []}
    white = color('WHITE_PAGE', 'white_page', np.array([97., 0., 0.]))
    white.update({'id': 0, 'page': 0, 'page_patch_number': 1, 'page_file': 'pages/00_white.png',
                  'bbox_px': [0, 0, W, H], 'roi_bbox_px': [W * .3, H * .3, W * .7, H * .7]})
    Image.new('RGB', (W, H), tuple(white['p3_8bit'])).save(page_dir / '00_white.png', icc_profile=profile, compress_level=9)
    metadata['patches'].append(white)
    metadata['pages'].append({'page': 0, 'file': 'pages/00_white.png', 'purpose': 'manual WB and exposure',
                              'patch_count': 1, 'markers': [], 'page_code': None})
    pid = 0
    free = [(r, c) for r in range(ROWS) for c in range(COLS) if (r, c) not in MARKER_SLOTS.values()]
    for page, base in enumerate(sets, 1):
        assert len(base) == 104
        ordered = list(base)
        random.Random(20261023 + page).shuffle(ordered)
        anchor_at = {ANCHOR_SLOTS[(i + 5 * (page - 1)) % 12]: dict(a) for i, a in enumerate(anchors)}
        im = Image.new('RGB', (W, H), BACKGROUND)
        draw = ImageDraw.Draw(im)
        paint_markers(draw, marks)
        paint_label(draw, page)
        page_code = paint_page_code(draw, page)
        it = iter(ordered)
        for number, slot in enumerate(free, 1):
            p = anchor_at[slot] if slot in anchor_at else next(it)
            pid += 1
            box = bbox(*slot)
            x, y, xx, yy = box
            p.update({'id': pid, 'page': page, 'page_patch_number': number,
                      'page_file': f'pages/{page:02d}_chart.png', 'row': slot[0], 'col': slot[1],
                      'bbox_px': box, 'center_px': [(x + xx) / 2., (y + yy) / 2.],
                      'roi_bbox_px': [x + .3 * PW, y + .3 * PH, xx - .3 * PW, yy - .3 * PH]})
            rectangle(draw, box, tuple(p['p3_8bit']))
            metadata['patches'].append(p)
        im.save(page_dir / f'{page:02d}_chart.png', icc_profile=profile, compress_level=9)
        metadata['pages'].append({'page': page, 'file': f'pages/{page:02d}_chart.png',
                                  'patch_count': 116, 'markers': marks, 'page_code': page_code})
    metadata['counts'] = {'chart_pages': 6, 'white_pages': 1, 'chart_patch_instances': pid,
                          'hue_grid': 576, 'gray': 21, 'skin': 12, 'memory': 15,
                          'anchor_instances': 72, 'distinct_non_anchor_samples': 624}
    assert pid == 696
    write_json(out / 'patches.json', metadata)
    print(json.dumps({'out': str(out), 'pages': 7, 'chart_patches': pid}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=HERE)
    args = parser.parse_args()
    guard()
    generate(args.out)


if __name__ == '__main__':
    main()
