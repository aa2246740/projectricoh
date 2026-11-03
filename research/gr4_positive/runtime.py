"""Reuse established numerical code without importing its write drivers."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap as b
import ast
import functools
import numpy as np

b.guard()
P = b.load('positive_pairs_refit', b.ROOT / 'research/gr_pairs/refit.py')
FS, MM, E, G = P.FS, P.MM, P.E, P.G
common = sys.modules['common']
common.TMP = b.TMP
grio, CM, meas, tn = common.modules()
grio.SCRATCH = b.TMP / 'decoder'
grio.LOCAL = b.LOCAL / 'decoder_cache'
__import__('os').environ['TMPDIR'] = str(b.TMP)


@functools.lru_cache(None)
def data(iso=200):
    return P.data_of('01', iso)


@functools.lru_cache(None)
def generator():
    return G.GRGenerator(b.ROOT / 'artifacts/downloads/bastibe-gr3')


@functools.lru_cache(None)
def transfer(group='gr4_hdf'):
    return P.Transfer(group, 'positive', G, generator())


def arrays(path):
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k].copy() for k in z.files}


def save(path, **values):
    path = Path(path).resolve()
    assert path.is_relative_to(b.LOCAL)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **values)


def jsonable(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    return v


def dump(path, value):
    b.dump(path, jsonable(value))


def stats(v):
    v = np.asarray(v, float)
    if not v.size:
        return dict(n=0, median=None, p90=None, mean=None, max=None)
    assert np.isfinite(v).all()
    return dict(n=int(v.size), median=float(np.median(v)), p90=float(np.percentile(v, 90)),
                mean=float(v.mean()), max=float(v.max()))


def score(target, pred, base):
    error = FS.delta_e00(target, pred)
    den = stats(FS.delta_e00(target, base))
    out = stats(error)
    out.update(stock04=den, similarity=1-out['median']/den['median'] if len(error) and den['median'] > 1e-12 else None,
               share_lt2=float(np.mean(error < 2)) if len(error) else None)
    return out


def rgb(fit, x, iso=200):
    D = data(iso)
    row, A, B = E.f.unpack_solution(fit)
    pre = MM.Curve(D.a['curve_x'], D.a['curve_y'])(np.asarray(x))
    return D.forward(pre, row, FS.Z_of_words(A, B, D.ctx))[1]


def predict(fit, x, iso=200):
    return FS.lab_from_codes(rgb(fit, x, iso))


def source_functions(path, names, namespace):
    tree = ast.parse(path.read_text())
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in selected} == set(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


web = source_functions(b.ROOT / 'research/gr_webpairs/score.py', ['selected', 'bridge'],
    dict(np=np, ROOT=b.ROOT, read=b.read, modules=lambda: (grio, CM, meas, tn)))


def known_datasets():
    return b.read(b.LOCAL / 'datasets.json')


def dataset(ident):
    return arrays(b.LOCAL / 'datasets' / (ident + '.npz'))


if __name__ == '__main__':
    print('Established round5 renderer loaded; curve nodes:', len(data().a['curve_x']))
