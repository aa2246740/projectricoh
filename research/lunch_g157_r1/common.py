"""Read-only g157 lunch research. Run every entry point with Python -I -B, nice 15."""
from pathlib import Path
import os
import sys

assert sys.flags.isolated, 'Run Python -I -B'
sys.dont_write_bytecode = True
assert os.getpriority(os.PRIO_PROCESS, 0) == 15, 'Run with nice -n 15 exactly once'
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS',
            'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['GXR_C040_GEOMETRY'] = 'native'
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOCAL = HERE / 'local'
PHOTOS = ROOT / 'captures/g157-lunch-20261105'
DAT = ROOT / 'firmware/package_v310_g157_test/local/SD_ROOT/GXRCE.DAT'
DAT_SHA = '2b8904592ce56ab03649ced52c8479b0bbac4e45bf9a47505d220795bb3ec56c'
SNAP = ROOT / 'research/recipe_redo_r1/local/source/studio_snapshot/src'
LOCAL.mkdir(exist_ok=True)
os.environ.update(TMPDIR=str(LOCAL), MPLCONFIGDIR=str(LOCAL / 'mpl'))

import ast
import datetime
import hashlib
import importlib.util
import io
import json
import math
import struct
import time


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def plain(v):
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if isinstance(v, Path):
        return str(v)
    if hasattr(v, 'tolist'):
        return plain(v.tolist())
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def dump(path, value):
    p = Path(path)
    if not p.is_absolute():
        p = LOCAL / p
    assert p.resolve().is_relative_to(LOCAL)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_name(p.name + f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(p)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def admit(label):
    queued = os.environ.get('LUNCH_QUEUE_ADMISSION')
    if queued:
        proof = read(queued)
        assert proof['parent_pid'] == os.getppid() and proof['label'] == label
        assert proof['admit'] and proof['cap'] > proof['running_before']
        dump(f'admissions/{label}-{os.getpid()}.json', dict(utc=utc(), nice=15,
             queue_admission=proof, queue_owns_gate=True))
        return 1
    sys.path.insert(0, str(ROOT / 'tools'))
    import loadgate
    count, info = loadgate.workers()
    dump(f'admissions/{label}-{os.getpid()}.json', dict(utc=utc(), nice=15, **info))
    if count == 0:
        print('DEFER', label, json.dumps(info), flush=True)
        raise SystemExit(75)
    return count


def fence(event, args):
    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo', 'subprocess.Popen',
                 'os.system', 'os.posix_spawn'):
        raise PermissionError('No network, device, or subprocess access in numerical jobs')
    mutations = []
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        p = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        if str(p).startswith('/dev/') and str(p) not in ('/dev/null', '/dev/urandom', '/dev/random'):
            raise PermissionError('No device access')
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            mutations = [p]
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime', 'os.truncate'):
        mutations = [args[0]]
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        mutations = args[:2]
    for p in mutations:
        if not isinstance(p, (str, bytes, Path)):
            continue
        p = Path(os.fsdecode(p)).resolve()
        if event == 'os.mkdir' and p.is_dir():
            continue
        if not p.is_relative_to(LOCAL):
            raise PermissionError('Write outside lunch local/: ' + str(p))


def numerical():
    global np, Image, Dng, scene_colour, fs, mm, Model, cm, module_spec, Cube, Target, xyz_to_encoded
    import numpy as np
    from PIL import Image
    sys.path.insert(0, str(SNAP))
    from gxr_studio.raw.dng import Dng
    from gxr_studio.lut.scene import scene_colour
    from gxr_studio.engine import colour as fs, matrix_model as mm
    from gxr_studio.engine.model import Model
    from gxr_studio.lut.cube import Cube
    from gxr_studio.lut.spaces import Target, xyz_to_encoded
    sys.path.insert(0, str(ROOT / 'research/module_adapt'))
    from c040 import module_spec
    cm = module('lunch_colour_math', ROOT / 'research/color_references/colour_math.py')


