"""Shared helpers for the spektrafilm bake: paths, the sandboxed renderer, photo/DNG inputs, colour maths."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
CUBES = LOCAL / 'cubes'
W = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/spektrafilm')
WORK = W / 'work'
PY = W / 'venv/bin/python'
RUN = W / 'sb/run.sh'
RENDER = HERE / 'render.py'
JPG = ROOT / 'captures/street-g137-20261031/jpg'
DNG = ROOT / 'captures/street-g137-20261031/dng'
PHOTOS = ['R8051530', 'R8051554', 'R8051570', 'R8051586', 'R8051594', 'R8051610']
FULL = ['R8051530', 'R8051586']
DNGS = ['R8051530', 'R8051533', 'R8051562', 'R8051577', 'R8051644', 'R8051685']
VARIANTS = ('srgb', 'srgbmid', 'vlog', 'vlog65')
RES = {'srgb': 33, 'srgbmid': 33, 'vlog': 33, 'vlog65': 65}
N = 33


def check_paths(*paths):
    for p in paths:
        p = Path(p).resolve()
        if not (p.is_relative_to(LOCAL) or p.is_relative_to(W)):
            raise PermissionError(f'write outside fence: {p}')


def spk(*args, timeout=1800):
    """Run render.py only inside the sandbox (no network, writes only under Scratch), as `python -I`."""
    cmd = [str(RUN), str(PY), '-I', str(RENDER), *map(str, args)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f'render.py failed ({r.returncode}): {" ".join(map(str, args))}\n{r.stderr[-2000:]}')
    return json.loads(r.stdout.strip().splitlines()[-1])


# --- inputs -------------------------------------------------------------------------------
def load_jpeg(path):
    from PIL import Image
    im = Image.open(path)
    assert im.mode == 'RGB', im.mode
    return np.asarray(im, np.float64) / 255


def box(img, f):
    h, w, _ = img.shape
    return img[:h // f * f, :w // f * f].reshape(h // f, f, w // f, f, 3).mean((1, 3))


def load_photos():
    """1/8-size 8-bit codes of the six JPEGs, and 1/4-size frames of two of them (sRGB codes, no conversion)."""
    small, full = {}, {}
    for n in PHOTOS:
        im = load_jpeg(JPG / f'{n}.JPG')
        small[n] = np.rint(box(im, 8) * 255) / 255
        if n in FULL:
            full[n] = np.rint(box(im, 4) * 255) / 255
    return small, full


ZERO_DENOMINATOR_TAGS = set()


def _ifd_zero_safe(self, offset, endian=None):
    """analyze_capture.Tiff.ifd with one change: a RATIONAL with a 0 denominator reads as 0.0 (the street DNGs
    carry one in an EXIF tag; the original raises ZeroDivisionError). Tags hit are logged."""
    import struct
    e = endian or self.endian
    count = struct.unpack_from(e + 'H', self.data, offset)[0]
    assert 0 <= offset < len(self.data) and offset + 2 + 12 * count + 4 <= len(self.data)
    result = {}
    for i in range(count):
        p = offset + 2 + i * 12
        tag, typ, n = struct.unpack_from(e + 'HHI', self.data, p)
        if typ not in self.TYPES:
            continue
        fmt, size = self.TYPES[typ]
        length = n * size
        o = p + 8 if length <= 4 else struct.unpack_from(e + 'I', self.data, p + 8)[0]
        assert o + length <= len(self.data), (tag, o, length)
        raw = self.data[o:o + length]
        if typ == 2:
            value = raw.rstrip(b'\0 ').decode('ascii', errors='replace')
        elif fmt is None:
            value = raw
        elif typ in [5, 10]:
            a = struct.unpack(e + fmt * n, raw)
            if any(a[j + 1] == 0 for j in range(0, len(a), 2)):
                ZERO_DENOMINATOR_TAGS.add(tag)
            value = [a[j] / a[j + 1] if a[j + 1] else 0.0 for j in range(0, len(a), 2)]
        else:
            value = list(struct.unpack(e + fmt * n, raw))
        result[tag] = {'offset': o, 'raw': raw, 'value': value, 'type': typ, 'count': n}
    return result


def dng_scene_xyz(camera, path, width):
    """camera.scene() without its captures/a12-50 restriction or cache: sparse 2x2 CFA means, per-DNG white
    matrix, the fixed 50mm meter anchor (camera.xyz). Scene-referred XYZ, D65, middle grey ~0.18."""
    camera.dng.analyze_capture().Tiff.ifd = _ifd_zero_safe
    d = camera.dng.Dng(path)
    col = camera.dng.DngColour(d)
    white, _ = camera.dng.as_shot_white(d, col)
    M = col.camera_to_xyz(white)
    neutral = d.as_shot_neutral
    y0, x0, h, w = d.crop_window()
    nh = max(1, round(h * width / w))
    ys = y0 + 2 * np.linspace(0, (h - 2) // 2, nh).astype(int)
    xs = x0 + 2 * np.linspace(0, (w - 2) // 2, width).astype(int)
    yy, xx = np.meshgrid(ys, xs, indexing='ij')
    raw, counts = np.zeros((nh, width, 3)), np.zeros((nh, width, 3))
    clipped = np.zeros((nh, width), bool)
    for dy in (0, 1):
        for dx in (0, 1):
            color = d.cfa_at(yy + dy, xx + dx)
            signal = d.normalised_at(yy + dy, xx + dx)
            clipped |= signal >= .98
            for ch in range(3):
                mask = color == ch
                raw[:, :, ch] += signal * mask
                counts[:, :, ch] += mask
    x = raw / counts / neutral * 4095
    return camera.xyz(x, neutral, M), clipped


def xyz_to_vlog(xyz):
    from spaces import encode, matrix
    return np.clip(encode(np.asarray(xyz) @ np.linalg.inv(matrix('vgamut')).T, 'vlog'), 0, 1)


def as_image(flat, cols=1024):
    pad = (-len(flat)) % cols
    return np.concatenate([flat, np.zeros((pad, 3))]).reshape(-1, cols, 3)


# --- colour -------------------------------------------------------------------------------
SRGB_TO_XYZ = np.array([[0.4123908, 0.3575843, 0.1804808],
                        [0.2126390, 0.7151687, 0.0721923],
                        [0.0193308, 0.1191948, 0.9505322]])
WHITE = SRGB_TO_XYZ.sum(1)


def eotf(v):
    v = np.asarray(v, float)
    return np.where(v <= 0.04045, v / 12.92, ((np.maximum(v, 0) + 0.055) / 1.055) ** 2.4)


def oetf(v):
    v = np.clip(np.asarray(v, float), 0, 1)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055)


def lab(codes):
    xyz = (eotf(codes) @ SRGB_TO_XYZ.T) / WHITE
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def de00(a, b):
    L1, a1, b1 = np.moveaxis(a, -1, 0)
    L2, a2, b2 = np.moveaxis(b, -1, 0)
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dh = h2p - h1p
    dh = np.where(C1p * C2p == 0, 0, np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh)))
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh) / 2)
    Lm, Cmp = (L1 + L2) / 2, (C1p + C2p) / 2
    hs = h1p + h2p
    hm = np.where(C1p * C2p == 0, hs,
                  np.where(abs(h1p - h2p) <= 180, hs / 2, np.where(hs < 360, (hs + 360) / 2, (hs - 360) / 2)))
    T = (1 - 0.17 * np.cos(np.radians(hm - 30)) + 0.24 * np.cos(np.radians(2 * hm))
         + 0.32 * np.cos(np.radians(3 * hm + 6)) - 0.20 * np.cos(np.radians(4 * hm - 63)))
    dtheta = 30 * np.exp(-((hm - 275) / 25) ** 2)
    Rc = 2 * np.sqrt(Cmp ** 7 / (Cmp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lm - 50) ** 2 / np.sqrt(20 + (Lm - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cmp, 1 + 0.015 * Cmp * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def dE(a, b):
    return de00(lab(a), lab(b))


# --- LUT ----------------------------------------------------------------------------------
def grid_codes(n=N):
    """Node codes in .cube order (R fastest, then G, then B): shape (n**3, 3)."""
    v = np.linspace(0, 1, n)
    b, g, r = np.meshgrid(v, v, v, indexing='ij')
    return np.stack([r, g, b], -1).reshape(-1, 3)


def apply_lut(table, rgb, method='tetrahedral'):
    """table: (n,n,n,3) indexed [b,g,r]; rgb in [0,1]."""
    n = table.shape[0]
    x = np.clip(np.asarray(rgb, float).reshape(-1, 3), 0, 1) * (n - 1)
    base = np.minimum(x.astype(int), n - 2)
    f = x - base
    at = lambda c: table[c[:, 2], c[:, 1], c[:, 0]]
    if method == 'trilinear':
        out = 0
        for dr in (0, 1):
            for dg in (0, 1):
                for db in (0, 1):
                    w = ((f[:, 0] if dr else 1 - f[:, 0]) * (f[:, 1] if dg else 1 - f[:, 1])
                         * (f[:, 2] if db else 1 - f[:, 2]))
                    out = out + w[:, None] * at(base + np.array([dr, dg, db]))
        return out.reshape(np.shape(rgb))
    order = np.argsort(-f, axis=1, kind='stable')
    idx = np.arange(len(x))
    b = base.copy()
    v0 = at(b)
    b[idx, order[:, 0]] += 1
    v1 = at(b)
    b[idx, order[:, 1]] += 1
    v2 = at(b)
    b[idx, order[:, 2]] += 1
    v3 = at(b)
    u = np.take_along_axis(f, order, axis=1)
    out = v0 + u[:, 0, None] * (v1 - v0) + u[:, 1, None] * (v2 - v1) + u[:, 2, None] * (v3 - v2)
    return out.reshape(np.shape(rgb))


def read_cube(path):
    """(header comment lines, data lines, table[b,g,r,3])."""
    head, body, n, rows = [], [], None, []
    for line in Path(path).read_text().splitlines():
        if line.startswith('#'):
            head.append(line)
            continue
        body.append(line)
        s = line.strip()
        if s.startswith('LUT_3D_SIZE'):
            n = int(s.split()[1])
        elif s and (s[0].isdigit() or s[0] in '-.'):
            rows.append([float(t) for t in s.split()])
    return head, body, np.asarray(rows).reshape(n, n, n, 3)


def read_cube_table(path):
    return read_cube(path)[2]


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def dump(path, value):
    check_paths(path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n')


def stats(e):
    e = np.asarray(e).ravel()
    return {'median': float(np.median(e)), 'p95': float(np.percentile(e, 95)),
            'p99': float(np.percentile(e, 99)), 'max': float(e.max()), 'mean': float(e.mean())}


def r3(d):
    return {k: round(v, 3) for k, v in d.items()}
