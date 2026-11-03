"""Source-aware input normalization. The analytic pixel function stays frozen."""
from pathlib import Path
from functools import lru_cache
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import pipeline as pp


@lru_cache(maxsize=1)
def chart_sources():
    audit = rt.read('research/gr4_analytic_target_r1/local/dense_audit.json')
    return frozenset(row['dng_sha256'] for row in audit)


def radial_factor(radius, source_sha256, common):
    # No camera-model, filename or user label can grant the chart-only correction.
    if source_sha256 is not None and not re.fullmatch('[0-9a-f]{64}', source_sha256):
        raise ValueError('source must be an exact SHA256 digest or None')
    if source_sha256 not in chart_sources():
        return np.ones_like(np.asarray(radius, float))
    radius = np.asarray(radius, float)
    if not np.isfinite(radius).all() or np.any((radius < 0) | (radius > 1)):
        raise ValueError('chart radius must be finite and between zero and one')
    return 2 ** np.interp(radius, common['radius'], common['radial_ev'])


def scene_from_raw(raw_wb, raw_wb_to_scene_without_BE, baseline_exposure):
    """Apply the source DNG BaselineExposure once, before the scene API."""
    raw = np.asarray(raw_wb, float)
    matrix = np.asarray(raw_wb_to_scene_without_BE, float)
    be = np.asarray(baseline_exposure, float)
    if raw.shape[-1:] != (3,) or matrix.shape != (3, 3):
        raise ValueError('RGB samples and one 3x3 colorimetric matrix required')
    if not (np.isfinite(raw).all() and np.isfinite(matrix).all() and np.isfinite(be).all()):
        raise ValueError('nonfinite DNG input')
    return (raw @ matrix.T) * np.expand_dims(2 ** be, -1)


def render_scene(scene_with_BE, mode, radius=0., source_sha256=None, common=None):
    """Scene input already includes BE; this API deliberately takes no BE argument."""
    c = pp.common() if common is None else common
    scene = np.asarray(scene_with_BE, float)
    if scene.shape[-1:] != (3,) or not np.isfinite(scene).all():
        raise ValueError('finite scene-linear RGB required')
    factor = radial_factor(radius, source_sha256, c)
    return rt.sim.render_scene(scene * np.expand_dims(factor, -1), mode, c)


def render_template_camera(raw_wb, baseline_exposure, mode, radius=0., source_sha256=None, common=None):
    """GR IV template-camera RGB; normalize BE to the fixed training template once."""
    c = pp.common() if common is None else common
    raw = np.asarray(raw_wb, float)
    be = np.asarray(baseline_exposure, float)
    if raw.shape[-1:] != (3,) or not (np.isfinite(raw).all() and np.isfinite(be).all()):
        raise ValueError('finite camera RGB and BaselineExposure required')
    factor = radial_factor(radius, source_sha256, c) * 2 ** (be - c['template_baseline_exposure'])
    return rt.sim.render(raw * np.expand_dims(factor, -1), mode, c)
