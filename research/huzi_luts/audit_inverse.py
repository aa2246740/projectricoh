#!/usr/bin/env python3
"""Check actual native-V-Log anchors and the hardest synthetic inverse results."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *


def main():
    preflight(); install_fence()
    import numpy as np
    from scipy.optimize import least_squares
    from panasonic import StandardInverse, summary
    Camera, _, _, stats, Cube, _, _, _ = converter()
    from spaces import encode, matrix
    c = Camera()
    inv = StandardInverse(Cube.read(DOWNLOAD/'Luts/Panasonic-Standard/Conversion/S1RIIS2V.cube'))
    anchor_path = DOWNLOAD/'Luts/Panasonic-Standard/Calibration/PanasonicForwardPairAnchors.npz'
    with np.load(anchor_path, allow_pickle=False) as z:
        anchor = {k: z[k].copy() for k in z.files}
    rgb, residual = inv.invert(anchor['target'])
    de = c.fs.delta_e00(c.fs.lab_from_codes(rgb*255), c.fs.lab_from_codes(anchor['standard']*255))
    data = np.load(LOCAL/'prepared/dataset.npz', allow_pickle=False)
    old = np.load(LOCAL/'prepared/S1RII.npz', allow_pickle=False)
    y, x, e = data['test_vlog'], old['test']/255, old['test_inverse_residual']
    idx = np.r_[np.argsort(e)[-24:], np.linspace(0, len(y)-1, 12).astype(int)]
    checks = []
    for i in idx:
        best = None
        for start in (x[i], np.full(3, .5)):
            opt = least_squares(lambda q: inv.cube.apply(q[None])[0]-y[i],
                    np.clip(start, 1e-9, 1-1e-9), jac=lambda q: inv.value_jacobian(q[None])[1][0],
                    bounds=(0., 1.), max_nfev=160, ftol=1e-11, xtol=1e-11, gtol=1e-11)
            result = {'sse': float(np.sum(opt.fun**2)), 'linf': float(abs(opt.fun).max()),
                      'standard_rgb': opt.x, 'status': int(opt.status)}
            if best is None or result['sse'] < best['sse']:
                best = result
        vector_sse = float(np.sum((inv.cube.apply(x[i:i+1])[0]-y[i])**2))
        checks.append({'synthetic_index': int(i), 'vlog': y[i], 'vector_standard': x[i],
                       'vector_linf': float(e[i]), 'vector_sse': vector_sse,
                       'scipy_two_start': best,
                       'scipy_improves_linf_gt_1e_3': bool(e[i]-best['linf'] > .001)})
    np.savez_compressed(LOCAL/'inverse_anchor_evaluation.npz', measured_standard=anchor['standard'],
                        measured_vlog=anchor['target'], inverse_standard=rgb,
                        inverse_residual=residual, delta_e00=de)
    official = np.array([[.679644,.152211,.118600],[.260686,.774894,-.035580],[-.009310,-.004612,1.102980]])
    doc = {'anchor_sha256': sha(anchor_path), 'anchor_n': len(de),
           'standard_reconstruction_de00': stats(de), 'chart_first_72_de00': stats(de[:72]),
           'scene_remaining_20519_de00': stats(de[72:]),
           'inverse_boundary': inv.boundary(anchor['target'], rgb, residual),
           'scope': 'agreement on upstream training/calibration anchors; not independent capture validation',
           'hard_case_scipy_checks': checks,
           'hard_case_checks_n': len(checks),
           'hard_cases_scipy_improves_linf_gt_1e_3': sum(r['scipy_improves_linf_gt_1e_3'] for r in checks),
           'official_formula_checks': {
               'xyz_matrix_max_error_vs_6dp_official': float(abs(matrix('vgamut')-official).max()),
               'vlog_black_18pct_90pct_times_1023': encode(np.array([0.,.18,.9]),'vlog')*1023}}
    dump(LOCAL/'inverse_anchor_evaluation.json', doc)
    print('Anchor reconstruction DE00 median/p90', round(float(np.median(de)),3), round(float(np.percentile(de,90)),3))
    print('Hard-case independent solver improvements >0.001:', doc['hard_cases_scipy_improves_linf_gt_1e_3'], '/', len(checks))


if __name__ == '__main__':
    main()
