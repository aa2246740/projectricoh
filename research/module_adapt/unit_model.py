"""Three module variants of the measured 50mm forward chain. Host research only."""
import copy
import sys
from pathlib import Path
from types import SimpleNamespace
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import support as s
from c040 import geometry_mode, module_spec

COLORS = ('orange', 'green', 'blue', 'red', 'magenta')


def modifiers(data, display):
    d0 = np.zeros(24)
    d1 = np.zeros(24)
    sat = np.full(24, 100.)
    for i, color in enumerate(COLORS):
        selected = np.array([bool(int(data['mask'][i]) & (1 << j)) for j in range(24)])
        hue_level = int(display[color+'_hue'])-1
        sat_level = int(display[color+'_saturation'])-1
        # The shipped masks are disjoint. The native function updates every selected sector.
        d0[selected] = np.asarray(data['d0_levels'])[hue_level, selected]
        d1[selected] = np.asarray(data['d1_levels'])[hue_level, selected]
        sat[selected] = np.asarray(data['sat_levels'])[sat_level, selected]
    return d0, d1, sat


class UnitModel:
    def __init__(self, unit='50mm', iso=200, base=None, ideal=False, model_spec=None, display=None, *, geometry=None):
        self.unit = unit
        self.geometry = geometry_mode(geometry)
        self.base = base or s.engine(iso)
        self.mm, self.fs = self.base.mm, self.base.fs
        self.data = s.read('research/module_adapt/local/official_parameters.json')['units'][unit]
        self.display = display or s.read('research/stage2e_verification/local/measurements.json')['frames']['R8051160']['meta']['display']
        self.vividness_percent = self.data['vividness_levels'][self.display['vividness']-1]
        assert self.vividness_percent == 100, '当前适配仅支持已验证的 vividness=100%'
        self.d0, self.d1, self.sat = modifiers(self.data, self.display)
        self.stock = np.array([self.fs.decode_word(bytes.fromhex(self.data['rows']['colour1']['hex'])[i*4:i*4+4]) for i in range(24)])
        self.stock_effective = self.effective(self.stock[:, 0], self.stock[:, 1])
        self.model_spec = module_spec(model_spec or self.base.model, unit, self.geometry)
        if ideal:
            self.model_spec.update(gain=1., gain_per_sector=None, k_coupling=1.)
        pretable = s.load('module_adapt_pretable_'+unit, s.ROOT / 'research/closed_loop/local/vendor/pretable.py')
        pretable.sm = self.base.table.sm
        self.table = pretable.PreTable(self.model_spec, self.stock_effective)
        self.stock_matrix = self.mm.MatrixRow.from_bytes(bytes.fromhex(self.data['rows']['matrix1_2']['hex'])[:28])
        self.curve04 = self.mm.Curve.from_rows(*self.base.src.unpack_tone(
            bytes.fromhex(self.data['rows']['A5']['hex']), bytes.fromhex(self.data['rows']['B5']['hex'])))

    def effective(self, A, B):
        # At the current neutral saturation setting the native truncation is exact.
        # Non-neutral hue d0 is added after A saturation; B+d1 is scaled together.
        return ((np.asarray(A)*self.sat/100+self.d0)-1j*(np.asarray(B)+self.d1)*self.sat/100)/32

    def curves(self, slot):
        e = self.base.entries[slot]
        a, b, _, _, _, _, cd = e['written']
        inputs, outputs = self.base.src.unpack_tone(a, b)
        if e['mask'] & 6:
            assert e['mask'] & 6 == 6 and e['control'] == 0
            ys = (list(cd[:33]), outputs, list(cd[33:]))
        else:
            ys = (outputs,)*3
        return [self.mm.Curve.from_rows(inputs, y, name=slot) for y in ys]

    def parameters(self, slot):
        if slot == '04':
            return self.stock_matrix, self.stock[:, 0].copy(), self.stock[:, 1].copy()
        return self.base.parameters(slot)

    def pre(self, slot, x):
        return np.column_stack([curve(np.asarray(x)[:, i]) for i, curve in enumerate(self.curves(slot))])

    def predict(self, slot, x, row=None, A=None, B=None, unclipped=False):
        r, a, b = self.parameters(slot)
        r, a, b = r if row is None else row, a if A is None else A, b if B is None else B
        pre = self.pre(slot, x)
        y, ci = r.apply(pre)
        if slot == '03':
            rgb = np.repeat(y[:, None], 3, axis=1)
        elif slot == '04' and A is None and B is None:
            rgb = self.mm.rgb_from_ycc(y, self.table.forward_stock(ci)[0])
        else:
            ratio = self.effective(a, b) / self.stock_effective
            co = self.table.forward(ci, ratio)[0]
            rgb = self.mm.rgb_from_ycc(y, co)
        return rgb if unclipped else np.clip(rgb, 0, 255)

    def inverse04(self, rgb, raw_wb):
        y, co = self.mm.ycbcr(rgb)
        hint = self.mm.hue_deg(self.stock_matrix.apply(self.curve04(raw_wb*4095))[1])
        ci, _ = self.table.inverse_stock(co, h_hint=hint)
        pre = self.stock_matrix.invert(y, ci)
        x = self.curve04.inverse(pre)
        rt = self.predict('04', x)
        de = self.fs.delta_e00(self.fs.lab_from_codes(rt), self.fs.lab_from_codes(rgb))
        bad = np.any((pre <= self.curve04.ys[0]+.01) | (pre >= self.curve04.ys[-1]-.01), axis=1)
        bad |= de > .1
        return x, bad

    def de(self, a, b):
        return self.fs.delta_e00(self.fs.lab_from_codes(a), self.fs.lab_from_codes(b))

    def describe(self):
        return {'unit': self.unit, 'firmware': self.data['firmware'], 'iso': self.base.iso,
                'table_sha256': s.digest(s.DAILY), 'stock_is_module_native': True,
                'recipe_colour_is_full_row_replacement': True,
                't_and_mask_remain_module_native': True, 'response_calibration_source': '50mm measured',
                'c040_geometry': self.geometry, 'c040_nodes_module_native': self.geometry == 'native',
                'unit_camera_calibrated': self.unit == '50mm', 'camera_acceptance': False}
