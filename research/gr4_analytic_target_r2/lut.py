"""Complete 17 cubed reference with the frozen second-pass LUT training protocol."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import fit as ff
from scipy.linalg import cho_factor, cho_solve
from scipy.spatial.distance import cdist


def target_rgb(target):
    return np.clip(rt.cm.srgb_encode(rt.cm.lab_xyz(target, rt.cm.D65) @ np.linalg.inv(rt.cm.SRGB_XYZ).T) * 255, 0, 255)


def kernel(a, b, width):
    return np.exp(-cdist(a, b, 'sqeuclidean') / (2 * width ** 2))


def fit(x, y, width, ridge):
    K = kernel(x, x, width)
    alpha = cho_solve(cho_factor(K + ridge * np.eye(len(x)), lower=True), y - x)
    return dict(x=x, alpha=alpha, width=width, ridge=ridge)


def predict(model, x):
    return x + kernel(x, model['x'], model['width']) @ model['alpha']


def choose(m, x, target, train, groups):
    rows = []
    for width in (24., 48., 96.):
        for ridge in (.01, .1, 1.):
            errors = []
            for group in np.unique(groups[train]):
                a, b = train & (groups != group), train & (groups == group)
                if a.sum() < 20 or not b.any(): continue
                model = fit(x[a], target_rgb(target[a]), width, ridge)
                pred = np.clip(predict(model, x[b]), 0, 255)
                errors.extend(m.fs.delta_e00(m.fs.lab_from_codes(pred), target[b]))
            rows.append(dict(width=width, ridge=ridge, inner_n=len(errors),
                inner_median=float(np.median(errors)) if errors else 1e20))
    return min(rows, key=lambda r: r['inner_median']), rows


def grid(model, n=17):
    x = np.stack(np.meshgrid(*([np.linspace(0, 255, n)] * 3), indexing='ij'), axis=-1).reshape(-1, 3)
    y = np.empty_like(x)
    for start in range(0, len(x), 2048):
        y[start:start + 2048] = np.clip(predict(model, x[start:start + 2048]), 0, 255)
    return np.floor(y.reshape(n, n, n, 3) * 256 + .5).astype(np.uint16)


def apply(table, x, strict=False):
    if strict: x = np.floor(np.clip(x, 0, 255) + .5)
    n = table.shape[0]
    xx = np.floor(np.clip(x, 0, 255) * ((n - 1) / 255) * 256 + .5) / 256
    ix = np.minimum(np.floor(xx).astype(int), n - 2)
    frac = xx - ix
    order = np.argsort(-frac, axis=1, kind='stable')
    delta = np.eye(3, dtype=int)[order]
    vv = np.stack([ix, ix + delta[:, 0], ix + delta[:, 0] + delta[:, 1], ix + 1], axis=1)
    f = np.take_along_axis(frac, order, axis=1)
    weights = np.rint(np.stack([1 - f[:, 0], f[:, 0] - f[:, 1], f[:, 1] - f[:, 2], f[:, 2]], axis=1) * 256).astype(np.int64)
    assert np.all(weights.sum(1) == 256)
    nodes = table[vv[:, :, 0], vv[:, :, 1], vv[:, :, 2]].astype(np.int64)
    output = (nodes * weights[:, :, None]).sum(axis=1) / 65536
    return np.floor(output + .5) if strict else output


def one(m, slot, fold, source):
    path = rt.LOCAL / f'lut/{slot}/{source}/{fold}.json'
    if path.exists(): return rt.read(path)
    d = ff.data(m, slot, fold)
    x = rt.old.Problem(m, slot, d).predict(np.zeros(0)) if source == 'current' else m.predict('04', d['x'])
    groups = d['pages'] if fold.startswith('page') else d['hue_group']
    choice, inner = choose(m, x, d['target'], d['train'], groups)
    mdl = fit(x[d['train']], target_rgb(d['target'][d['train']]), choice['width'], choice['ridge'])
    table = grid(mdl)
    pred, strict = apply(table, x), apply(table, x, True)
    error = m.fs.delta_e00(m.fs.lab_from_codes(pred), d['target'])
    strict_error = m.fs.delta_e00(m.fs.lab_from_codes(strict), d['target'])
    smooth = np.clip(predict(mdl, x), 0, 255)
    smooth_error = m.fs.delta_e00(m.fs.lab_from_codes(smooth), d['target'])
    held = d['held']
    doc = dict(slot=slot, fold=fold, source=source, evidence='电脑预测',
        target_label='未验证的模拟目标，仅作诊断', score=rt.old.score(error[held], d['baseline'][held]),
        strict_u8=rt.old.score(strict_error[held], d['baseline'][held]),
        continuous_RBF=rt.old.score(smooth_error[held], d['baseline'][held]),
        choice=choice, inner=inner, heldout_used_for_choice=False,
        train_keys=d['train_keys'], held_keys=d['held_keys'], theoretical_global_upper_bound=False)
    rt.dump(path, doc)
    np.savez_compressed(path.with_suffix('.npz'), prediction=pred, error=error, strict_error=strict_error,
        smooth_error=smooth_error, held=held, train=d['train'], target=d['target'], baseline=d['baseline'],
        nodes_q8_8=table, input=x)
    print(json.dumps(dict(slot=slot, fold=fold, source=source, width=choice['width'], ridge=choice['ridge'],
        percent=round(doc['score']['similarity'] * 100, 3))), flush=True)
    return doc


def aggregate():
    rows = []
    for slot in ('01', '02'):
        for source in ('current', '04model'):
            for scheme, folds in [('page', ff.FOLDS[:6]), ('hue', ff.FOLDS[6:])]:
                paths = [rt.LOCAL / f'lut/{slot}/{source}/{f}.npz' for f in folds]
                if not all(p.exists() for p in paths): continue
                a = [rt.arrays(p) for p in paths]
                cat = lambda k: np.concatenate([q[k][q['held']] for q in a])
                rows.append(dict(slot=slot, source=source, route='LUT17_' + source, scheme=scheme,
                    evidence='电脑预测', **rt.old.score(cat('error'), cat('baseline')),
                    strict_u8=rt.old.score(cat('strict_error'), cat('baseline')),
                    continuous_RBF=rt.old.score(cat('smooth_error'), cat('baseline'))))
    rt.dump('aggregates/lut.json', rows)
    return rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--slots', default='01,02')
    ap.add_argument('--folds', default=','.join(ff.FOLDS))
    a = ap.parse_args()
    m = rt.model()
    for slot in a.slots.split(','):
        for fold in a.folds.split(','):
            for source in ('current', '04model'):
                one(m, slot, fold, source)
    print(json.dumps(aggregate(), ensure_ascii=False), flush=True)
    rt.finish('lut')
