"""Numerical adapter using archived source and read-only local artifacts."""
from runtime_std import *
import struct
import types

sys.path.insert(0, str(SOURCE / 'studio_snapshot/src'))
import numpy as np
from gxr_studio.engine import colour as fs
from gxr_studio.engine import matrix_model as mm
from gxr_studio.engine.model import Model
from gxr_studio.camdata.datcodec import parse
from gxr_studio.engine.colour import lab_from_codes, delta_e00, de00_components

_models = {}
sys.path.insert(0, str(ROOT/'research/module_adapt'))
from c040 import geometry_mode, module_spec, input_map_path


def to_words(Zrow, ctx):
    """Exact quantizer from the frozen research fit_sectors.py:910-916."""
    P = Zrow * ctx.S_eff * 32
    A = np.clip(np.rint(P.real - ctx.d0), -127, 127).astype(int)
    B = np.clip(np.rint(-P.imag - ctx.d1), -127, 127).astype(int)
    clipped = (np.abs(np.rint(P.real - ctx.d0)) > 127) | (np.abs(np.rint(-P.imag - ctx.d1)) > 127)
    return A, B, clipped


fs.to_words = to_words


def stats(values):
    v = np.asarray(values, float).ravel()
    assert np.isfinite(v).all()
    if not len(v):
        return dict(n=0, median=None, p95=None, max=None, mean=None)
    return dict(n=len(v), median=float(np.median(v)), p95=float(np.percentile(v, 95)),
                max=float(v.max()), mean=float(v.mean()))


def score(base, prediction, desired):
    err = delta_e00(lab_from_codes(prediction), lab_from_codes(desired))
    den = delta_e00(lab_from_codes(base), lab_from_codes(desired))
    median = float(np.median(den))
    return dict(label='电脑预测', de00=stats(err), baseline_de00=stats(den),
        similarity_percent=None if median < .25 else 100 * (1 - float(np.median(err)) / median))


def source_copy(rel):
    source, destination = ROOT / rel, SOURCE / rel
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    assert sha(source) == sha(destination), 'Input source changed: ' + rel
    return destination


def camera_model(ui=0, transferred=False, iso=200, *, geometry=None):
    """Native unit model; transferred=True explicitly retains the whole 50mm comparator."""
    model_iso = 1600 if iso >= 566 else 200
    geometry = geometry_mode('legacy50' if transferred and geometry is None else geometry)
    key = ui, transferred, model_iso, geometry
    if key not in _models:
        cp = source_copy(f'research/color_fit_v2/06_classic_neg/round4/local/cache/data_{model_iso}.npz')
        rp = source_copy('research/hue_ring/local/'+('ring_model_v2_iso1600.json' if model_iso == 1600 else 'ring_model_v2.json'))
        with np.load(cp, allow_pickle=False) as z:
            stock, d0, d1 = (z[k].copy() for k in ('stock', 'd0', 'd1'))
        dat = release_dat()
        if not transferred:
            official = read(source_copy('research/module_adapt/local/official_parameters.json'))['units']
            data = official[('50mm', '28mm', 'mount')[ui]]
            display = read(source_copy('research/stage2e_verification/local/measurements.json'))['frames']['R8051160']['meta']['display']
            d0, d1 = np.zeros(24), np.zeros(24)
            for i, color in enumerate(('orange', 'green', 'blue', 'red', 'magenta')):
                selected = np.array([bool(int(data['mask'][i]) & (1 << j)) for j in range(24)])
                level = int(display[color + '_hue']) - 1
                d0[selected] = np.asarray(data['d0_levels'])[level, selected]
                d1[selected] = np.asarray(data['d1_levels'])[level, selected]
                assert data['vividness_levels'][int(display['vividness'])-1] == 100
                assert data['sat_levels'][int(display[color+'_saturation'])-1] == 100 or np.all(np.asarray(data['sat_levels'])[int(display[color+'_saturation'])-1, selected] == 100)
            entry = dat.entry_of(ui, 4)
            stock = np.array([fs.decode_word(entry[115+i*4:119+i*4]) for i in range(24)])
        unit = ('a12-50', 'a12-28', 'mount-a12')[ui]
        _models[key] = Model(stock, d0, d1, module_spec(read(rp), unit, geometry))
    return _models[key]


