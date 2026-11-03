"""GR IV scene model with explicit numeric and MultiAxial hypotheses.

Numeric expressions use this repository's earlier independent derivations.
Downloaded implementations are never loaded or copied into this module.
"""
from pathlib import Path
from dataclasses import dataclass, asdict
from functools import lru_cache
import hashlib
import re
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np

MODES = {'standard': 'Standard', 'positive': 'Positive_Film', 'negative': 'Negative_Film'}


@lru_cache(maxsize=1)
def parameters():
    doc = rt.read('research/gr_firmware/data/gr4-1.11-tables.json')
    gamma = rt.read('research/gr_complete_pipeline/gr3_gr4_effective_curves.json')
    own = rt.read('research/gr_complete_pipeline/arm_color_analysis.json')['models']['gr4']['modes']
    tables = {t['id']: t for t in doc['tables']}
    for t in tables.values():
        fmt = t['format'].split(' x ', 1)[1]
        code = {'u8': 'B', 'u16LE': 'H', 'i16LE': 'h', 'u32LE': 'I', 'i32LE': 'i'}[fmt]
        raw = struct.pack('<' + code * len(t['values']), *t['values'])
        assert len(raw) == t['size'] and hashlib.sha256(raw).hexdigest() == t['sha256']
    blocks, families = {}, [[None] * 5 for _ in range(3)]
    for t in gamma['source_blocks']:
        raw = bytes.fromhex(t['bytes_hex'])
        assert len(raw) == t['size'] and hashlib.sha256(raw).hexdigest() == t['sha256']
        if t['model'] != 'gr4': continue
        blocks[t['meaning']] = raw
        m = re.fullmatch(r'base family (\d) band (\d)', t['meaning'])
        if m: families[int(m[1])][int(m[2])] = np.frombuffer(raw, '<u2').astype(int).tolist()
    text = rt.inp('artifacts/downloads/gr3-film-mods/repo/FINDINGS.md').read_text()
    match = re.search(r'edges ([0-9.,\s]+) deg; sector g', text)
    edges = np.fromstring(match.group(1).replace(',', ' '), sep=' ')
    assert len(edges) == 12
    result = dict(modes={}, gamma=dict(families=families,
        keys=list(struct.unpack('<9i', blocks['signed-key lookup'])),
        smoothing=list(struct.unpack('<97H', blocks['97x u16 transition smoothing'])),
        unit=struct.unpack('<H', blocks['normalization/anchor base unit'])[0]), edges=edges)
    names = {'standard': 'Standard', 'positive': 'Positive Film', 'negative': 'Negative Film'}
    gnames = {'standard': 'Standard', 'positive': 'PositiveFilm', 'negative': 'NegativeFilm'}
    for mode, prefix in MODES.items():
        def v(suffix): return tables[prefix + '-' + suffix]['values']
        ma = own[names[mode]]['MultiAxial']
        result['modes'][mode] = dict(look=v('look-matrix'), sensor=v('sensor-ccm'),
            saturation={str(i): v('saturation-' + ('+' if i >= 0 else '') + str(i)) for i in range(-4, 5)},
            ma=v('multiaxial-matrix-bank-0'), controls=v('multiaxial-controls'), ycc=v('multiaxial-ycc'),
            bounds=ma['bounds']['values'], selectors=ma['bank_indices']['values'],
            gamma_flags=v('gamma-descriptor')[1],
            sliders=next(t['sliders'] for t in gamma['effective_curves']
                         if t['model'] == 'gr4' and t['mode'] == gnames[mode]))
        assert result['modes'][mode]['ma'] == ma['matrix_bank']['values']
    rt.dump('parameters.json', result)
    return result


def blend(a, b, weight):
    return (a * weight + b * (512 - weight) + 256) >> 9


