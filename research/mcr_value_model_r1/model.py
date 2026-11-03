"""Conditional pre-curve RGB mixing, jointly fitted with existing recipe controls."""
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np, f, old

FOLDS = [f'page{i}' for i in range(1, 7)] + [f'hue{i}' for i in range(3)]
PAIRS = [(i, j) for i in range(3) for j in range(3) if i != j]
SCALE = 256.
LIMIT = .25
RIDGE = .02


def data(m, slot, fold, target_kind='bridge'):
    original_local = rt.LOCAL
    try:
        rt.LOCAL = rt.ROOT / 'research/hw_refit_r1/local'
        d = old.prepare_data(m, slot, fold)
    finally:
        rt.LOCAL = original_local
    if slot in ('01', '02'):
        prefix = 'gr4_dense_returns_r1' if slot == '01' else 'gr4_nega_returns_r1'
        d['raw_wb'] = rt.arrays(f'research/{prefix}/local/fit/data.npz')['raw']
    else:
        d['raw_wb'] = np.array([r['raw'] for r in d['records']])
    frames = rt.read(rt.DATA / 'frames.json')['frames']
    d['wb'] = np.array([frames[r['frame']]['white_balance']['gains'] for r in d['records']])
    d['calibration'] = rt.read(rt.R7 / f'local/folds/{fold}/calibration.json')
    assert d['calibration']['degree'] == 1
    assert np.max(abs(rt.calibrate.apply_calibration(d['raw_wb'], d['calibration']) - d['x'])) < 1e-9
    d['bridge_target'], d['bridge_baseline'] = d['target'].copy(), d['baseline'].copy()
    if target_kind == 'diagnostic':
        assert slot in ('01', '02')
        a = rt.arrays(f'research/gr4_analytic_target_r2/local/data/{slot}.npz')
        assert np.array_equal(d['raw_wb'], a['raw'])
        assert np.array_equal(d['score_mask'], a['supported'])
        d['target'] = a['target']
        d['baseline'] = m.fs.delta_e00(m.fs.lab_from_codes(a['base_rgb']), d['target'])
    d['target_kind'] = target_kind
    return d


