#!/usr/bin/env python3
"""Bake every fotufilm stock's pointwise colour into 33^3 .cube files and check them on real photos.

Per stock:
  1. one render of an identity 33^3 grid followed by a shuffled copy of it, as a 4-row strip
     (17969x4 with two padding pixels). A 4-pixel short edge puts every spatial radius under the engine's 0.15 px cut-off,
     and identical outputs for the two copies prove the render is pointwise;
  2. .cube from the grid: sRGB in -> sRGB out (fotufilm's Display P3 output converted, clipped),
     plus sRGB in -> Display P3 out (fotufilm's own file values);
  3. the six validation photos (1/8 size) as 4-row strips (pointwise render of the same pixels)
     -> LUT vs engine;
  4. two photos (1/4 size) at full frame (spatial stages the CLI cannot switch off stay on) -> engine vs strip,
     raw and after an 8x8 low-pass, to separate edge/sharpness effects from colour.
The CLI runs only inside the sandbox (common.fotufilm). Writes: research/fotufilm_bake/local and Scratch.
"""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from common import (CAPTURES, CUBES, LOCAL, N, P3_TO_SRGB, W, WORK, apply_lut, de00, decode_image,
                    dump, encode_png, eotf, fotufilm, grid_codes, lab, oetf, p3_to_srgb_codes, sha,
                    stats, write_cube)

PHOTOS = ['R8051530', 'R8051554', 'R8051570', 'R8051586', 'R8051594', 'R8051610']
FULL = ['R8051530', 'R8051586']
SKIP = {'example-monochrome-100', 'example-negative-400', 'example-reversal-64'}
FLAGS = ['--grain', '0', '--halation', '0', '--local-tone', '0',
         '--digital-reference', 'reference-exposure', '--depth', '16']
STRIP_ROWS = 4
STRIP_MAX = 65536 * 4
SRC = W / 'src'


def commit():
    head = (SRC / '.git/HEAD').read_text().strip()
    if head.startswith('ref:'):
        return (SRC / '.git' / head.split()[1]).read_text().strip()
    return head


def stock_meta(sid):
    d = json.loads((SRC / f'Sources/FotufilmCore/Stocks/{sid}.json').read_text())
    rev, refl = bool(d.get('isReversal')), bool(d.get('isReflectionPrint'))
    # PrintPaper.default(for:): reversal stocks resolve to screen (first choice), others to their
    # native medium or ektacolor-edge.
    medium = 'screen' if rev else (d.get('nativePrintMedium') or 'ektacolor-edge')
    return {'id': sid, 'name': d.get('name'), 'subtitle': d.get('subtitle'), 'reversal': rev,
            'monochrome': bool(d.get('isMonochrome')), 'reflection_print': refl,
            'medium': medium, 'format': d.get('nativeFormatID')}


