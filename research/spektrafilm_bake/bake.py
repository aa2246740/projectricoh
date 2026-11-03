#!/usr/bin/env python3
"""Export every spektrafilm film as 33^3 .cube files with spektrafilm's own exporter and check them against
spektrafilm's runtime rendering the same pixels directly.

Per film and variant (srgb / srgbmid / vlog, see render.py):
  1. export with the exporter (sandboxed render.py export);
  2. the runtime renders an identity 33^3 grid followed by a shuffled copy in one image (pointwise mode):
     identical outputs for the two copies prove the render is per pixel; the first copy against the cube
     rows shows exporter == runtime at the nodes;
  3. the runtime renders real pixels (six GXR JPEGs at 1/8 for sRGB input; six GXR DNGs as V-Log codes for
     V-Log input) -> LUT (tetrahedral) vs runtime, dE00 in sRGB;
  4. srgb only: two JPEGs at 1/4 size rendered with the runtime's default auto exposure, and with the author's
     default spatial effects (grain and auto exposure off) -> vs LUT, raw and after an 8x8 low-pass.
Writes: research/spektrafilm_bake/local and Scratch only.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import bakelib
from bakelib import (RES, CUBES, DNG, DNGS, FULL, JPG, LOCAL, N, PHOTOS, VARIANTS, WORK, apply_lut, as_image, lab,
                    check_paths, dE, dng_scene_xyz, dump, eotf, grid_codes, load_photos, oetf, r3, read_cube,
                    sha, spk, stats, xyz_to_vlog)

COMMIT = '500bc429b7e93450ef228305c319dc03d8e185d1'
TAG = 'v0.3.3'
SEED = 20261101
INPUT_TEXT = {'vlog65': 'Panasonic V-Log code values, V-Gamut primaries, full range, scene-referred',
              'srgb': 'sRGB code values (IEC 61966-2-1 transfer, Rec.709 primaries, D65), full range',
              'srgbmid': 'sRGB code values (IEC 61966-2-1 transfer, Rec.709 primaries, D65), full range',
              'vlog': 'Panasonic V-Log code values, V-Gamut primaries, full range, scene-referred'}


def prepare():
    WORK.mkdir(parents=True, exist_ok=True)
    g = grid_codes()
    perm = np.random.default_rng(SEED).permutation(len(g))
    np.save(WORK / 'grid2.npy', np.concatenate([g, g[perm]]).reshape(66, 1089, 3))
    g = grid_codes(65)
    perm = np.random.default_rng(SEED).permutation(len(g))
    np.save(WORK / 'grid2_65.npy', np.concatenate([g, g[perm]]).reshape(650, 845, 3))
    small, full = load_photos()
    flat = np.concatenate([small[n].reshape(-1, 3) for n in PHOTOS])
    np.save(WORK / 'photos.npy', as_image(flat))
    for n in FULL:
        np.save(WORK / f'full_{n}.npy', full[n])
    from camera import Camera
    camera = Camera()
    scene, smeta = [], {}
    for n in DNGS:
        xyz, clipped = dng_scene_xyz(camera, DNG / f'{n}.DNG', 536)
        v = xyz_to_vlog(xyz.reshape(-1, 3))
        scene.append(v)
        smeta[n] = {'source': f'captures/street-g137-20261031/dng/{n}.DNG', 'sha256': sha(DNG / f'{n}.DNG'),
                    'size': list(xyz.shape[:2][::-1]), 'raw_clipped_share': round(float(clipped.mean()), 4),
                    'median_Y': round(float(np.median(xyz[..., 1])), 4),
                    'vlog_code_p1_p50_p99': [round(float(np.percentile(v, q)), 3) for q in (1, 50, 99)]}
    scene = np.concatenate(scene)
    np.save(WORK / 'scene.npy', as_image(scene))
    info = {'photos': {n: {'source': f'captures/street-g137-20261031/jpg/{n}.JPG', 'sha256': sha(JPG / f'{n}.JPG'),
                           'pointwise_size': list(small[n].shape[:2][::-1]),
                           'full_frame_size': list(full[n].shape[:2][::-1]) if n in full else None}
                       for n in PHOTOS},
            'dngs': smeta, 'zero_denominator_tags': sorted(bakelib.ZERO_DENOMINATOR_TAGS), 'photo_pixels': int(len(flat)), 'scene_pixels': int(len(scene)), 'seed': SEED,
            'dng_decode': 'sparse 2x2 CFA means, per-DNG white matrix, fixed 50mm meter anchor (camera.xyz); '
                          'XYZ -> V-Gamut -> V-Log, codes clipped to [0, 1]'}
    dump(LOCAL / 'inputs.json', info)
    return info


def lowpass(codes_hw3, k=8):
    lin = eotf(codes_hw3)
    h, w, _ = lin.shape
    return oetf(lin[:h // k * k, :w // k * k].reshape(h // k, k, w // k, k, 3).mean((1, 3)))


def direct(film, variant, src, mode):
    dst = WORK / f'o_{film}_{variant}_{mode}_{Path(src).stem}.npy'
    meta = spk('direct', film, variant, src, dst, mode)
    out = np.load(dst)
    dst.unlink()
    return out, meta


ATTRIBUTION = [
    'Derived from spektrafilm by Andrea Volpato',
    'https://github.com/andreavolpato/spektrafilm',
    'Licensed CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/)',
    'Modified by the projectricoh GXR project (local, 2026-11-01): this comment block added; LUT rows exactly',
    'as written by the spektrafilm exporter. Changes are listed in CHANGELOG.txt; license text in',
    'SPEKTRAFILM_LICENSE.txt (unchanged) and LICENSE-CC-BY-SA-4.0.txt next to this file.',
    'Not endorsed by Andrea Volpato or by the film manufacturer; film names only identify the simulated stock.']


def header(info, variant, bundle, how):
    film, name = info['film'], info['name']
    snap = next(iter(bundle['params_snapshot'].values()))
    exp = bundle['input_exposure']
    pr = ('none: reversal film scanned directly (io.scan_film = True, as the spektrafilm GUI does for positive stocks)'
          if info['positive'] else f'{bundle["stocks"]["prints"][0]} (the film profile\'s own target_print)')
    lines = [
        f'spektrafilm film simulation LUT: {name} ({film}), print {pr}',
        f'Input: {INPUT_TEXT[variant]}. Output: sRGB code values, full range.',
        f'Exposure: fixed linear gain {exp["gain"]:.6g} on the decoded input (stops_above_midgray '
        f'{exp["stops_above_midgray"]:.6g}); no auto exposure.',
        f'spektrafilm {bundle["provenance"]["spektrafilm_version"]} (tag {TAG}, commit {COMMIT}); '
        f'1-LUT topology, {bundle["resolution"]}^3, lut_mode on (grain, halation, scatter, coupler diffusion, '
        'glare, lens/scanner blur, unsharp mask, auto exposure, scanner white/black correction all off).',
        f'Gamut compression: input {snap["input_gamut_compress"]["algorithm"]} knee {snap["input_gamut_compress"]["knee"]}; '
        f'output {snap["output_gamut_compress"]["algorithm"]} knee {snap["output_gamut_compress"]["knee"]} '
        f'lightness {snap["output_gamut_compress"]["lightness_compression"]}.',
        f'Exported with: {how}',
] + ATTRIBUTION + ['']
    return ['# ' + l if l else '#' for l in lines]


def bake(film, inputs):
    t0 = time.time()
    exp = spk('export', film, WORK / 'bundles')
    info = exp['info']
    row = {**info, 'variants': {}}
    photos = np.load(WORK / 'photos.npy').reshape(-1, 3)[:inputs['photo_pixels']]
    scene = np.load(WORK / 'scene.npy').reshape(-1, 3)[:inputs['scene_pixels']]
    autoexp = {}
    for variant in VARIANTS:
        bdir = Path(exp['bundles'][variant]['dir'])
        cubes = sorted(bdir.glob('*.cube'))
        assert len(cubes) == 1, cubes
        bundle = json.loads((bdir / 'bundle.json').read_text())
        head, body, T = read_cube(cubes[0])
        n3 = RES[variant] ** 3
        perm = np.random.default_rng(SEED).permutation(n3)
        inv = np.empty_like(perm)
        inv[perm] = np.arange(n3)
        gfile = WORK / ('grid2.npy' if RES[variant] == 33 else f'grid2_{RES[variant]}.npy')
        og, meta = direct(film, variant, gfile, 'pointwise')
        og = og.reshape(-1, 3)
        a, b = og[:n3], og[n3:2 * n3]
        v = {'exporter_file_sha256': sha(cubes[0]), 'gain': meta['gain'], 'scan_film': meta['scan_film'],
             'shuffle_max_u16': float(abs(a - b[inv]).max() * 65535),
             'nodes_runtime_vs_cube_max_abs': float(abs(np.clip(a, 0, 1) - T.reshape(-1, 3)).max()),
             'nodes_runtime_range': [float(a.min()), float(a.max())],
             'out_of_unit_share': float(((a < -1e-6) | (a > 1 + 1e-6)).any(1).mean())}
        x = scene if variant.startswith('vlog') else photos
        src = WORK / ('scene.npy' if variant.startswith('vlog') else 'photos.npy')
        eng, _ = direct(film, variant, src, 'pointwise')
        eng = np.clip(eng.reshape(-1, 3)[:len(x)], 0, 1)
        lut = apply_lut(T, x)
        e = dE(eng, lut)
        v['lut_vs_runtime'] = {'tetra': r3(stats(e)), 'trilinear': r3(stats(dE(eng, apply_lut(T, x, 'trilinear')))),
                               'tetra_8bit_out': r3(stats(dE(eng, np.rint(lut * 255) / 255)))}
        names = DNGS if variant.startswith('vlog') else PHOTOS
        k = len(x) // len(names)
        v['per_image'] = {n: r3(stats(e[i * k:(i + 1) * k])) for i, n in enumerate(names)}
        v['runtime_mean_srgb'] = [round(float(c), 4) for c in eng.mean(0)]
        if variant in ('srgb', 'srgbmid'):
            # full frames: the runtime's default auto exposure (scale-invariant, so one render serves both sRGB
            # cubes) and the author's default spatial effects at this variant's fixed gain
            ff = {}
            for n in FULL:
                img = np.load(WORK / f'full_{n}.npy')
                ls = apply_lut(T, img.reshape(-1, 3)).reshape(img.shape)
                d = {'lut_L_median': round(float(np.median(lab(ls)[..., 0])), 2)}
                if variant == 'srgb':
                    autoexp[n], _ = direct(film, variant, WORK / f'full_{n}.npy', 'autoexp')
                    autoexp[n] = np.clip(autoexp[n], 0, 1)
                    d['autoexp_L_median'] = round(float(np.median(lab(autoexp[n])[..., 0])), 2)
                f = autoexp[n]
                d['autoexp'] = {'raw': r3(stats(dE(f, ls))), 'lowpass8': r3(stats(dE(lowpass(f), lowpass(ls))))}
                f, _ = direct(film, variant, WORK / f'full_{n}.npy', 'spatial')
                f = np.clip(f, 0, 1)
                d['spatial'] = {'raw': r3(stats(dE(f, ls))), 'lowpass8': r3(stats(dE(lowpass(f), lowpass(ls))))}
                ff[n] = d
            v['full_frame'] = ff
        # final cube: our header + the exporter's header and rows, rows byte-identical
        out = CUBES / f'spektrafilm_{film}_{variant}.cube'
        check_paths(out)
        out.write_text('\n'.join(header(info, variant, bundle, exp['bundles'][variant]['how']) + head + body) + '\n')
        assert read_cube(out)[1] == body
        v['cube'] = out.name
        v['cube_sha256'] = sha(out)
        dump(LOCAL / 'bundles' / f'{film}_{variant}.json', bundle)
        if not (CUBES / 'SPEKTRAFILM_LICENSE.txt').exists():
            shutil.copyfile(bdir / 'SPEKTRAFILM_LICENSE.txt', CUBES / 'SPEKTRAFILM_LICENSE.txt')
        row['variants'][variant] = v
        shutil.rmtree(bdir)
    row['seconds'] = round(time.time() - t0, 1)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prepare', action='store_true')
    ap.add_argument('--only')
    ap.add_argument('--shard', default='0/1')
    args = ap.parse_args()
    CUBES.mkdir(parents=True, exist_ok=True)
    if args.prepare:
        print(json.dumps(prepare(), indent=1)[:1500])
        return 0
    inputs = json.loads((LOCAL / 'inputs.json').read_text())
    films = [f['film'] for f in json.loads((LOCAL / 'info.json').read_text())['films']]
    if args.only:
        films = args.only.split(',')
    k, m = map(int, args.shard.split('/'))
    films = films[k::m]
    out = LOCAL / f'bake_{k}of{m}.json'
    rows = json.loads(out.read_text()) if out.exists() else []
    done = {r['film'] for r in rows if r.get('success')}
    for film in films:
        if film in done:
            continue
        try:
            row = bake(film, inputs)
            row['success'] = True
            print(film, {v: (x['shuffle_max_u16'], round(x['nodes_runtime_vs_cube_max_abs'], 7),
                             x['lut_vs_runtime']['tetra']['median'], x['lut_vs_runtime']['tetra']['p99'],
                             x['lut_vs_runtime']['tetra']['max']) for v, x in row['variants'].items()},
                  row['seconds'], 's', flush=True)
        except Exception as exc:
            row = {'film': film, 'success': False, 'error': str(exc)[-1500:]}
            print('FAILED', film, exc, flush=True)
        rows = [r for r in rows if r['film'] != film] + [row]
        dump(out, rows)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