class Problem(old.Problem):
    def __init__(self, m, slot, d, hypothesis='H1', placement='before_calibration', radius=LIMIT, ridge=RIDGE):
        self.hypothesis, self.placement = hypothesis, placement
        self.radius, self.mix_ridge = radius, ridge
        super().__init__(m, slot, d, (), True)
        self.base_np = self.np
        old_R = self.R.copy()
        if hypothesis != 'current':
            self.add('mix', 6, radius * SCALE, ridge)
            self.R = np.zeros((old_R.shape[0] + 6, self.np))
            self.R[:old_R.shape[0], :self.base_np] = old_R
            self.R[old_R.shape[0]:, self.base_np:] = np.eye(6) * ridge
        coeff = np.asarray(d['calibration']['residual_coefficients'])
        self.cal_K, self.cal_b = np.eye(3) + coeff[1:], coeff[0]
        self.source = d['raw_wb'] / d['wb'] if hypothesis == 'H3' else d['raw_wb']
        self.dx = np.zeros((len(self.source), 3, 6))
        if hypothesis != 'current':
            for k, (i, j) in enumerate(PAIRS):
                if placement == 'at_curve':
                    self.dx[:, i, k] = d['x'][:, j] / SCALE
                    if hypothesis == 'H2':
                        self.dx[:, i, k] -= d['x'][:, i] / SCALE
                else:
                    dt = np.zeros_like(self.source)
                    dt[:, i] = self.source[:, j] / SCALE
                    if hypothesis == 'H2': dt[:, i] -= self.source[:, i] / SCALE
                    if hypothesis == 'H3': dt *= d['wb']
                    self.dx[:, :, k] = dt @ self.cal_K * 4095

    def mix_matrix(self, p, quant=False):
        M = np.eye(3)
        if self.hypothesis == 'current': return M
        values = self.val(p, 'mix') / SCALE
        if quant: values = np.rint(values * 1024) / 1024
        for value, (i, j) in zip(values, PAIRS):
            M[i, j] = value
            if self.hypothesis == 'H2': M[i, i] -= value
        return M

    def curve_input(self, p, quant=False):
        if self.hypothesis == 'current': return self.d['x']
        M = self.mix_matrix(p, quant)
        if self.placement == 'at_curve': return self.d['x'] @ M.T
        raw = self.source @ M.T
        if self.hypothesis == 'H3': raw *= self.d['wb']
        return (raw @ self.cal_K + self.cal_b) * 4095

    def predict(self, p, quant=False, x=None, bias=None):
        assert x is None
        state = self.state(p, quant)
        H = f.weights(self.curve_input(p, quant), self.xnodes)
        pre = np.einsum('ncj,cj->nc', H, state['q'])
        raw = self.forward(state, pre)
        return np.clip(raw + (self.d['bias'] if bias is None else bias), 0, 255)

    def evaluate(self, p):
        if self.cache is not None and np.array_equal(p, self.cache[0]): return self.cache[1:]
        self.calls += 1
        state = self.state(p)
        x = self.curve_input(p)
        H = f.weights(x, self.xnodes)
        pre = np.einsum('ncj,cj->nc', H, state['q'])
        raw, ci, G, gain = self.forward(state, pre, True)
        def loss(rgb):
            return self.m.fs.de00_components(self.m.fs.lab_from_codes(np.clip(rgb + self.d['bias'], 0, 255)), self.d['target'])
        res = loss(raw)
        eps = 1e-5
        L = np.empty((len(raw), 3, 3))
        D = np.empty_like(L)
        for ch in range(3):
            dv = np.zeros_like(raw)
            dv[:, ch] = eps
            L[:, :, ch] = (loss(raw + dv) - loss(raw - dv)) / (2 * eps)
            D[:, :, ch] = (self.forward(state, pre + dv) - self.forward(state, pre - dv)) / (2 * eps)
        J = np.zeros((len(raw), 3, self.np))
        if 'sector' in self.blocks:
            dc = ci[:, None] * G / 32 * gain[:, None]
            J[:, :, self.blocks['sector']] = np.concatenate([self.rgbj(dc), self.rgbj(1j * dc)], axis=2)
        sl = self.blocks['curve']
        for ch in range(3):
            start = sl.start + (ch if self.nc == 3 else 0) * 33
            J[:, :, start:start + 33] += D[:, :, ch, None] * H[:, ch, None, :]
        for j in range(self.blocks['Y'].start, self.blocks['Y'].stop):
            delta = np.zeros(self.np)
            delta[j] = eps
            J[:, :, j] = (self.forward(self.state(p + delta), pre) - self.forward(self.state(p - delta), pre)) / (2 * eps)
        if 'mix' in self.blocks:
            k = np.clip(np.searchsorted(self.xnodes, x, side='right') - 1, 0, len(self.xnodes) - 2)
            slopes = np.empty_like(x)
            for ch in range(3):
                slopes[:, ch] = np.diff(state['q'][ch])[k[:, ch]] / np.diff(self.xnodes)[k[:, ch]]
            slopes *= (x > self.xnodes[0]) & (x < self.xnodes[-1])
            J[:, :, self.blocks['mix']] = np.einsum('nrc,nck->nrk', D, slopes[:, :, None] * self.dx)
        mask = self.d['train']
        jac = np.einsum('nrc,ncp->nrp', L, J)[mask].reshape(-1, self.np)
        residual = np.r_[res[mask].ravel(), self.R @ p, self.constraints(p, state)]
        jac = np.vstack([jac, self.R, self.constraint_jacobian(state)])
        self.cache = (p.copy(), residual, jac)
        return residual, jac

    def packed(self, p):
        packed = old.packed_parameters(self, p)
        packed['mix_q10'] = np.rint(self.mix_matrix(p, True) * 1024).astype(int)
        packed['hypothesis'] = self.hypothesis
        packed['placement'] = self.placement
        return packed


def integer_refine(P, p):
    p = p.copy()
    if 'mix' not in P.blocks: return p, dict(evaluations=0)
    sl = P.blocks['mix']
    p[sl] = np.rint(p[sl] * 4) / 4
    calls = 0
    def objective(v):
        nonlocal calls
        calls += 1
        rgb = P.predict(v, True)
        r = P.m.fs.de00_components(P.m.fs.lab_from_codes(rgb), P.d['target'])[P.d['train']]
        reg = P.R @ v
        return float(np.sum(r*r) + reg @ reg)
    initial = best = objective(p)
    for _ in range(3):
        changed = False
        for j in range(sl.start, sl.stop):
            choices = []
            for step in (-.25, .25):
                trial = p.copy()
                trial[j] += step
                if abs(trial[j]) <= P.radius * SCALE:
                    choices.append((objective(trial), trial))
            if choices:
                cost, trial = min(choices, key=lambda item: item[0])
                if cost < best - 1e-10: p, best, changed = trial, cost, True
        if not changed: break
    return p, dict(evaluations=calls, initial_objective=initial, final_objective=best, training_only=True)
