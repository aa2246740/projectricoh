"""Shared helpers for the fotufilm bake: paths, raw image I/O, the sandboxed CLI, colour maths."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
CUBES = LOCAL / 'cubes'
W = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/fotufilm')
WORK = W / 'work'
FOTUFILM = W / 'build/release/fotufilm'
RUN = W / 'sb/run.sh'
IMGIO = W / 'bin/imgio'
CAPTURES = ROOT / 'captures/street-g137-20261031/jpg'
N = 33


def check_paths(*paths):
    for p in paths:
        p = Path(p).resolve()
        if not (p.is_relative_to(LOCAL) or p.is_relative_to(W)):
            raise PermissionError(f'write outside fence: {p}')


def read_u16(path):
    raw = Path(path).read_bytes()
    if raw[:4] != b'U16R':
        raise ValueError(f'not U16R: {path}')
    w, h, c = np.frombuffer(raw[4:16], '<u4')
    return np.frombuffer(raw[16:], '<u2').reshape(h, w, c).astype(np.float64) / 65535


def write_u16(path, img):
    check_paths(path)
    img = np.asarray(img)
    h, w, _ = img.shape
    q = np.clip(np.rint(img * 65535), 0, 65535).astype('<u2')
    Path(path).write_bytes(b'U16R' + np.array([w, h, 3], '<u4').tobytes() + q.tobytes())


def decode_image(src, dst_u16):
    """Pixels exactly as stored in the file (no colour conversion), via ImageIO."""
    check_paths(dst_u16)
    out = subprocess.run([str(IMGIO), 'decode', str(src), str(dst_u16)], check=True,
                         capture_output=True, text=True).stdout.strip()
    return read_u16(dst_u16), out


def encode_png(img, png, space='srgb'):
    check_paths(png)
    tmp = Path(str(png) + '.u16')
    write_u16(tmp, img)
    subprocess.run([str(IMGIO), 'encode', str(tmp), str(png), space], check=True)
    tmp.unlink()


def fotufilm(args, timeout=1800):
    """Run the CLI only inside the sandbox profile (no network, writes only under Scratch)."""
    cmd = [str(RUN), str(FOTUFILM), *map(str, args)]
    r = subprocess.run(cmd, cwd=WORK, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f'fotufilm failed ({r.returncode}): {" ".join(map(str, args))}\n{r.stderr[-2000:]}')
    return r.stdout


# --- colour -------------------------------------------------------------------------------
SRGB_TO_XYZ = np.array([[0.4123908, 0.3575843, 0.1804808],
                        [0.2126390, 0.7151687, 0.0721923],
                        [0.0193308, 0.1191948, 0.9505322]])
P3_TO_XYZ = np.array([[0.4865709, 0.2656677, 0.1982173],
                      [0.2289746, 0.6917385, 0.0792869],
                      [0.0000000, 0.0451134, 1.0439444]])
P3_TO_SRGB = np.linalg.solve(SRGB_TO_XYZ, P3_TO_XYZ)
WHITE = SRGB_TO_XYZ.sum(1)


def eotf(v):
    v = np.asarray(v, float)
    return np.where(v <= 0.04045, v / 12.92, ((np.maximum(v, 0) + 0.055) / 1.055) ** 2.4)


def oetf(v):
    v = np.clip(np.asarray(v, float), 0, 1)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055)


def p3_to_srgb_codes(p3):
    """Display P3 code values -> sRGB code values, out-of-gamut clipped in linear light."""
    return oetf(eotf(p3) @ P3_TO_SRGB.T)


def lab(codes, space='srgb'):
    m = P3_TO_XYZ if space == 'p3' else SRGB_TO_XYZ
    xyz = (eotf(codes) @ m.T) / WHITE
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


def write_cube(path, table, title, comments):
    check_paths(path)
    n = table.shape[0]
    lines = [f'# {c}' for c in comments] + [f'TITLE "{title}"', f'LUT_3D_SIZE {n}',
                                            'DOMAIN_MIN 0.0 0.0 0.0', 'DOMAIN_MAX 1.0 1.0 1.0']
    rows = np.clip(table.reshape(-1, 3), 0, 1)
    lines += [f'{r:.6f} {g:.6f} {b:.6f}' for r, g, b in rows]
    Path(path).write_text('\n'.join(lines) + '\n')


def read_cube_table(path):
    n, rows = None, []
    for line in Path(path).read_text().splitlines():
        s = line.split('#', 1)[0].strip()
        if not s:
            continue
        if s.startswith('LUT_3D_SIZE'):
            n = int(s.split()[1])
        elif s[0].isdigit() or s[0] in '-.':
            rows.append([float(t) for t in s.split()])
    return np.asarray(rows).reshape(n, n, n, 3)


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