def load_photos(tmp='in.u16'):
    small, full = {}, {}
    for name in PHOTOS:
        im, _ = decode_image(CAPTURES / f'{name}.JPG', WORK / tmp)
        for f, dst in ((8, small), (4, full)):
            if dst is full and name not in FULL:
                continue
            h, w, _ = im.shape
            dst[name] = np.rint(im[:h // f * f, :w // f * f].reshape(h // f, f, w // f, f, 3).mean((1, 3))
                                * 255) / 255
    (WORK / tmp).unlink()
    return small, full


def strips(flat, prefix):
    """Write pixels as 4-row strips of at most STRIP_MAX pixels; return the file names."""
    names = []
    for i in range(0, len(flat), STRIP_MAX):
        chunk = flat[i:i + STRIP_MAX]
        pad = (-len(chunk)) % STRIP_ROWS
        chunk = np.concatenate([chunk, np.zeros((pad, 3))])
        names.append(f'{prefix}{len(names)}.png')
        encode_png(chunk.reshape(STRIP_ROWS, -1, 3), WORK / names[-1])
    return names


def prepare_inputs():
    """Grid + shuffled grid, photo strips and full frames (8-bit sRGB codes)."""
    WORK.mkdir(parents=True, exist_ok=True)
    g = grid_codes()
    perm = np.random.default_rng(20261101).permutation(len(g))
    both = np.concatenate([g, g[perm], np.zeros(((-2 * len(g)) % STRIP_ROWS, 3))])
    encode_png(both.reshape(STRIP_ROWS, -1, 3), WORK / 'grid2.png')
    small, full = load_photos()
    info = {n: {'source': f'captures/street-g137-20261031/jpg/{n}.JPG', 'sha256': sha(CAPTURES / f'{n}.JPG'),
                'pointwise_size': list(small[n].shape[:2][::-1]),
                'full_frame_size': list(full[n].shape[:2][::-1]) if n in full else None} for n in PHOTOS}
    for n in FULL:
        encode_png(full[n], WORK / f'full_{n}.png')
    sets = {'small': strips(np.concatenate([small[n].reshape(-1, 3) for n in PHOTOS]), 'ps'),
            'full': strips(np.concatenate([full[n].reshape(-1, 3) for n in FULL]), 'pf')}
    return info, sets


def render_strips(names, sid, n):
    out = []
    for name in names:
        fotufilm([WORK / name, WORK / f'o_{sid}.png', '--stock', sid, *FLAGS])
        o, _ = decode_image(WORK / f'o_{sid}.png', WORK / f'o_{sid}.u16')
        out.append(o.reshape(-1, 3))
    return np.concatenate(out)[:n]


def lowpass(codes_hw3, k=8):
    lin = eotf(codes_hw3)
    h, w, _ = lin.shape
    lin = lin[:h // k * k, :w // k * k].reshape(h // k, k, w // k, k, 3).mean((1, 3))
    return oetf(lin)


def r3(d):
    return {k: round(v, 3) for k, v in d.items()}


def bake(meta, perm, small, full, sets, meta_common):
    sid = meta['id']
    t0 = time.time()
    fotufilm([WORK / 'grid2.png', WORK / f'g_{sid}.png', '--stock', sid, *FLAGS])
    out, desc = decode_image(WORK / f'g_{sid}.png', WORK / f'g_{sid}.u16')
    assert 'DisplayP3' in desc, desc
    out = out.reshape(-1, 3)
    a, b = out[:N ** 3], out[N ** 3:2 * N ** 3]
    inv = np.empty_like(perm)
    inv[perm] = np.arange(len(perm))
    pointwise_max = float(abs(a - b[inv]).max() * 65535)
    T_p3 = a.reshape(N, N, N, 3)
    T_srgb = p3_to_srgb_codes(T_p3)
    lin_s = eotf(T_p3).reshape(-1, 3) @ P3_TO_SRGB.T
    gamut_share = float(((lin_s < -1e-4) | (lin_s > 1 + 1e-4)).any(1).mean())

    # pointwise engine on the six photos (1/8 size) vs the LUT
    flat = np.concatenate([small[n].reshape(-1, 3) for n in PHOTOS])
    eng_p3 = render_strips(sets['small'], sid, len(flat))
    eng_srgb = p3_to_srgb_codes(eng_p3)
    lut_p3 = apply_lut(T_p3, flat)
    lut_srgb = apply_lut(T_srgb, flat)
    e_srgb = de00(lab(eng_srgb), lab(lut_srgb))
    res = {'srgb_tetra': r3(stats(e_srgb)),
           'srgb_trilinear': r3(stats(de00(lab(eng_srgb), lab(apply_lut(T_srgb, flat, 'trilinear'))))),
           'srgb_tetra_8bit_out': r3(stats(de00(lab(eng_srgb), lab(np.rint(lut_srgb * 255) / 255)))),
           'p3_tetra': r3(stats(de00(lab(eng_p3, 'p3'), lab(lut_p3, 'p3'))))}
    per, off = {}, 0
    for n in PHOTOS:
        k = small[n].shape[0] * small[n].shape[1]
        per[n] = r3(stats(e_srgb[off:off + k]))
        off += k
    res['per_photo_srgb'] = per
    # how much the engine's own output changes from 8-bit input quantisation is zero here: both
    # sides read the same 8-bit codes.
    row = {**meta, 'pointwise_max_u16': pointwise_max, 'grid_out_of_srgb_share': round(gamut_share, 4),
           'pixels': int(len(flat)), 'lut_vs_engine': res,
           'engine_mean_srgb': [round(float(v), 4) for v in eng_srgb.mean(0)]}

    # full-frame renders (1/4 size): spatial stages the CLI cannot switch off stay on
    flat_f = np.concatenate([full[n].reshape(-1, 3) for n in FULL])
    pw_f = p3_to_srgb_codes(render_strips(sets['full'], sid, len(flat_f)))
    ff, off = {}, 0
    for n in FULL:
        h, w, _ = full[n].shape
        fotufilm([WORK / f'full_{n}.png', WORK / f'f_{sid}.png', '--stock', sid, *FLAGS])
        f, _ = decode_image(WORK / f'f_{sid}.png', WORK / f'f_{sid}.u16')
        fs = p3_to_srgb_codes(f.reshape(-1, 3)).reshape(h, w, 3)
        es = pw_f[off:off + h * w].reshape(h, w, 3)
        ls = apply_lut(T_srgb, full[n].reshape(-1, 3)).reshape(h, w, 3)
        off += h * w
        ff[n] = {'lut_vs_pointwise': r3(stats(de00(lab(es), lab(ls)))),
                 'full_vs_pointwise': r3(stats(de00(lab(fs), lab(es)))),
                 'full_vs_lut': r3(stats(de00(lab(fs), lab(ls)))),
                 'lowpass8_full_vs_lut': r3(stats(de00(lab(lowpass(fs)), lab(lowpass(ls)))))}
    row['full_frame'] = ff

    note = [f'fotufilm stock: {meta["name"]} ({sid}); fotufilm-engine {meta_common["tag"]} '
            f'commit {meta_common["commit"]}',
            f'Settings: {" ".join(FLAGS[:-2])}; medium {meta["medium"]} (the stock default); '
            f'native format {meta["format"]}; fixed timing, no Auto Levels; spatial stages at zero radius.',
            'Input: sRGB (IEC 61966-2-1) display-referred code values, full range.',
            'Film profile data (c) MUAStudio, CC BY-SA 4.0. Rendered with Fotufilm (https://fotufilm.com).',
            'This LUT is adapted from the Fotufilm film profile and is shared under CC BY-SA 4.0',
            '(https://creativecommons.org/licenses/by-sa/4.0/). Not endorsed by Fotufilm, MUAStudio',
            'or the film manufacturer.']
    p_s = CUBES / f'fotufilm_{sid}_srgb.cube'
    p_p = CUBES / f'fotufilm_{sid}_p3out.cube'
    write_cube(p_s, T_srgb, f'Fotufilm {meta["name"]} (sRGB to sRGB)',
               note + ['Output: sRGB code values (fotufilm Display P3 output converted; '
                       'out-of-gamut clipped in linear light).'])
    write_cube(p_p, T_p3, f'Fotufilm {meta["name"]} (sRGB to Display P3)',
               note + ['Output: Display P3 code values exactly as fotufilm writes them; '
                       'interpret/tag the result as Display P3.'])
    row['cubes'] = {'srgb': p_s.name, 'srgb_sha256': sha(p_s), 'p3out': p_p.name, 'p3out_sha256': sha(p_p)}
    row['seconds'] = round(time.time() - t0, 1)
    for p in WORK.glob(f'*_{sid}.*'):
        p.unlink()
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only')
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--prepare', action='store_true')
    args = ap.parse_args()
    CUBES.mkdir(parents=True, exist_ok=True)
    meta_common = {'commit': commit(), 'tag': 'v1.14.1'}
    if args.prepare:
        info, sets = prepare_inputs()
        dump(LOCAL / 'inputs.json', {'photos': info, 'sets': sets, 'strip_rows': STRIP_ROWS,
                                     'flags': FLAGS, **meta_common})
        return 0
    stocks = [l.split('\t')[0] for l in (WORK / 'stocks.txt').read_text().splitlines() if l.strip()]
    stocks = [s for s in stocks if s not in SKIP]
    if args.only:
        stocks = args.only.split(',')
    k, m = map(int, args.shard.split('/'))
    stocks = stocks[k::m]
    sets = json.loads((LOCAL / 'inputs.json').read_text())['sets']
    perm = np.random.default_rng(20261101).permutation(N ** 3)
    small, full = load_photos(f'in_{k}.u16')
    out = LOCAL / f'bake_{k}of{m}.json'
    rows = json.loads(out.read_text()) if out.exists() else []
    done = {r['id'] for r in rows if r.get('success')}
    for sid in stocks:
        if sid in done:
            continue
        meta = stock_meta(sid)
        try:
            row = bake(meta, perm, small, full, sets, meta_common)
            row['success'] = True
            e = row['lut_vs_engine']['srgb_tetra']
            print(sid, 'pointwise', row['pointwise_max_u16'], 'LUT dE med', e['median'], 'p99', e['p99'],
                  'max', e['max'], '| full-vs-pointwise med',
                  {n: v['full_vs_pointwise']['median'] for n, v in row['full_frame'].items()},
                  row['seconds'], 's', flush=True)
        except Exception as exc:
            row = {**meta, 'success': False, 'error': str(exc)[-1500:]}
            print('FAILED', sid, exc, flush=True)
        rows = [r for r in rows if r['id'] != sid] + [row]
        dump(out, rows)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