@lru_cache(maxsize=1024)
def gamma14(mode, gain, sliders_tuple=None):
    p = parameters()
    t = p['gamma']
    s = p['modes'][mode]['sliders']
    key, contrast, highlight, shadow = (s[k] for k in ('key', 'contrast', 'highlight', 'shadow')) if sliders_tuple is None else sliders_tuple
    gain = int(gain)
    if not 0 <= gain <= 65535 or any(not -4 <= k <= 4 for k in (key, contrast, highlight, shadow)):
        raise ValueError('gamma state outside source range')
    knee = max(128, min(2048, ((t['keys'][key + 4] * 2 * gain & 0xffffffff) >> 13)))
    low = 0 if knee <= 255 else 1 if knee < 512 else 2 if knee < 1024 else 3
    high, at = low + 1, knee >> 4
    target = (t['unit'] * 118) & 65535
    regions = []
    for adjustment in (highlight, 0, -shadow):
        k = max(-12, min(12, 2 * contrast + adjustment))
        a, b, w = (0, 1, k * 512 // 12) if k > 0 else (1, 2, (k + 12) * 512 // 12)
        yl = blend(t['families'][a][low][at], t['families'][b][low][at], w)
        yh = blend(t['families'][a][high][at], t['families'][b][high][at], w)
        bw = 512 if yl <= yh else 0 if yh >= target else ((target - yh) << 9) // (yl - yh)
        regions.append((a, b, w, bw))
    def value(region, i):
        a, b, w, bw = region
        return blend(blend(t['families'][a][low][i], t['families'][b][low][i], w),
                     blend(t['families'][a][high][i], t['families'][b][high][i], w), bw)
    out = []
    for i in range(256):
        x = i * 16
        mid, selected = value(regions[1], i), value(regions[2 if x <= knee else 0], i)
        y = mid
        if x > knee and highlight:
            if x >= knee * 4: y = selected
            else:
                w = t['smoothing'][max(0, min(96, i * 512 // knee - 32))]
                y = (selected * w + mid * (2048 - w) + 1024) >> 11
        if x < knee and shadow:
            if x <= knee // 4: y = selected
            else:
                w = t['smoothing'][max(0, min(96, knee * 32 // x - 32))]
                y = (selected * w + mid * (2048 - w) + 1024) >> 11
        out.append(min(16384, (y << 14) // (0x3f02 * (t['unit'] >> 6))))
    return np.asarray(out, np.int64)


@dataclass(frozen=True)
class Options:
    front: str = 'float'
    gamma: str = 'u14'
    regions: str = 'angles'
    level: str = 'first'
    zero_selector: str = 'matrix0'


def q13_matrix(matrix):
    q = np.floor(np.asarray(matrix) * 8192 + .5).astype(np.int64)
    for i in range(3): q[i, i] = 8192 - sum(q[i, j] for j in range(3) if i != j)
    return q


def front_matrix(mode, common, options):
    look = np.asarray(parameters()['modes'][mode]['look'], np.int64).reshape(3, 3)
    base = np.asarray(common['matrix_base'])
    if options.front == 'float': return look / 8192 @ base
    if options.front != 'integer': raise ValueError('unknown front matrix format')
    product = look @ q13_matrix(base) + 4096
    mixed = np.where(product >= 0, product // 8192, -((-product) // 8192))
    scaled = mixed * 128
    q = np.where(scaled >= 0, scaled // 4096, -((-scaled) // 4096))
    for i in range(3): q[i, i] = 256 - sum(q[i, j] for j in range(3) if i != j)
    return np.clip(q, -2048, 2047) / 256


def ma_active(mode):
    return parameters()['modes'][mode]['controls'][10:14] == [1024] * 4


def region_info(rgb, mode, options):
    p = parameters()['modes'][mode]
    coordinate = np.asarray(rgb) @ (np.asarray(p['ycc']).reshape(3, 3) / 256).T
    cb, cr = coordinate[..., 1], coordinate[..., 2]
    if options.regions == 'angles':
        angle = np.degrees(np.arctan2(cr, cb)) % 360
        e = np.asarray(parameters()['edges'])
        relative = (angle - e[0]) % 360
        group = np.clip(np.searchsorted((e - e[0]) % 360, relative, side='right') - 1, 0, 11)
    elif options.regions == 'native':
        quadrant = ((cr < 0) * 2 + np.where(cr >= 0, cb < 0, cb >= 0)).astype(int)
        ax = np.where((quadrant % 2) == 0, abs(cb), abs(cr))
        ay = np.where((quadrant % 2) == 0, abs(cr), abs(cb))
        thresholds = np.asarray(p['bounds']).reshape(4, 4)[quadrant]
        segment = np.sum(2048 * ax[..., None] < thresholds * (ax + ay)[..., None], axis=-1)
        group = np.asarray(p['selectors']).reshape(4, 5)[quadrant, segment]
    else: raise ValueError('unknown region model')
    if options.level == 'first': position = np.zeros_like(cb)
    else:
        scalar = coordinate[..., 0] if options.level == 'luminance' else abs(cb) + abs(cr)
        # Only the four nonzero upper anchors are taken from controls.
        # The origin and coordinate interpretation remain explicit hypotheses.
        knots = np.r_[0, np.asarray(p['controls'][5:9])] / 4095
        position = np.interp(np.clip(scalar, 0, 1), knots, np.arange(5))
    return group, position, coordinate


def multiaxial(rgb, mode, options):
    if not ma_active(mode): return rgb
    p = parameters()['modes'][mode]
    groups, position, _ = region_info(rgb, mode, options)
    bank = np.asarray(p['ma']).reshape(12, 5, 3, 3) / 1024
    lo = np.minimum(position.astype(int), 3)
    mix = (position - lo)[..., None, None]
    matrix = bank[groups, lo] * (1 - mix) + bank[groups, lo + 1] * mix
    output = np.einsum('...ij,...j->...i', matrix, rgb)
    if options.zero_selector == 'identity': output = np.where((groups == 0)[..., None], rgb, output)
    elif options.zero_selector != 'matrix0': raise ValueError('unknown zero selector model')
    return output


@lru_cache(maxsize=1024)
def gamma_table(mode, gain, kind, sliders_tuple=None):
    source = gamma14(mode, int(gain), sliders_tuple)
    if kind == 'u14': return np.arange(256) * 16., source / 16384
    nodes = np.minimum(source >> 4, 1023)
    if kind == 'u10': return np.arange(256) * 16., nodes / 1023
    if kind != 'increments': raise ValueError('unknown gamma numeric format')
    steps = np.clip(np.diff(nodes, append=nodes[-1]), 0, 240)
    fractions = np.arange(16)
    fine = nodes[:, None] + (steps[:, None] * fractions[None, :]) // 16
    return np.arange(4096, dtype=float), fine.reshape(-1) / 1023


def render(raw_wb, mode, common, options=Options(), sliders=None):
    p = parameters()['modes'][mode]
    source = np.asarray(raw_wb, float) * np.asarray(common['wb_correction'])
    z = (source @ front_matrix(mode, common, options).T) * 2 ** common['exposure_ev']
    z = multiaxial(z, mode, options)
    controls = None if sliders is None else tuple(sliders[k] for k in ('key', 'contrast', 'highlight', 'shadow'))
    x, y = gamma_table(mode, int(common['gain']), options.gamma, controls)
    output = np.interp(np.clip(z * 4095, 0, x[-1]), x, y)
    assert p['gamma_flags'] == 0
    sat = 0 if sliders is None else int(sliders.get('saturation', 0))
    if sat:
        q13 = np.asarray(p['saturation'][str(sat)], np.int64).reshape(3, 3)
        q9 = ((512 * q13 + 4096) >> 13) / 512
        output = output @ q9.T
    return np.clip(output, 0, 1)


def render_scene(scene_with_be, mode, common, options=Options(), sliders=None):
    raw = np.asarray(scene_with_be) @ np.linalg.inv(common['raw_wb_to_scene']).T
    return render(raw, mode, common, options, sliders)


def radial_gain(radius, common, xy=None):
    r = np.asarray(radius, float)
    kind = common.get('radial_kind', 'knots')
    if kind == 'knots': ev = np.interp(r, common['radius'], common['radial_ev'])
    else:
        if xy is not None and kind == 'poly_center':
            r = np.sqrt(np.sum((np.asarray(xy) - np.asarray(common['radial_center'])) ** 2, axis=-1))
        coeff = np.asarray(common['radial_coeff'])
        ev = np.stack([r ** (2 * (i + 1)) for i in range(len(coeff))], axis=-1) @ coeff
    return 2 ** ev


def source_gain(radius, source_sha256, common, xy=None):
    if source_sha256 not in common['chart_sources']:
        return np.ones_like(np.asarray(radius, float))
    return radial_gain(radius, common, xy)


def options_dict(options): return asdict(options)