def metadata_reader():
    source = ROOT / 'research/recipe_redo_r1/inventory.py'
    tree = ast.parse(source.read_text())
    keep = []
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in (
                'TYPES', 'DISPLAY', 'SELECTORS') for t in n.targets):
            keep.append(n)
        if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in (
                'Tiff', 'jpeg_tiff', 'scalar', 'metadata'):
            keep.append(n)
    scope = dict(struct=struct, io=io, Path=Path)
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(source), 'exec'), scope)
    return scope['metadata']


def stats(values):
    v = np.asarray(values, float).ravel()
    assert np.isfinite(v).all()
    if not len(v):
        return dict(n=0, median=None, p95=None, mean=None, max=None)
    return dict(n=len(v), median=float(np.median(v)), p95=float(np.percentile(v, 95)),
                mean=float(v.mean()), max=float(v.max()))


def lab(rgb, white='D50'):
    if white == 'D50':
        return cm.rgb_lab(np.asarray(rgb) / 255)
    return fs.lab_from_codes(rgb)


def de(a, b, white='D50'):
    return cm.delta_e00(lab(a, white), lab(b, white))


def input_codes(raw):
    C = np.asarray(read(ROOT / 'research/model_c040_r1/local/calibration/input-map-mount-a12.json')['coefficients'])
    u = np.asarray(raw) / 4095
    H = np.c_[np.ones(len(u)), u]
    if len(C) == 10:
        r, g, b = u.T
        H = np.c_[H, r*r, g*g, b*b, r*g, r*b, g*b]
    return raw + 4095 * (H @ C)


_models = {}


def camera_model(iso, raw13):
    branch = 200 if iso < 566 else 1600
    key = (branch, tuple(raw13))
    if key not in _models:
        official = read(ROOT / 'research/module_adapt/local/official_parameters.json')['units']['mount']
        display = {v: i for i, v in enumerate((0, 7, 6, 1, 2, 3, 4, 5, 8, 9))}
        levels = [display[v] for v in raw13]
        d0, d1 = np.zeros(24), np.zeros(24)
        for j in range(5):
            ix = np.array([bool(int(official['mask'][j]) & (1 << s)) for s in range(24)])
            d0[ix] = np.asarray(official['d0_levels'])[levels[8+j]-1, ix]
            d1[ix] = np.asarray(official['d1_levels'])[levels[8+j]-1, ix]
            sat = np.broadcast_to(np.asarray(official['sat_levels'])[levels[3+j]-1], (24,))
            assert np.all(sat[ix] == 100), 'Nondefault five-colour saturation'
        assert official['vividness_levels'][levels[2]-1] == 100, 'Nondefault vividness'
        stock_entry = (LOCAL / 'records/04_Std.record552').read_bytes()
        stock = np.array([fs.decode_word(stock_entry[o:o+4]) for o in range(115, 211, 4)])
        ring = read(ROOT / 'research/hue_ring/local' / ('ring_model_v2.json' if branch == 200 else 'ring_model_v2_iso1600.json'))
        _models[key] = Model(stock, d0, d1, module_spec(ring, 'mount-a12', 'native'))
    return _models[key]


def predict(model, entry, x):
    # Same explicit Standard route as native-C040 recipe-redo. Native BW discards chroma.
    return model.predict(entry, x, quantize=False,
                         bw_chroma='discard' if entry[0] == 3 else 'conditional')


def save_jpeg(path, rgb):
    p = Path(path)
    assert p.resolve().is_relative_to(LOCAL)
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(np.rint(rgb), 0, 255).astype(np.uint8)).save(p, quality=95, subsampling=0)


def decision(phase, what, why, evidence, result):
    p = LOCAL / 'decisions.tsv'
    if not p.exists():
        p.write_text('ts\tphase\tdecision\twhy\tevidence\tresult\n')
    values = [utc(), phase, what, why, evidence, result]
    with p.open('a') as f:
        f.write('\t'.join(str(v).replace('\t', ' ').replace('\n', ' ') for v in values) + '\n')
