"""Shared helpers for the GR Positive/Negative gap study. Run scripts with python3 -I -B."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
CAPS = ROOT / 'captures/gr-posneg-gap'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/gr-posneg-gap')
for key in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
os.environ['TMPDIR'] = str(TMP)
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cm = _load('gap_colour_math', 'research/color_references/colour_math.py')


def lab(rgb):
    return cm.xyz_lab(cm.srgb_decode(np.asarray(rgb, float) / 255) @ cm.SRGB_XYZ.T, cm.D65)


def rgb(labs):
    return cm.srgb_encode(cm.lab_xyz(np.asarray(labs, float), cm.D65) @ np.linalg.inv(cm.SRGB_XYZ).T) * 255


def de(a, b):
    return cm.delta_e00(np.asarray(a, float).reshape(-1, 3), np.asarray(b, float).reshape(-1, 3))


def lch(labs):
    labs = np.asarray(labs, float)
    return labs[..., 0], np.hypot(labs[..., 1], labs[..., 2]), np.degrees(np.arctan2(labs[..., 2], labs[..., 1])) % 360


def stats(v):
    v = np.asarray(v, float)
    if not v.size:
        return dict(n=0)
    return dict(n=int(v.size), median=float(np.median(v)), mean=float(v.mean()), p90=float(np.percentile(v, 90)))


def score(err, base):
    e, b = stats(err), stats(base)
    return dict(error=e, baseline=b, S_median=1 - e['median'] / b['median'], S_mean=1 - e['mean'] / b['mean'])


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=float) + '\n')


def jpg(path):
    return np.asarray(Image.open(path).convert('RGB'))


def lut_apply(nodes, x, chunk=1 << 20):
    """Tetrahedral 8-bit LUT, same ordering as gr4_lut_ceiling/lut.py (Q8.8 nodes when integer)."""
    nodes = np.asarray(nodes)
    n = nodes.shape[0]
    q8 = np.issubdtype(nodes.dtype, np.integer)
    flat = nodes.reshape(-1, 3).astype(np.int64 if q8 else float)
    x = np.asarray(x).reshape(-1, 3)
    out = np.empty((len(x), 3), np.uint8 if q8 else float)
    for s in range(0, len(x), chunk):
        xx = np.clip(np.floor(np.clip(x[s:s + chunk], 0, 255) + .5), 0, 255) * ((n - 1) / 255)
        xx = np.floor(xx * 256 + .5) / 256
        ix = np.minimum(np.floor(xx).astype(int), n - 2)
        fr = xx - ix
        order = np.argsort(-fr, axis=1, kind='stable')
        delta = np.eye(3, dtype=int)[order]
        vv = np.stack([ix, ix + delta[:, 0], ix + delta[:, 0] + delta[:, 1], ix + 1], axis=1)
        ff = np.take_along_axis(fr, order, axis=1)
        w = np.stack([1 - ff[:, 0], ff[:, 0] - ff[:, 1], ff[:, 1] - ff[:, 2], ff[:, 2]], axis=1)
        idx = (vv[..., 0] * n + vv[..., 1]) * n + vv[..., 2]
        val = flat[idx]
        if q8:
            w = np.rint(w * 256).astype(np.int64)
            out[s:s + chunk] = np.clip(((val * w[:, :, None]).sum(1) + 32768) // 65536, 0, 255)
        else:
            out[s:s + chunk] = (val * w[:, :, None]).sum(1)
    return out


def cube_read(path):
    """Read an Adobe/Resolve .cube 3D LUT as data (R fastest). Returns (n,n,n,3) indexed [r,g,b], domain."""
    size, lo, hi, rows = None, [0., 0, 0], [1., 1, 1], []
    for line in Path(path).read_text(errors='replace').splitlines():
        t = line.strip()
        if not t or t.startswith('#'):
            continue
        k = t.split()
        if k[0].upper() == 'LUT_3D_SIZE':
            size = int(k[1])
        elif k[0].upper() == 'DOMAIN_MIN':
            lo = [float(v) for v in k[1:4]]
        elif k[0].upper() == 'DOMAIN_MAX':
            hi = [float(v) for v in k[1:4]]
        elif k[0].upper() in ('TITLE', 'LUT_1D_SIZE', 'LUT_3D_INPUT_RANGE', 'LUT_1D_INPUT_RANGE'):
            if k[0].upper() == 'LUT_1D_SIZE':
                raise ValueError('1D LUT not supported')
        else:
            try:
                rows.append([float(v) for v in k[:3]])
            except ValueError:
                pass
    a = np.array(rows, float)
    assert size and len(a) == size ** 3, (path, size, len(a))
    # .cube: red index changes fastest -> reshape [b,g,r] then transpose to [r,g,b]
    return a.reshape(size, size, size, 3).transpose(2, 1, 0, 3), np.array(lo), np.array(hi)