def release_dat():
    if not hasattr(release_dat, 'cached'):
        path = source_copy('firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT')
        release_dat.cached = parse(path.read_bytes())
    return release_dat.cached


class Camera:
    def __init__(self, ui=0, transferred=False, *, geometry=None):
        self.model = camera_model(ui, transferred, geometry=geometry)
        self.E = self.model.engine
        self.mm, self.fs = mm, fs
        self.entry = release_dat().entry_of(ui, 4)
        self.row = mm.MatrixRow.from_bytes(self.entry[216:244])
        self.curve = mm.Curve([0, *struct.unpack_from('>31H', self.entry, 20), 4095], list(self.entry[82:115]))
        self.A, self.B = np.array([fs.decode_word(self.entry[i:i+4]) for i in range(115, 211, 4)]).T
        self.initial_z = fs.Z_of_words(self.A, self.B, self.E.ctx)
        self.anchor = read(source_copy('research/color_fit_v2/05_classic_chrome/round4/local/fit_v4_noT1.json'))['anchor']
        self.ui = ui

    def stock(self, x):
        return self.model.predict(self.entry, x)

    def xyz(self, x, neutral, matrix):
        u, f = self.anchor['u_m'], self.anchor['f']
        neutral, matrix = np.asarray(neutral), np.asarray(matrix)
        white = neutral @ matrix.T
        return ((np.asarray(x)/4095-f)*neutral) @ matrix.T * (.18/((u-f)*white[1]))


def load_fit_helpers():
    # The copied fit module only imports these narrow helpers from its old host.
    guard = types.ModuleType('guard')
    guard.LOCAL, guard.dump = LOCAL, dump
    guard.output_path = lambda p: LOCAL / p
    sys.modules['guard'] = guard
    safety = module('redo_safety', source_copy('research/closed_loop/local/vendor/safety.py'))
    safety.fs = fs
    common = types.ModuleType('common')
    common.helper = lambda name: safety if name == 'safety' else (_ for _ in ()).throw(KeyError(name))
    sys.modules['common'] = common
    legacy = module('redo_legacy_fit', SOURCE / 'research/film_look_routes/fit.py')
    return legacy.Problem, legacy.weights


LegacyProblem, weights = load_fit_helpers()


def arrays(path):
    p = Path(path).resolve()
    for unit in ('a12-28', 'mount-a12'):
        definition = None
        if p.is_relative_to(LOCAL/'inputs'/unit):
            definition = LOCAL/'inputs'/unit/'definition.json'
        elif p.is_relative_to(LOCAL/'targets'/unit) and p.name[:2].isdigit():
            definition = p.parent/(p.name[:2]+'.json')
        if definition is not None and definition.is_file():
            actual = read(definition).get('c040_geometry', 'legacy50')
            if actual != geometry_mode():
                raise ValueError('C040/input model mismatch: rebuild inputs and targets for '+unit+
                    ', or explicitly use GXR_C040_GEOMETRY=legacy50 for the frozen old study')
    with np.load(path, allow_pickle=False) as z:
        return dict(z)


def calibration_apply(raw_wb, coefficients):
    raw_wb = np.asarray(raw_wb, float)
    C = np.asarray(coefficients)
    H = np.c_[np.ones(len(raw_wb)), raw_wb]
    if len(C) == 10:
        r, g, b = raw_wb.T
        H = np.c_[H, r*r, g*g, b*b, r*g, r*b, g*b]
    assert H.shape[1] == len(C)
    return 4095 * (raw_wb + H @ C)
