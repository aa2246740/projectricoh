#!/usr/bin/env python3
"""RAW -> JPEG neutral tone curves for every GR IV / GR III frame used here.

Writes local/tone_curves.json (derived from contributor photos: local only).
Run: python3 -I research/gr4_modes/tone.py

Inputs are the .npz caches written by gr4io.load_pair (see run_all.sh).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core  # noqa: E402
import gr4io  # noqa: E402

LOCAL = HERE / 'local'
PUBLIC_CACHE = '/tmp/gr4modes_work/cache'

# key, cache dir (None = local/), body, mode, DR byte 0
FRAMES = [
    ('hdf_std', None, 'GR IV HDF 1.10 (B)', 'standard', 1),
    ('hdf_pos', None, 'GR IV HDF 1.10 (B)', 'positive', 1),
    ('hdf_neg', None, 'GR IV HDF 1.10 (B)', 'negative', 1),
    ('hdf_hc', None, 'GR IV HDF 1.10 (B)', 'hc_bw', 1),
    ('hdf_cy', None, 'GR IV HDF 1.10 (B)', 'cinema_yellow', 1),
    ('hdf_cg', None, 'GR IV HDF 1.10 (B)', 'cinema_green', 1),
    ('positive', None, 'GR IV 1.11 (A)', 'positive', 0),
    ('negative', None, 'GR IV 1.11 (A)', 'negative', 1),
    ('hc_bw', None, 'GR IV 1.11 (A)', 'hc_bw', 0),
] + [(f'gruser_G40000{n}', PUBLIC_CACHE, 'GR IV 1.02 (gruser)', 'standard', dr)
     for n, dr in [('30', 1), ('31', 1), ('32', 1), ('48', 1), ('49', 1), ('50', 1),
                   ('51', 0), ('52', 0), ('54', 0), ('55', 0), ('56', 0), ('57', 0)]] + [
    ('gruser_G4000053', PUBLIC_CACHE, 'GR IV 1.02 (gruser)', 'monotone', 0),
] + [(f'gruser_GR0028{n}', PUBLIC_CACHE, 'GR III 1.92 (gruser)', 'standard', dr)
     for n, dr in [('09', 1), ('10', 1), ('11', 0), ('12', 0), ('14', 0), ('15', 0), ('16', 0), ('17', 0)]] + [
    ('gruser_GR002813', PUBLIC_CACHE, 'GR III 1.92 (gruser)', 'monotone', 0),
    ('gr3chart_std', PUBLIC_CACHE, 'GR III 1.60 chart (bastibe)', 'standard', 0),
    ('gr3chart_pos', PUBLIC_CACHE, 'GR III 1.60 chart (bastibe)', 'positive', 0),
    ('gr3chart_neg', PUBLIC_CACHE, 'GR III 1.60/1.71 chart (bastibe)', 'negative', 0),
]

NEUTRAL_SPREAD = 0.15     # white-balanced (max-min)/mean of the RAW block
FLAT_CV = 0.06            # RAW block coefficient of variation


def selection(b, spread=NEUTRAL_SPREAD, cv=FLAT_CV):
    wb = b['wb']
    s = (wb.max(-1) - wb.min(-1)) / np.maximum(wb.mean(-1), 1e-6)
    return (s < spread) & (b['u_cv'] < cv) & (b['u'] > 2e-4)


def radial_for(key, b, sel):
    s = sel & (b['jl'] > 3) & (b['jl'] < 240)
    if s.sum() < 2000:
        return None
    try:
        return core.fit_tone_radial(np.log(np.clip(b['u'], 1e-6, None)), b['jl'], s, b['r2'])
    except ValueError:
        return None


def main():
    out = {'definitions': {
        'u': '2**BaselineExposure * (R/nR + 2G/nG + B/nB)/4, camera RGB normalised to (raw-black)/(white-black), n = AsShotNeutral',
        'u_c': 'u times the radial gain g(r) the camera applies before the curve; g(0)=1',
        'jpeg_luma': 'Rec.709 weights on encoded 8-bit RGB (same as phase 1); equals the grey value for neutral blocks',
        'block': '8x8 sensor pixels (4x4 half-res RGGB quads)',
        'neutral': f'RAW white-balanced spread < {NEUTRAL_SPREAD}, RAW block CV < {FLAT_CV}',
    }, 'frames': {}}
    # Radial gain: one GR IV fit (B Standard, many neutral blocks), checked per frame.
    ref = core.blocks(gr4io.load_pair(None, None, cache_name='hdf_std'))
    ref_fit = radial_for('hdf_std', ref, selection(ref, spread=0.3))
    gr4_coef = ref_fit['radial_coef']
    gr3 = core.blocks(gr4io.load_pair(None, None, cache_name='gruser_GR002814', cache_dir=PUBLIC_CACHE))
    gr3_fit = radial_for('gruser_GR002814', gr3, selection(gr3, spread=0.3))
    gr3_coef = gr3_fit['radial_coef']
    out['radial'] = {
        'gr4_coef_natural_log': list(map(float, gr4_coef)),
        'gr4_gain_ev_at_r': {str(r): float(core.radial_gain_ev(gr4_coef, r * r)) for r in (0.3, 0.5, 0.7, 0.85, 1.0)},
        'gr3_coef_natural_log': list(map(float, gr3_coef)),
        'gr3_gain_ev_at_r': {str(r): float(core.radial_gain_ev(gr3_coef, r * r)) for r in (0.3, 0.5, 0.7, 0.85, 1.0)},
        'r': 'distance from image centre / half diagonal',
    }
    for key, cdir, body, mode, dr in FRAMES:
        pair = gr4io.load_pair(None, None, cache_name=key, cache_dir=cdir)
        b = core.blocks(pair)
        sel = selection(b)
        coef = gr3_coef if body.startswith('GR III') else gr4_coef
        own = radial_for(key, b, sel)
        lu = np.log(np.clip(b['u'], 1e-6, None))
        luc = core.correct_u(lu, b['r2'], coef)
        rows = core.forward_curve(luc, b['jl'], sel)
        rec = {'body': body, 'mode': mode, 'dr_expansion_byte0': dr,
               'baseline_exposure': float(pair['baseline_exposure']),
               'neutral': list(map(float, pair['neutral'])), 'cct_K': b['cct'],
               'n_neutral_blocks': int(sel.sum()),
               'own_radial_gain_ev_at_r': ({str(r): float(core.radial_gain_ev(own['radial_coef'], r * r)) for r in (0.5, 0.7, 0.85, 1.0)} if own else None),
               'own_radial_resid_ev': own['resid_ev_std'] if own else None,
               'curve': rows}
        f = core.curve_fn(rows) if len(rows) > 3 else None
        if f is not None:
            inv = core.inverse_fn(f)
            rec['u_c_at_jpeg'] = {str(c): (float(np.exp(inv(c))) if np.isfinite(inv(c)) else None)
                                  for c in (20, 50, 80, 100, 118, 128, 150, 180, 200, 220, 240)}
            rec['support_u_c'] = [float(np.exp(f.support[0])), float(np.exp(f.support[1]))]
            rec['jpeg_range'] = [float(f.y.min()), float(f.y.max())]
        out['frames'][key] = rec
        print(f"{key:18s} {mode:13s} DR{dr} n={sel.sum():6d} support u_c {rec.get('support_u_c')} "
              f"u@118={rec.get('u_c_at_jpeg', {}).get('118')} own r1 gain {(rec['own_radial_gain_ev_at_r'] or {}).get('1.0')}", flush=True)
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / 'tone_curves.json').write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
