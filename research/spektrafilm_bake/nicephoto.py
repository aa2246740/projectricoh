#!/usr/bin/env python3
"""Our exports vs the 8 third-party NicePhoto re-bakes (Hugging Face Norton0924/OpenSourceLuts, .lut16, read-only
under research/film_engines_eval/local/downloads). Their CHANGELOG: spektrafilm-lut 0.3.4, sRGB in/out, 33^3,
default print, then a linear-light gain before the LUT so sRGB mid-grey 0.466 maps to 0.466, resampled to 16 bit.

On the six validation JPEGs (1/8 size) and on the neutral ramp, dE00 between NicePhoto and:
  srgb      our author-default export (gain 2.88 baked in);
  srgbmid   our gain-1.0 export (equivalent to a 1/2.88 pre-gain on srgb);
  srgb+g    our srgb cube behind the pre-gain g that best matches NicePhoto's neutral ramp (fitted per film):
            what is left is version 0.3.3 vs 0.3.4 plus their resampling.
Writes local/nicephoto.json."""
import json
import struct
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from bakelib import CUBES, LOCAL, PHOTOS, ROOT, apply_lut, dE, dump, eotf, lab, load_photos, oetf, r3, read_cube_table, sha, stats

HF = ROOT / 'research/film_engines_eval/local/downloads/hf-opensourceluts'
MAP = {'P09': 'kodak_portra_400', 'P06': 'kodak_portra_160', 'D17': 'kodak_gold_200', 'D18': 'kodak_ultramax_400',
       'P05': 'kodak_ektar_100', 'P03': 'fujifilm_pro_400h', 'D12': 'fujifilm_xtra_400', 'C13': 'kodak_vision3_500t'}


def read_lut16(path):
    raw = Path(path).read_bytes()
    assert raw[:4] == b'LUT1'
    n = struct.unpack('<I', raw[4:8])[0]
    assert len(raw) == 8 + n ** 3 * 6
    return np.frombuffer(raw[8:], '<u2').astype(float).reshape(n, n, n, 3) / 65535


def pregain(T, x, g):
    return apply_lut(T, oetf(np.clip(eotf(x) * g, 0, 1)))


def main():
    small, _ = load_photos()
    x = np.concatenate([small[n].reshape(-1, 3) for n in PHOTOS])
    ramp = np.repeat(np.linspace(0.02, 0.98, 97)[:, None], 3, 1)
    gains = np.exp(np.linspace(np.log(0.15), np.log(1.2), 400))
    out = {}
    for code, film in MAP.items():
        p = HF / f'olut_{code}_sk.lut16'
        NP = read_lut16(p)
        S = read_cube_table(CUBES / f'spektrafilm_{film}_srgb.cube')
        M = read_cube_table(CUBES / f'spektrafilm_{film}_srgbmid.cube')
        npx, npr = apply_lut(NP, x), apply_lut(NP, ramp)
        err = [float(np.median(dE(npr, pregain(S, ramp, g)))) for g in gains]
        g = float(gains[int(np.argmin(err))])
        mid = np.array([[0.466, 0.466, 0.466]])
        row = {'film': film, 'file': p.name, 'sha256': sha(p), 'fitted_pregain': round(g, 4),
               'fitted_pregain_ev': round(float(np.log2(g)), 3),
               'midgray_0466_out': {'nicephoto': round(float(apply_lut(NP, mid)[0, 1]), 4),
                                    'srgb': round(float(apply_lut(S, mid)[0, 1]), 4),
                                    'srgbmid': round(float(apply_lut(M, mid)[0, 1]), 4)},
               'photos': {'srgb': r3(stats(dE(npx, apply_lut(S, x)))),
                          'srgbmid': r3(stats(dE(npx, apply_lut(M, x)))),
                          'srgb+g': r3(stats(dE(npx, pregain(S, x, g))))},
               'ramp': {'srgb': r3(stats(dE(npr, apply_lut(S, ramp)))),
                        'srgbmid': r3(stats(dE(npr, apply_lut(M, ramp)))),
                        'srgb+g': r3(stats(dE(npr, pregain(S, ramp, g))))},
               'L_median_photos': {'nicephoto': round(float(np.median(lab(npx)[:, 0])), 2),
                                   'srgb': round(float(np.median(lab(apply_lut(S, x))[:, 0])), 2),
                                   'srgbmid': round(float(np.median(lab(apply_lut(M, x))[:, 0])), 2),
                                   'input': round(float(np.median(lab(x)[:, 0])), 2)}}
        out[code] = row
        print(code, film, 'g', row['fitted_pregain'], row['fitted_pregain_ev'], {k: (v['median'], v['p99'])
              for k, v in row['photos'].items()}, row['midgray_0466_out'], flush=True)
    dump(LOCAL / 'nicephoto.json', out)


if __name__ == '__main__':
    main()
