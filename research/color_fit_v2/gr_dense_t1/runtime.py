"""Offline runtime with an enforced write fence and frozen source modules."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[key] = '1'
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import hashlib
import importlib.util
import json
import ast
import math
import struct
from functools import lru_cache

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = HERE / 'local'
VROOT = LOCAL / 'vendor/repo'
os.environ['TMPDIR'] = str(LOCAL / 'tmp')
READS, WRITES = set(), set()


def audit(event, args):
    if event.startswith(('socket.connect', 'socket.bind', 'socket.getaddrinfo')):
        raise PermissionError('Offline task forbids network access')
    if event != 'open' or not isinstance(args[0], (str, bytes, Path)):
        return
    p = Path(os.fsdecode(args[0])).absolute()
    if str(p).startswith('/Volumes/') and not p.is_relative_to(Path('/Volumes/Workspace')):
        raise PermissionError('Other volumes forbidden: ' + str(p))
    mode, flags = args[1:3]
    write = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
        isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
    if write:
        assert p.resolve().is_relative_to(HERE), 'Write outside task fence: ' + str(p)
        WRITES.add(str(p))
    elif p.is_relative_to(ROOT):
        READS.add(str(p))


sys.addaudithook(audit)
import numpy as np
from scipy.optimize import least_squares


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def plain(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, bytes):
        return {'length': len(v), 'sha256': hashlib.sha256(v).hexdigest()}
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    return v


def dump(path, v):
    path = Path(path).resolve()
    assert path.is_relative_to(HERE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain(v), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


P = load('dense_frozen_pairs', VROOT / 'research/gr_pairs/refit.py')
G, E, FS, MM = P.G, P.E, P.FS, P.MM
SRC = E.src
NODES = np.array([int(v) >> 8 for v in struct.unpack('>24H',
    SRC.read_image(SRC.jlaunch(), 0x2012C0F4, 48))]) * (360 / 256)
NO_T = (0, 11, 17, 23)
# Reuse the measured T1/T3 renderer and its analytic Jacobian without executing
# Fuji's measurement-specific imports, input selection, or package writer.
source = VROOT / 'research/color_fit_v2/fuji_round5/core.py'
tree = ast.parse(source.read_text())
fragment = ast.Module(body=[n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                          and n.name in ('weights', 'physical_weights', 'Fit', 'Response')], type_ignores=[])
ns = dict(np=np, math=math, least_squares=least_squares, fs=FS, mm=MM, src=SRC,
          NODES=NODES, NO_T=NO_T)
exec(compile(fragment, str(source), 'exec'), ns)
BaseFit, Response, weights = ns['Fit'], ns['Response'], ns['weights']
physical_weights = ns['physical_weights']
for m in ('common', 'extract', 'models', 'targets'):
    mod = sys.modules[m]
    if hasattr(mod, 'TMP'):
        mod.TMP = LOCAL / 'tmp'
sys.modules['common'].modules()[0].SCRATCH = LOCAL / 'tmp/decoder'
os.environ['TMPDIR'] = str(LOCAL / 'tmp')


@lru_cache(None)
def data(slot, iso=200):
    return P.data_of(slot, iso)


@lru_cache(None)
def generator():
    return G.GRGenerator(VROOT / 'artifacts/downloads/bastibe-gr3')


def transfer(group, slot):
    return P.Transfer(group, 'positive' if slot == '01' else 'negative', G, generator())


def stats(a):
    a = np.asarray(a, float)
    if not a.size:
        return dict(n=0, median=None, p90=None, mean=None, max=None)
    assert np.isfinite(a).all()
    return dict(n=int(a.size), median=float(np.median(a)), p90=float(np.percentile(a, 90)),
                mean=float(a.mean()), max=float(a.max()))


def score(target, pred, base):
    error = FS.delta_e00(target, pred)
    out = stats(error)
    den = stats(FS.delta_e00(target, base))
    out['stock04'] = den
    out['similarity'] = 1-out['median']/den['median'] if out['n'] and den['median'] > 1e-12 else None
    out['fractions'] = {f'lt{x}': float((error < x).mean()) if len(error) else None for x in (1, 2, 3)}
    return out


if __name__ == '__main__':
    for group in ('gr3', 'gr4_hdf'):
        for slot in ('01', '02'):
            d = P.dense(group, slot)
            t = transfer(group, slot)
            target, valid = P.observed_targets(group, slot, d, t)
            print(group, slot, 'keys', list(d), 'valid', int(valid.sum()), 'nodes', len(data(slot).a['curve_x']))
    print('runtime import and observed-target rendering passed')
