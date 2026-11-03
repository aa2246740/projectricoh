"""Exposed analytic stages for component projections and declared perturbations."""
from pathlib import Path
import copy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from scipy.optimize import brentq

MODES = {'01': 'positive', '02': 'negative'}


def common():
    return rt.read('research/gr4_analytic_target_r1/local/calibration/primary_pre_hard.json')['common']


def front(scene, mode, c):
    p = rt.sim.parameters()['modes'][mode]
    L = np.asarray(p['saturation']).reshape(3, 3) / 8192 @ (np.asarray(p['look']).reshape(3, 3) / 8192)
    z = np.asarray(scene) @ np.linalg.inv(c['raw_wb_to_scene']).T @ np.asarray(c['matrix']).T * 2 ** c['exposure_ev']
    return z, L


def tone(z, mode, c):
    return np.interp(np.clip(z * 4095, 0, 4080), np.arange(256) * 16, rt.sim.curve(mode, c['gain']))


def staged(scene, mode, c=None, options=None):
    c = common() if c is None else c
    options = rt.sim.Options() if options is None else options
    z, L = front(scene, mode, c)
    return np.clip(tone(rt.sim.multiaxial(z @ L.T, mode, options), mode, c), 0, 1)


def relative(base, standard, styled):
    cs, cm, cb = [np.hypot(a[..., 1], a[..., 2]) for a in (standard, styled, base)]
    active = (cs >= 8) & (cm >= 8) & (cb >= 8)
    ratio = np.ones(cs.shape, complex)
    np.divide(styled[..., 1] + 1j * styled[..., 2], standard[..., 1] + 1j * standard[..., 2], out=ratio, where=active)
    ab = (base[..., 1] + 1j * base[..., 2]) * ratio
    return np.stack([base[..., 0] + styled[..., 0] - standard[..., 0], ab.real, ab.imag], axis=-1)


VARIANTS = [
    'exposure_minus_quarter', 'exposure_plus_quarter',
    'gain6144_grey_locked', 'gain10240_grey_locked',
    'level1', 'level4', 'level_luminance', 'sectors_linear', 'ma_chroma_gate',
    'CCM_minus_2pct', 'CCM_plus_2pct', 'tone_minus_2codes', 'tone_plus_2codes',
    'front_Q8', 'final_YCC_round', 'relative_control', 'fuji_metering',
]


def render_variant(scene, mode, name, c=None):
    c = copy.deepcopy(common() if c is None else c)
    options = rt.sim.Options()
    if name.startswith('exposure_'):
        c['exposure_ev'] += -.25 if name == 'exposure_minus_quarter' else .25
    elif name.startswith('gain'):
        old = copy.deepcopy(c)
        c['gain'] = int(name.split('_')[0][4:])
        grey = np.full((1, 3), .18)
        target = float(rt.sim.render_scene(grey, 'standard', old).mean())
        start = c['exposure_ev']
        c['exposure_ev'] = brentq(lambda ev: float(rt.sim.render_scene(grey, 'standard', {**c, 'exposure_ev': ev}).mean()) - target,
            start - 3, start + 3, xtol=1e-12)
    elif name == 'level1': options = rt.sim.Options(level=1)
    elif name == 'level4': options = rt.sim.Options(level=4)
    elif name == 'sectors_linear': options = rt.sim.Options(sectors='linear')
    elif name == 'front_Q8': options = rt.sim.Options(quantize_front=True)
    elif name.startswith('CCM_'):
        D = np.array([[-1., 1., 0.], [0., -1., 1.], [1., 0., -1.]])
        Y = scene @ rt.cm.SRGB_XYZ[1]
        w = np.clip(Y / .5, 0, 1)
        sign = -1 if name == 'CCM_minus_2pct' else 1
        scene = scene + sign * .02 * w[:, None] * (scene @ D.T)
    if name in ('level_luminance', 'ma_chroma_gate'):
        z, L = front(scene, mode, c)
        x = z @ L.T
        a = rt.sim.multiaxial(x, mode, rt.sim.Options())
        if name == 'level_luminance':
            b = rt.sim.multiaxial(x, mode, rt.sim.Options(level=4))
            w = np.clip((x @ np.array([.299, .587, .114])) / .5, 0, 1)
            a = a * (1 - w[:, None]) + b * w[:, None]
        else:
            q = np.asarray(rt.sim.parameters()['modes'][mode]['ycc']).reshape(3, 3) / 256
            cc = x @ q.T
            w = np.clip(np.hypot(cc[:, 1], cc[:, 2]) / .05, 0, 1)
            a = x * (1 - w[:, None]) + a * w[:, None]
        return np.clip(tone(a, mode, c), 0, 1)
    out = rt.sim.render_scene(scene, mode, c, options)
    if name.startswith('tone_'):
        sign = -1 if name == 'tone_minus_2codes' else 1
        out = np.clip(out + sign * 2 / 255 * np.sin(np.pi * out), 0, 1)
    if name == 'final_YCC_round':
        ycc = np.column_stack([out @ np.array([.299, .587, .114]), out @ np.array([-.168736, -.331264, .5]) + .5,
            out @ np.array([.5, -.418688, -.081312]) + .5])
        ycc = np.floor(ycc * 255 + .5) / 255
        cb, cr = ycc[:, 1] - .5, ycc[:, 2] - .5
        out = np.clip(np.column_stack([ycc[:, 0] + 1.402 * cr,
            ycc[:, 0] - .344136 * cb - .714136 * cr, ycc[:, 0] + 1.772 * cb]), 0, 1)
    return out
