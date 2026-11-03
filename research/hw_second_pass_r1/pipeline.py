"""Conditional two-pass ISP, with integer parameter packing and analytic chains.

This is a patch-mean colour model, not a hardware emulator or firmware builder.
The old first-pass calibration, targets, masks and residual priors are unchanged.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np, f
from scipy.linalg import block_diag
from scipy.optimize import least_squares
import time

old = rt.module('second_pass_frozen_single', 'research/hw_refit_r1/model.py')
SLOTS = ('05', '06', '01', '02')
FOLDS = tuple(f'page{i}' for i in range(1, 7)) + tuple(f'hue{i}' for i in range(3)) + ('full',)
TIERS = ('curves', 'mcm', 'both', 'c120Y', 'c120C')
FIRST_FEATURES = ('gain_Y', 'gain_nodes', 'offsets', 'six', 'tint_add', 'nodes', 'four')
NODES12 = np.r_[np.arange(0, 4096, 128), 4095.].astype(float)
NODES8 = NODES12 * 255 / 4095
B601 = np.array([[.299, .587, .114], [-.168736, -.331264, .5], [.5, -.418688, -.081312]])
C0 = np.rint(B601 * 1024)
V = old.INPUT_INV


def single_rgb_jac(P, p):
    """The frozen first-pass equation, differentiated before its Lab loss."""
    s = P.state(p)
    pre = np.einsum('ncj,cj->nc', P.H, s['q'])
    raw, ci, G, gain = P.forward(s, pre, True)
    J = np.zeros((len(raw), 3, P.np))
    if 'sector' in P.blocks:
        dc = ci[:, None] * G / 32 * gain[:, None]
        J[:, :, P.blocks['sector']] = np.concatenate([P.rgbj(dc), P.rgbj(1j * dc)], axis=2)
    eps = 1e-5
    if 'curve' in P.blocks:
        sl = P.blocks['curve']
        for ch in range(3):
            dv = np.zeros_like(pre)
            dv[:, ch] = eps
            df = (P.forward(s, pre + dv) - P.forward(s, pre - dv)) / (2 * eps)
            start = sl.start + (ch if P.nc == 3 else 0) * 33
            J[:, :, start:start + 33] += df[:, :, None] * P.H[:, ch, None, :]
    for key, sl in P.blocks.items():
        if key in ('sector', 'curve'):
            continue
        for j in range(sl.start, sl.stop):
            dv = np.zeros(P.np)
            dv[j] = eps
            J[:, :, j] = (P.forward(P.state(p + dv), pre) - P.forward(P.state(p - dv), pre)) / (2 * eps)
    unclipped = raw + P.d['bias']
    J *= ((unclipped > 0) & (unclipped < 255))[:, :, None]
    return np.clip(unclipped, 0, 255), J


class Body:
    def __init__(self, m, tier, order, stock_codes):
        self.m, self.tier, self.order = m, tier, order
        self.curves = tier != 'mcm'
        self.has_mcm = tier != 'curves'
        self.axis = tier[-1] if tier.startswith('c120') else None
        self.stock_codes = stock_codes.copy()
        self.orig_nodes = m.table.nodes.copy()
        self.blocks, self.limits, self.ridge = {}, [], []
        self.np = 0
        if self.curves:
            self.add('rlut', 99, 64, .10)
            self.add('tone', 99, 64, .10)
        if self.has_mcm:
            self.add('matrix', 9, 256, .015)
            self.add('offsets', 5, [8, 12, 12, 12, 12], .25)
            self.add('sector', 48, 32, .05)
            self.add('four', 8, 32, .15)
            self.add('nodes', 24, 3, .30)
            self.add('tint', 2, 8, .25)
        if self.axis:
            self.add('gains', 9, 32, .10)
            self.add('gain_nodes', 7, 12, .10)
        eye = np.eye(self.np)
        regs = [eye * np.asarray(self.ridge)[:, None]]
        for key, sl in self.blocks.items():
            if key in ('rlut', 'tone'):
                for ch in range(3):
                    start = sl.start + ch * 33
                    regs.extend([(.60 * (eye[start+i] - 2*eye[start+i+1] + eye[start+i+2]))[None] for i in range(31)])
            if key in ('sector', 'nodes'):
                strength = .12 if key == 'sector' else .35
                for start in range(sl.start, sl.stop, 24):
                    regs.extend([(strength * (eye[start+i] - eye[start+(i+1)%24]))[None] for i in range(24)])
            if key == 'gains':
                regs.extend([(.30 * (eye[sl.start+i] - 2*eye[sl.start+i+1] + eye[sl.start+i+2]))[None] for i in range(7)])
        self.R = np.vstack(regs)
        self.eye = eye

    def add(self, key, n, limit, ridge):
        self.blocks[key] = slice(self.np, self.np+n)
        self.np += n
        self.limits.extend(np.broadcast_to(limit, (n,)).tolist())
        self.ridge.extend(np.broadcast_to(ridge, (n,)).tolist())

    def val(self, p, key, default):
        return p[self.blocks[key]] if key in self.blocks else np.asarray(default, float)

    def state(self, p, quant=False):
        matrix = C0 + self.val(p, 'matrix', np.zeros(9)).reshape(3, 3)
        off = self.val(p, 'offsets', np.zeros(5)).copy()
        tint = self.val(p, 'tint', np.zeros(2)).copy()
        sec = self.val(p, 'sector', np.zeros(48)).copy()
        four = self.val(p, 'four', np.zeros(8)).copy()
        nodes = self.val(p, 'nodes', np.zeros(24)).copy()
        gains = self.val(p, 'gains', np.zeros(9)).copy()
        gn = old.INTERNAL + self.val(p, 'gain_nodes', np.zeros(7))*16383/255
        curves = {key: NODES8[None] + self.val(p, key, np.zeros(99)).reshape(3, 33) for key in ('rlut', 'tone')}
        if quant:
            matrix, off, tint, sec, four, nodes, gains, gn = [np.rint(a) for a in (matrix, off, tint, sec, four, nodes, gains, gn)]
            for i in range(1, 24):
                nodes[i] = max(nodes[i], self.stock_codes[i-1]+nodes[i-1]+2-self.stock_codes[i])
            nodes = np.clip(nodes, -3, 3)
            for i in range(1, 7):
                gn[i] = max(gn[i], gn[i-1]+256)
            gn = np.clip(gn, 256, 16383-256)
            curves['rlut'] = np.maximum.accumulate(np.rint(np.clip(curves['rlut'], 0, 255)*4095/255), axis=1)*255/4095
            curves['tone'] = np.maximum.accumulate(np.rint(np.clip(curves['tone'], 0, 255)), axis=1)
        z = 1+(sec[:24]+1j*sec[24:])/32
        e = abs(z)*np.exp(1j*self.m.table.k*np.angle(z))-1
        return dict(C=matrix, off=off, tint=tint, sec=sec, e=e, four=four,
                    node_delta=nodes, nodes=self.orig_nodes+nodes*360/256,
                    gains=1+gains/64, gain_nodes=np.r_[0., gn, 16383.]/16383,
                    **curves)

    def mcm_ycc(self, s, z, details=False):
        y = z[:, 0]
        ci = z[:, 1]-128+1j*(z[:, 2]-128)
        self.m.table.nodes = s['nodes']
        try:
            W = self.m.table.kernel_weights(self.m.mm.hue_deg(ci), abs(ci))
        finally:
            self.m.table.nodes = self.orig_nodes
        G = W*self.m.table.gain
        P = f.weights_cyclic(self.m.mm.hue_deg(ci), s['nodes'])[:, [0, 11, 17, 23]]
        co = ci*(1+G@s['e'])
        co += 1j/32*((P@s['four'][:4])*ci.real+(P@s['four'][4:])*ci.imag)
        unscaled = co.copy()
        axis = y/255 if self.axis == 'Y' else abs(ci)/(128*np.sqrt(2))
        gain = np.interp(axis, s['gain_nodes'], s['gains']) if self.axis else np.ones(len(y))
        co = co*gain+s['tint'][0]+1j*s['tint'][1]
        out = self.m.mm.rgb_from_ycc(y, co)
        return (out, ci, G, P, gain, unscaled, axis) if details else out

    def mcm(self, p, s, x, jac=False):
        xx = x+V@s['off'][3:]
        z = xx@(s['C']/1024).T + [0, 128, 128]+s['off'][:3]
        if not jac:
            return self.mcm_ycc(s, z)
        out, ci, G, Wfour, gain, unscaled, axis = self.mcm_ycc(s, z, True)
        Jz = np.empty((len(x), 3, 3))
        eps = 1e-5
        for ch in range(3):
            dv = np.zeros_like(z)
            dv[:, ch] = eps
            Jz[:, :, ch] = (self.mcm_ycc(s, z+dv)-self.mcm_ycc(s, z-dv))/(2*eps)
        J = np.zeros((len(x), 3, self.np))
        for row in range(3):
            for col in range(3):
                J[:, :, self.blocks['matrix'].start+row*3+col] = Jz[:, :, row]*xx[:, col, None]/1024
        sl = self.blocks['offsets']
        J[:, :, sl.start:sl.start+3] = Jz
        J[:, :, sl.start+3:sl.stop] = np.einsum('nrc,ck->nrk', Jz, s['C']/1024@V)
        zsec = 1+(s['sec'][:24]+1j*s['sec'][24:])/32
        r2 = np.maximum(abs(zsec)**2, 1e-12)
        eff = s['e']+1
        da = eff*(zsec.real-1j*self.m.table.k*zsec.imag)/r2/32
        db = eff*(zsec.imag+1j*self.m.table.k*zsec.real)/r2/32
        dc = ci[:, None]*G*gain[:, None]
        J[:, :, self.blocks['sector']] = np.concatenate([old.Problem.rgbj(dc*da), old.Problem.rgbj(dc*db)], axis=2)
        dc = 1j/32*gain[:, None]*Wfour
        J[:, :, self.blocks['four']] = np.concatenate([old.Problem.rgbj(dc*ci.real[:, None]), old.Problem.rgbj(dc*ci.imag[:, None])], axis=2)
        J[:, :, self.blocks['tint']] = np.broadcast_to(V, (len(x), 3, 2))
        if self.axis:
            H = f.weights(axis[:, None], s['gain_nodes'])[:, 0]
            J[:, :, self.blocks['gains']] = old.Problem.rgbj(unscaled[:, None]*H/64)
        for key in ('nodes', 'gain_nodes'):
            if key not in self.blocks:
                continue
            sl = self.blocks[key]
            for j in range(sl.start, sl.stop):
                dv = np.zeros(self.np)
                dv[j] = eps
                J[:, :, j] = (self.mcm_ycc(self.state(p+dv), z)-self.mcm_ycc(self.state(p-dv), z))/(2*eps)
        return out, np.einsum('nrc,ck->nrk', Jz, s['C']/1024), J

    def curve(self, s, key, x, jac=False):
        H = f.weights(x, NODES8)
        out = np.einsum('ncj,cj->nc', H, s[key])
        if not jac:
            return out
        Jx = np.zeros((len(x), 3, 3))
        J = np.zeros((len(x), 3, self.np))
        ix = np.clip(np.searchsorted(NODES8, x, side='right')-1, 0, 31)
        for ch in range(3):
            slopes = np.diff(s[key][ch])/np.diff(NODES8)
            Jx[:, ch, ch] = slopes[ix[:, ch]]*((x[:, ch]>0)&(x[:, ch]<255))
            start = self.blocks[key].start+33*ch
            J[:, ch, start:start+33] = H[:, ch]
        return out, Jx, J

    def predict(self, p, x, quant=False, jac=False):
        s = self.state(p, quant)
        stages = ('rlut', 'mcm', 'tone') if self.order == 'a' else ('tone', 'rlut', 'mcm')
        Jx = np.broadcast_to(np.eye(3), (len(x), 3, 3)).copy()
        Jp = np.zeros((len(x), 3, self.np))
        out = x.copy()
        for key in stages:
            if key == 'mcm' and not self.has_mcm or key != 'mcm' and not self.curves:
                continue
            result = self.mcm(p, s, out, jac) if key == 'mcm' else self.curve(s, key, out, jac)
            if jac:
                out, L, J = result
                Jx = np.einsum('nrc,nck->nrk', L, Jx)
                Jp = J+np.einsum('nrc,ncp->nrp', L, Jp)
            else:
                out = result
        if jac:
            mask = ((out>0)&(out<255))[:, :, None]
            return np.clip(out, 0, 255), Jx*mask, Jp*mask
        return np.clip(out, 0, 255)

    def constraints(self, p):
        s = self.state(p)
        rr, jj = [], []
        for key in ('rlut', 'tone'):
            if key not in self.blocks:
                continue
            q = s[key]
            J = self.eye[self.blocks[key]].reshape(3, 33, self.np)
            rr.extend([3*np.minimum(np.diff(q, axis=1), 0).ravel(), 3*np.minimum(q, 0).ravel(), 3*np.maximum(q-255, 0).ravel()])
            jj.extend([(3*np.diff(J, axis=1)*(np.diff(q, axis=1)<0)[:, :, None]).reshape(-1, self.np),
                       (3*J*(q<0)[:, :, None]).reshape(-1, self.np), (3*J*(q>255)[:, :, None]).reshape(-1, self.np)])
        if 'nodes' in self.blocks:
            codes = self.stock_codes+s['node_delta']
            D = np.roll(self.eye[self.blocks['nodes']], -1, axis=0)-self.eye[self.blocks['nodes']]
            active = np.diff(np.r_[codes, codes[0]+256])<2
            rr.append(8*np.minimum(np.diff(np.r_[codes, codes[0]+256])-2, 0))
            jj.append(8*D*active[:, None])
        if self.axis:
            gn = s['gain_nodes']
            J = np.zeros((9, self.np))
            J[1:-1] = self.eye[self.blocks['gain_nodes']]/255
            active = np.diff(gn)*255<256*255/16383
            rr.append(3*np.minimum(np.diff(gn)*255-256*255/16383, 0))
            jj.append(3*np.diff(J, axis=0)*255*active[:, None])
        return (np.concatenate(rr), np.vstack(jj)) if rr else (np.empty(0), np.empty((0, self.np)))

    def packed(self, p):
        s = self.state(p, True)
        return dict(matrix_q10=s['C'].astype(int), offsets_8bit_units=s['off'].astype(int),
                    A=(32+s['sec'][:24]).astype(int), B=(-s['sec'][24:]).astype(int),
                    c080_cd=s['four'].astype(int), c040_codes=(self.stock_codes+s['node_delta']).astype(int),
                    c004=s['tint'].astype(int), c120_nodes_u14=np.rint(s['gain_nodes'][1:-1]*16383).astype(int),
                    c120_gains_u8=np.rint(s['gains']*64).astype(int),
                    rlut_x_u12=NODES12.astype(int), rlut_y_u12=np.rint(s['rlut']*4095/255).astype(int),
                    tone_x_u12=NODES12.astype(int), tone_y_u8=s['tone'].astype(int),
                    curves_enabled=self.curves, mcm_enabled=self.has_mcm, c120_axis=self.axis,
                    order=self.order, physical_stage_semantics_verified=False)


class Pair:
    def __init__(self, m, slot, d, tier, order, mode):
        self.m, self.slot, self.d = m, slot, d
        self.tier, self.order, self.mode = tier, order, mode
        self.first = old.Problem(m, slot, d, FIRST_FEATURES if mode == 'joint' else (), mode == 'joint')
        if mode == 'joint' and slot == '06' and 'sector' not in self.first.blocks:
            previous = self.first.np
            self.first.add('sector', 48, 32, .04)
            self.first.R = np.pad(self.first.R, ((0, 0), (0, 48)))
            eye = np.eye(self.first.np)
            self.first.R = np.vstack([self.first.R, .04*eye[previous:]])
            for start in (previous, previous+24):
                self.first.R = np.vstack([self.first.R, *[(.10*(eye[start+i]-eye[start+(i+1)%24]))[None] for i in range(24)]])
        self.body = Body(m, tier, order, self.first.stock_codes)
        self.nfirst = self.first.np
        self.np = self.nfirst+self.body.np
        self.limits = np.r_[self.first.limits, self.body.limits]
        self.R = block_diag(self.first.R, self.body.R)
        self.fixed_rgb = self.first.predict(np.zeros(self.nfirst))
        self.cache = None
        self.calls = 0

    def predict(self, p, quant=False):
        first = self.first.predict(p[:self.nfirst], quant) if self.nfirst else self.fixed_rgb
        return self.body.predict(p[self.nfirst:], first, quant)

    def evaluate(self, p):
        if self.cache is not None and np.array_equal(p, self.cache[0]):
            return self.cache[1:]
        self.calls += 1
        if self.nfirst:
            first, Jfirst = single_rgb_jac(self.first, p[:self.nfirst])
        else:
            first, Jfirst = self.fixed_rgb, np.empty((len(self.fixed_rgb), 3, 0))
        rgb, Lbody, Jbody = self.body.predict(p[self.nfirst:], first, jac=True)
        J = np.concatenate([np.einsum('nrc,ncp->nrp', Lbody, Jfirst), Jbody], axis=2)
        def loss(value):
            return self.m.fs.de00_components(self.m.fs.lab_from_codes(value), self.d['target'])
        residual = loss(rgb)
        L = np.empty((len(rgb), 3, 3))
        eps = 1e-5
        for ch in range(3):
            dv = np.zeros_like(rgb)
            dv[:, ch] = eps
            L[:, :, ch] = (loss(rgb+dv)-loss(rgb-dv))/(2*eps)
        J = np.einsum('nrc,ncp->nrp', L, J)[self.d['train']].reshape(-1, self.np)
        cbody, jbody = self.body.constraints(p[self.nfirst:])
        if self.nfirst:
            state = self.first.state(p[:self.nfirst])
            cfirst = self.first.constraints(p[:self.nfirst], state)
            jfirst = self.first.constraint_jacobian(state)
        else:
            cfirst, jfirst = np.empty(0), np.empty((0, 0))
        constraints = np.r_[cfirst, cbody]
        jc = block_diag(jfirst, jbody)
        r = np.r_[residual[self.d['train']].ravel(), self.R@p, constraints]
        j = np.vstack([J, self.R, jc])
        self.cache = (p.copy(), r, j)
        return r, j

    def fit(self, max_nfev=40, initial=None):
        start = time.monotonic()
        p0 = np.zeros(self.np) if initial is None else initial.copy()
        limits = np.array(self.limits)
        p0 = np.clip(p0, -limits+1e-7, limits-1e-7)
        opt = least_squares(lambda p:self.evaluate(p)[0], p0, jac=lambda p:self.evaluate(p)[1],
                            bounds=(-limits, limits), max_nfev=max_nfev, ftol=3e-6, xtol=3e-6, gtol=3e-6, x_scale='jac')
        return opt.x, dict(success=bool(opt.success), status=int(opt.status), message=opt.message,
                           nfev=int(opt.nfev), njev=int(opt.njev), cost=float(opt.cost), optimality=float(opt.optimality),
                           seconds=time.monotonic()-start, parameters=self.np, evaluations=self.calls)

    def integer_objective(self, p):
        rgb = self.predict(p, True)
        r = self.m.fs.de00_components(self.m.fs.lab_from_codes(rgb), self.d['target'])[self.d['train']]
        return float(np.sum(r*r)+np.sum((self.R@p)**2))

    def refine_integer(self, p, rounds=1):
        p = p.copy()
        start = objective = self.integer_objective(p)
        coordinates = []
        for source, base in ((self.first, 0), (self.body, self.nfirst)):
            keys = ('offsets', 'tint_add', 'gain_Y') if source is self.first else ('offsets', 'tint', 'gains', 'matrix')
            for key in keys:
                if key in source.blocks:
                    sl = source.blocks[key]
                    coordinates.extend(range(base+sl.start, base+sl.stop))
        changes = 0
        for _ in range(rounds):
            for j in coordinates:
                best, best_value = None, objective
                for step in (-1., 1.):
                    candidate = p.copy()
                    candidate[j] += step
                    if abs(candidate[j]) > self.limits[j]:
                        continue
                    value = self.integer_objective(candidate)
                    if value < best_value-1e-9:
                        best, best_value = candidate, value
                if best is not None:
                    p, objective = best, best_value
                    changes += 1
        return p, dict(start_objective=start, final_objective=objective, changes=changes,
                       rounds=rounds, heldout_used=False)

    def pack(self, p):
        return dict(first=dict(packed=old.packed_parameters(self.first, p[:self.nfirst]),
                               features=list(self.first.features)), body=self.body.packed(p[self.nfirst:]))


def integer_checks(P, p):
    a = P.first.state(p[:P.nfirst], True)
    b = P.body.state(p[P.nfirst:], True)
    codes = P.body.stock_codes+b['node_delta']
    return dict(first_matrix_width=bool(np.max(abs(a['C']))<=2047),
                first_sector_width=bool(np.max(abs(a['A']))<=127 and np.max(abs(a['B']))<=127),
                first_curve=bool(np.min(a['q'])>=0 and np.max(a['q'])<=255 and np.min(np.diff(a['q'], axis=1))>=0),
                body_matrix_width=bool(np.max(abs(b['C']))<=2047),
                body_sector_width=bool(np.max(abs(32+b['sec'][:24]))<=127 and np.max(abs(b['sec'][24:]))<=127),
                body_curves=bool(all(np.min(b[key])>=0 and np.max(b[key])<=255 and np.min(np.diff(b[key], axis=1))>=0 for key in ('rlut', 'tone'))),
                body_nodes=bool(np.min(np.diff(np.r_[codes, codes[0]+256]))>=2 and np.min(codes)>=0 and np.max(codes)<=255),
                body_c120=bool(np.min(np.diff(b['gain_nodes']))>0 and np.min(b['gains'])>=.5 and np.max(b['gains'])<=1.5))
