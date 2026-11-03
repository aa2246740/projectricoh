"""Fit with relative hue-ring penalties before the final integer hard checks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from scipy.optimize import least_squares
import time


class GuardedProblem:
    def __init__(self, primary, current_predict, fixture_camera, rings, weight=40., optimizer=None):
        self.P, self.weight = primary, weight
        self.optimizer = optimizer or least_squares
        self.x = np.concatenate([r['x'] for r in rings])
        target = current_predict(self.x)
        self.Q = type(primary)(primary.c, self.x, target, np.ones(len(target)), primary.config)
        assert self.Q.np == primary.np and not self.Q.bw
        left, right, eligible = [], [], []
        offset = 0
        for r in rings:
            n = len(r['x'])
            left.extend(range(offset, offset+n-1))
            right.extend(range(offset+1, offset+n))
            eligible.extend(r['valid'][:-1] & r['valid'][1:])
            offset += n
        self.left, self.right = np.array(left), np.array(right)
        self.eligible = np.asarray(eligible, bool)
        _, co = rt.mm.ycbcr(target)
        delta = np.angle(co[self.right]/np.where(abs(co[self.left])>1e-12, co[self.left], 1))*180/np.pi
        baseline_reverse = ((abs(co[self.left])>=2) & (abs(co[self.right])>=2) & (delta/.5 < -.001))
        self.protect = self.eligible & ~baseline_reverse
        self.key, self.parts = None, None

    def penalty(self, p):
        self.Q.evaluate(p)
        _, raw, jac = self.Q.raw_state
        rgb = np.clip(raw, 0, 255)
        jac = jac * ((raw > 0) & (raw < 255))[:, :, None]
        _, co = rt.mm.ycbcr(rgb)
        chroma_derivative = np.array([-.168736+.5j, -.331264-.418688j, .5-.081312j])
        dco = np.einsum('c,ncp->np', chroma_derivative, jac)
        a, b = self.left, self.right
        delta = np.angle(co[b]/np.where(abs(co[a])>1e-12, co[a], 1))*180/np.pi
        active = self.protect & (abs(co[a])>=2) & (abs(co[b])>=2) & (delta < 0)
        residual = self.weight*np.minimum(delta, 0)*active
        direction = np.zeros_like(dco)
        np.divide(dco, co[:, None], out=direction, where=abs(co[:, None])>1e-12)
        derivative = self.weight*(direction[b]-direction[a]).imag*180/np.pi*active[:, None]
        self.last_active_pairs = int(active.sum())
        return residual, derivative

    def evaluate(self, p):
        if self.key is not None and np.array_equal(self.key, p):
            return self.parts
        value, derivative = self.P.evaluate(p)
        guard_value, guard_derivative = self.penalty(p)
        self.key = p.copy()
        self.parts = np.r_[value, guard_value], np.vstack([derivative, guard_derivative])
        return self.parts

    def solve(self, start, nfev=60):
        p = np.clip(start, np.array(self.P.lower)+1e-9, np.array(self.P.upper)-1e-9)
        before = time.monotonic()
        opt = self.optimizer(lambda a:self.evaluate(a)[0], p, jac=lambda a:self.evaluate(a)[1],
            bounds=(self.P.lower, self.P.upper), max_nfev=nfev, x_scale='jac',
            ftol=2e-6, xtol=2e-6, gtol=2e-5)
        return opt.x, dict(success=bool(opt.success), status=int(opt.status), nfev=int(opt.nfev), njev=int(opt.njev),
            cost=float(opt.cost), optimality=float(opt.optimality), seconds=time.monotonic()-before,
            message=opt.message, fixture_penalty_weight=self.weight, remaining_continuous_penalty_pairs=self.last_active_pairs)


def check():
    from fit_one import model, quality, seed
    from entry_codec import predict
    ui, index = 2, 31
    meta = rt.read(rt.LOCAL/'targets/mount-a12'/f'{index:02d}.json')
    data = rt.arrays(rt.LOCAL/'targets/mount-a12'/f'{index:02d}_train.npz')
    current = bytes.fromhex(meta['template_hex'])
    camera = rt.Camera(ui)
    import copy
    native = copy.copy(camera)
    native.row = rt.mm.MatrixRow.from_bytes(current[216:244])
    P = model.Problem(native, data['x'], data['want'], data['sw'], dict(level=0, key='L0_guard_derivative_check'))
    _, rings = quality.fixtures(camera)
    G = GuardedProblem(P, lambda x:predict(current, x, ui, round_output=False), camera, rings)
    p = seed(P, current)
    p[26:50] += .2*np.sin(np.arange(24)*1.7)
    value, jac = G.penalty(p)
    active = abs(value)>1e-6
    assert active.sum() >= 8, 'Derivative check did not exercise hue violations'
    checks = []
    for j in (0, 1, 2, 26, P.qstart+16, P.np-9):
        v = np.zeros(P.np)
        v[j] = 1e-5
        finite = (G.penalty(p+v)[0]-G.penalty(p-v)[0])/(2e-5)
        error = abs(finite-jac[:, j])
        scale = np.maximum(1, abs(finite))
        rel = error/scale
        checks.append(dict(parameter=j, active_pairs=int(active.sum()),
            absolute_max=float(error[active].max()), relative_p95=float(np.percentile(rel[active],95)),
            relative_max=float(rel[active].max())))
        assert np.percentile(rel[active],95) < .01, checks[-1]
    rt.dump('guard_derivative_check.json', dict(status='PASS', checks=checks,
        exercise='perturbed real MOUNT 05 row and its reachable fixed hue rings', implementation='analytic hue derivatives compared to finite differences'))
    print('Hue guard derivative PASS', checks)


if __name__ == '__main__':
    check()
