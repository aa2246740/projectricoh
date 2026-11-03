"""Weighted smooth RAW-to-JPEG functions, spatial CV and repeat-value dispersion."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, LOCAL, dump, read, guard, modules, stats
from extract import feature
import argparse
import json
import numpy as np
from scipy.interpolate import NdBSpline
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree

CM = modules()[1]
SCALE = np.array([.35, .10, .10])


def knots():
    return tuple(np.r_[[lo] * 4, interior, [hi] * 4].astype(float) for lo, hi, interior in (
        (-12, 2, np.arange(-10, 1, .8)),
        (-4, 4, np.arange(-2, 2.01, .5)),
        (-4, 4, np.arange(-2, 2.01, .5))))


KNOTS = knots()
SHAPE = tuple(len(t) - 4 for t in KNOTS)


def design(x):
    x = np.asarray(x, float).copy()
    if len(x) == 0:
        return sparse.csr_matrix((0, int(np.prod(SHAPE))))
    for j, t in enumerate(KNOTS):
        x[:, j] = np.clip(x[:, j], t[3], t[-4])
    a = sparse.csr_matrix(NdBSpline.design_matrix(x, KNOTS, 3))
    # SciPy omits trailing all-zero columns when the observed gamut is small.
    return sparse.csr_matrix((a.data, a.indices, a.indptr), shape=(len(x), int(np.prod(SHAPE))))


def regularizer():
    terms = []
    for axis, n in enumerate(SHAPE):
        d = sparse.diags([np.ones(n - 2), -2 * np.ones(n - 2), np.ones(n - 2)], [0, 1, 2], shape=(n - 2, n))
        left = sparse.eye(int(np.prod(SHAPE[:axis])))
        right = sparse.eye(int(np.prod(SHAPE[axis + 1:])))
        terms.append(sparse.kron(sparse.kron(left, d), right, format='csr'))
    d = sparse.vstack(terms, format='csr')
    return d.T @ d


REG = regularizer()


class Function:
    """Tensor cubic B-spline, fit in camera JPEG codes; confidence is empirical."""
    def __init__(self, coefficients, x, weights=None):
        self.coef = coefficients
        self.x = x
        self.tree = cKDTree(x / SCALE)
        self.weights = weights

    @classmethod
    def fit(cls, x, y, weight, smooth=.3):
        X = design(x)
        w = np.asarray(weight, float)
        # One fixed smoothing rule. CV never tunes it against held-out scores.
        Xw = X.multiply(w[:, None])
        normal = (X.T @ Xw + smooth * REG + sparse.eye(REG.shape[0]) * 1e-5).tocsc()
        c = spsolve(normal, np.asarray(X.T @ (w[:, None] * y)))
        return cls(c, np.asarray(x), w)

    def predict(self, x):
        return np.clip(design(x) @ self.coef, 0, 255)

    def support(self, x):
        dist, _ = self.tree.query(np.asarray(x) / SCALE, k=8, workers=1)
        return (dist[:, 0] <= 1.) & (dist[:, -1] <= 1.5), dist[:, 0]

    def save(self, path):
        np.savez_compressed(path, coefficients=self.coef, training_x=self.x, weight=self.weights)

    @classmethod
    def open(cls, name):
        with np.load(LOCAL / 'models' / (name + '.npz'), allow_pickle=False) as z:
            return cls(z['coefficients'], z['training_x'], z['weight'])


def samples(ids):
    arrays = []
    for i, name in enumerate(ids):
        with np.load(LOCAL / 'samples' / (name + '.npz'), allow_pickle=False) as z:
            d = dict(z)
        d['image'] = np.full(len(d['jpeg']), i, np.int16)
        arrays.append(d)
    return {k: np.concatenate([d[k] for d in arrays]) for k in arrays[0]}


def model_groups():
    groups = {f['id']: [f['id']] for f in read(LOCAL / 'inventory.json')}
    groups['gr3_standard_pooled'] = ['bastibe_standard', 'ir_still', 'ir_portrait']
    groups['gr3_family_standard_pooled'] = ['bastibe_standard', 'ir_still', 'ir_portrait', 'ir_gr3x']
    return groups


def error(y, prediction):
    return CM.delta_e00(CM.rgb_lab(y / 255), CM.rgb_lab(prediction / 255))


def dispersion(d):
    # Exact repeated RAW tuples are reported separately from near-equal corrected u_c.
    keys = np.column_stack([d['image'], d['raw3'], np.floor(d['r2'] / .02).astype(int)])
    _, inv, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    pairs = []
    for g in np.flatnonzero(counts >= 2):
        ix = np.flatnonzero(inv == g)
        pairs.extend((int(ix[0]), int(j)) for j in ix[1:])
    exact = np.asarray(pairs, int).reshape(-1, 2)
    x = d.get('features_quad', d['features']) / SCALE
    dist, near = cKDTree(x).query(x, k=2, workers=1)
    i = np.arange(len(x))
    use = (i < near[:, 1]) & (dist[:, 1] < .1)
    nearpairs = np.column_stack([i[use], near[use, 1]])
    def summarize(pp):
        if not len(pp):
            return {'pairs': 0, 'delta_e00': stats([]), 'rgb_rms_codes': stats([])}
        a, b = pp.T
        j = d.get('jpeg_quad', d['jpeg'])
        return {'pairs': len(pp), 'delta_e00': stats(error(j[a], j[b])),
                'rgb_rms_codes': stats(np.sqrt(np.mean((j[a] - j[b]) ** 2, axis=-1)))}
    return {'exact_raw_same_r2_bin': summarize(exact), 'near_uc_distance_le_0p1': summarize(nearpairs),
            'interpretation': 'pairwise dispersion, not irreducible sensor noise; shading, demosaic and scene-local processing remain',
            'exact_repeat_radius_bin_width_r2': .02, 'near_uc_scale_log2': SCALE, 'near_uc_threshold': .1}


def train(name, ids):
    d = samples(ids)
    x, y, w = d['features'], d['jpeg'], d['weight']
    model = Function.fit(x, y, w)
    outdir = LOCAL / 'models'
    outdir.mkdir(parents=True, exist_ok=True)
    model.save(outdir / (name + '.npz'))
    pred = np.full_like(y, np.nan, dtype=float)
    covered = np.zeros(len(y), bool)
    folds = []
    for fold in range(4):
        train = (d['folds'] != fold) & d['spatial_core']
        test = (d['folds'] == fold) & d['spatial_core']
        f = Function.fit(x[train], y[train], w[train])
        pred[test] = f.predict(x[test])
        covered[test] = f.support(x[test])[0]
        folds.append({'fold': fold, 'train': int(train.sum()), 'test': int(test.sum()),
                      'de00': stats(error(y[test], pred[test])),
                      'supported_fraction': float(covered[test].mean())})
    valid = d['spatial_core']
    de = error(y[valid], pred[valid])
    image_cv = []
    if len(ids) > 1:
        for i, ident in enumerate(ids):
            tr, te = d['image'] != i, d['image'] == i
            f = Function.fit(x[tr], y[tr], w[tr])
            p = f.predict(x[te])
            support, distance = f.support(x[te])
            image_cv.append({'heldout': ident, 'train_images': [j for j in ids if j != ident],
                             'de00_all': stats(error(y[te], p)), 'de00_supported': stats(error(y[te][support], p[support])),
                             'supported_fraction': float(support.mean())})
    else:
        image_cv = [{'heldout': ids[0], 'available': False, 'reason': 'Only one scene for this body/style; zero style observations remain'}]
    metrics = {'name': name, 'frames': ids, 'model': 'weighted cubic tensor B-spline in log2(u), log2(R/G), log2(B/G)',
               'coefficient_shape': SHAPE, 'smoothing': .3, 'n': len(y), 'spatial_folds': folds,
               'spatial_cv_de00': stats(de), 'spatial_cv_supported_de00': stats(error(y[valid & covered], pred[valid & covered])),
               'spatial_cv_rgb_rms_codes': stats(np.sqrt(np.mean((y[valid] - pred[valid]) ** 2, axis=1))),
               'spatial_cv_by_hue': {f'{h * 30:03d}-{(h + 1) * 30:03d}': stats(de[(d['cell'][valid] // 15 == h) &
                                                                                             (d['cell'][valid] % 3 > 0)]) for h in range(12)},
               'image_holdout': image_cv, 'noise_dispersion': dispersion(d),
               'single_scene_spatial_CV_is_not_cross_scene_validation': True}
    np.savez_compressed(outdir / (name + '_cv.npz'), predicted=pred[valid], observed=y[valid],
                        image=d['image'][valid], features=x[valid], supported=covered[valid])
    dump(outdir / (name + '.json'), metrics)
    print(json.dumps({'model': name, 'n': len(y), 'spatial_cv': metrics['spatial_cv_de00'],
                      'image_holdout': image_cv}, ensure_ascii=False), flush=True)


def compare_dr():
    # DR status is confounded with body, ISO and scene. Compare normalized overlapping x only.
    checks = []
    for mode in ('positive', 'negative'):
        a, b = 'hdf_' + mode, 'gr4b_' + mode
        da, db = samples([a]), samples([b])
        fa, fb = Function.open(a), Function.open(b)
        xx = np.concatenate([da['features'][::5], db['features'][::5]])
        ok = fa.support(xx)[0] & fb.support(xx)[0]
        p, q = fa.predict(xx[ok]), fb.predict(xx[ok])
        checks.append({'mode': mode, 'overlap': int(ok.sum()), 'de00': stats(error(p, q)),
                       'luma_code_difference_b_minus_hdf': stats(abs((q - p) @ np.array([.2126, .7152, .0722]))),
                       'hdf_DR': True, 'body_b_DR': mode == 'negative',
                       'causal_DR_effect_identifiable': False})
    dump(LOCAL / 'body_dr_comparison.json', checks)
    print(json.dumps(checks), flush=True)


def main():
    guard()
    p = argparse.ArgumentParser()
    p.add_argument('--model', action='append')
    p.add_argument('--compare', action='store_true')
    a = p.parse_args()
    if a.compare:
        compare_dr()
    else:
        for name, ids in model_groups().items():
            if a.model is None or name in a.model:
                train(name, ids)


if __name__ == '__main__':
    main()
