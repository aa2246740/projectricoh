#!/usr/bin/env python3
"""Why does the 33^3 V-Log cube interpolate worse than the sRGB one? Same DNG pixels, several log inputs the
exporter supports, 33^3 vs 65^3; LUT (tetrahedral) vs the runtime, dE00 in sRGB, plus where the error sits.
Writes local/log_probe.json."""
import json
import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from bakelib import LOCAL, WORK, apply_lut, as_image, dE, dump, lab, r3, read_cube, spk, stats
from spaces import decode, encode, matrix, GAMUT

FILMS = ['fujifilm_velvia_100', 'kodak_ektachrome_100', 'kodak_portra_400', 'kodak_vision3_500t']
PROBES = {'vlog-33': ('vlog', 'vlog'), 'vlog-65': ('vlog', 'vlog'), 'applelog-33': ('applelog', 'applelog'),
          'flog2-33': ('flog2', 'flog2'), 'slog3cine-33': ('slog3cine', 'slog3')}


def main():
    inputs = json.loads((LOCAL / 'inputs.json').read_text())
    v = np.load(WORK / 'scene.npy').reshape(-1, 3)[:inputs['scene_pixels']]
    xyz = decode(v, 'vlog') @ matrix('vgamut').T
    res = {}
    for film in FILMS:
        res[film] = {}
        for key, (slug, ours) in PROBES.items():
            variant = f'probe-{slug}-{key.split("-")[1]}'
            codes = np.clip(encode(xyz @ np.linalg.inv(matrix(GAMUT[ours])).T, ours), 0, 1)
            src = WORK / f'probe_{key}.npy'
            np.save(src, as_image(codes))
            exp = spk('export', film, WORK / 'probe_bundles', variant)
            bdir = Path(exp['bundles'][variant]['dir'])
            T = read_cube(next(bdir.glob('*.cube')))[2]
            dst = WORK / f'probe_out_{key}.npy'
            spk('direct', film, variant, src, dst, 'pointwise')
            eng = np.clip(np.load(dst).reshape(-1, 3)[:len(codes)], 0, 1)
            e = dE(eng, apply_lut(T, codes))
            L = lab(eng)[:, 0]
            C = np.hypot(*lab(eng)[:, 1:].T)
            bins = {f'L{a}-{b}': r3(stats(e[(L >= a) & (L < b)])) for a, b in ((0, 25), (25, 50), (50, 75), (75, 101))
                    if ((L >= a) & (L < b)).sum() > 100}
            hiC = C > np.percentile(C, 90)
            res[film][key] = {'all': r3(stats(e)), 'by_output_L': bins, 'top10pct_chroma': r3(stats(e[hiC])),
                              'code_p1_p50_p99': [round(float(np.percentile(codes, q)), 3) for q in (1, 50, 99)]}
            print(film, key, res[film][key]['all']['median'], res[film][key]['all']['p99'], res[film][key]['all']['max'],
                  {k: b['p99'] for k, b in bins.items()}, 'hiC p99', res[film][key]['top10pct_chroma']['p99'], flush=True)
            shutil.rmtree(bdir)
            dst.unlink()
            src.unlink()
    dump(LOCAL / 'log_probe.json', res)


if __name__ == '__main__':
    main()
