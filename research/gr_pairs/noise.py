"""Conditional JPEG dispersion with exact-input counts and nonoverlapping averages."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LOCAL, read, dump, stats, guard, modules
from models import samples, SCALE, error
import numpy as np
from scipy.spatial import cKDTree
import json


def group_pairs(keys):
    _, inv, count = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    result = []
    for k in np.flatnonzero(count > 1):
        ix = np.flatnonzero(inv == k)
        result.extend((int(ix[0]), int(j)) for j in ix[1:])
    return np.asarray(result, int).reshape(-1, 2)


def measure():
    guard()
    out = {}
    for frame in read(LOCAL / 'inventory.json'):
        d = samples([frame['id']])
        raw_exact = group_pairs(np.column_stack([d['raw3'], np.floor(d['r2'] / .02).astype(int)]))
        uc_exact = group_pairs(d['uc_quad'].view(np.uint32))
        dm, ix = cKDTree(d['features'] / SCALE).query(d['features'] / SCALE, k=32, workers=1)
        ii = np.arange(len(ix))
        spatial = np.max(abs(d['xy'][:, None, :].astype(int) - d['xy'][ix].astype(int)), axis=-1) > 8
        choice = (dm < .1) & spatial & (ii[:, None] < ix)
        rows = np.flatnonzero(choice.any(axis=1))
        col = np.argmax(choice[rows], axis=1)
        mean_pairs = np.column_stack([rows, ix[rows, col]])
        def score(pp, field):
            if len(pp) == 0:
                return {'n': 0, 'delta_e00': stats([]), 'rgb_rms_codes': stats([])}
            a, b = pp.T
            y = d[field]
            return {'n': len(pp), 'delta_e00': stats(error(y[a], y[b])),
                    'rgb_rms_codes': stats(np.sqrt(np.mean((y[a] - y[b]) ** 2, axis=1)))}
        out[frame['id']] = {'exact_corrected_uc_quad': score(uc_exact, 'jpeg_quad'),
                            'exact_RAW_RGB_r2_bin_0p02': score(raw_exact, 'jpeg_quad'),
                            'near_uc_mean_nonoverlap': score(mean_pairs, 'jpeg'),
                            'near_input_log2_tolerances': (SCALE * .1),
                            'spatial_distance_min_half_pixels': 9,
                            'pure_irreducible_noise_floor_identified': False}
    dump(LOCAL / 'analysis/noise.json', out)
    print(json.dumps({k: {n: {'pairs': q['n'], 'median': q['delta_e00']['median']} for n, q in v.items() if isinstance(q, dict)}
                      for k, v in out.items()}), flush=True)


if __name__ == '__main__':
    measure()
