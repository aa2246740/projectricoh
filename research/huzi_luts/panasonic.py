"""Bounded numerical inverse of the downloaded tetrahedrally sampled S2V data."""
import numpy as np
from itertools import product
from scipy.spatial import cKDTree


def summary(x):
    x = np.asarray(x).ravel()
    if not len(x):
        return {'n': 0, 'median': None, 'p90': None, 'max': None}
    return {'n': len(x), 'median': float(np.median(x)), 'p90': float(np.percentile(x, 90)),
            'p99': float(np.percentile(x, 99)), 'max': float(x.max())}


class StandardInverse:
    def __init__(self, cube):
        if cube.table1 is not None or len(cube.table3) != 33:
            raise ValueError('Expected a 33-point 3D Standard to V-Log LUT')
        self.cube = cube
        z, y, x = np.meshgrid(np.linspace(0, 1, 33), np.linspace(0, 1, 33),
                              np.linspace(0, 1, 33), indexing='ij')
        self.nodes = np.stack([x, y, z], axis=-1).reshape(-1, 3)
        self.values = cube.table3.reshape(-1, 3)
        self.tree = cKDTree(self.values)
        self.neutral_x = np.linspace(0, 1, 4097)
        self.neutral_y = cube.apply(np.repeat(self.neutral_x[:, None], 3, axis=1)).mean(axis=1)

    def value_jacobian(self, x):
        x = np.clip(np.asarray(x).reshape(-1, 3), 0, 1)
        n = len(self.cube.table3)
        pos = x * (n - 1)
        b = np.minimum(pos.astype(int), n - 2)
        f = pos - b
        order = np.argsort(-f, axis=1, kind='stable')
        ix = np.arange(len(x))
        v = [self.cube.table3[b[:, 2], b[:, 1], b[:, 0]]]
        for j in range(3):
            b[ix, order[:, j]] += 1
            v.append(self.cube.table3[b[:, 2], b[:, 1], b[:, 0]])
        u = np.take_along_axis(f, order, axis=1)
        out = v[0].copy()
        J = np.empty((len(x), 3, 3))
        for j in range(3):
            d = v[j+1] - v[j]
            out += u[:, j, None] * d
            J[ix, :, order[:, j]] = d * (n - 1)
        return out, J

    def refine(self, target, start, iterations=24):
        x = np.clip(np.asarray(start).copy(), 0, 1)
        target = np.asarray(target)
        error = np.max(abs(self.cube.apply(x) - target), axis=1)
        stalled = np.zeros(len(x), int)
        for _ in range(iterations):
            active = np.flatnonzero((error > 1e-7) & (stalled < 3))
            if not len(active):
                break
            a = x[active]
            value, J = self.value_jacobian(a)
            r = value - target[active]
            JT = J.swapaxes(1, 2)
            H = JT @ J + 1e-10 * np.eye(3)
            step = np.linalg.solve(H, (JT @ r[..., None]))[..., 0]
            step *= np.minimum(1., .3 / np.maximum(np.max(abs(step), axis=1), 1e-12))[:, None]
            best, be = a.copy(), np.sum(r*r, axis=1)
            for scale in (1., .5, .125, .03125):
                trial = np.clip(a - scale * step, 0, 1)
                re = self.cube.apply(trial) - target[active]
                e = np.sum(re*re, axis=1)
                use = e < be - 1e-17
                best[use], be[use] = trial[use], e[use]
            new_error = np.max(abs(self.cube.apply(best) - target[active]), axis=1)
            improvement = error[active] - new_error
            stalled[active] = np.where(improvement < 1e-9, stalled[active] + 1, 0)
            x[active], error[active] = best, new_error
        return x, error

    def invert(self, target, restarts=True):
        shape = np.asarray(target).shape
        y = np.asarray(target).reshape(-1, 3)
        if not np.isfinite(y).all():
            raise ValueError('Nonfinite V-Log input')
        _, ix = self.tree.query(y, k=1, workers=1)
        x, residual = self.refine(y, self.nodes[ix])
        if restarts:
            hard = np.flatnonzero(residual > 1e-5)
            if len(hard):
                _, alternatives = self.tree.query(y[hard], k=16, workers=1)
                neutral = np.repeat(np.interp(y[hard].mean(axis=1), self.neutral_y,
                                              self.neutral_x)[:, None], 3, axis=1)
                for start in (self.nodes[alternatives[:, 4]], self.nodes[alternatives[:, 15]], neutral):
                    xx, ee = self.refine(y[hard], start, 36)
                    use = ee < residual[hard]
                    x[hard[use]], residual[hard[use]] = xx[use], ee[use]
            hard = np.flatnonzero(residual > 1e-5)
            if len(hard):
                # Clipping an unconstrained Newton step is not the constrained
                # least-squares solution on a gamut face. Solve the local 3D
                # box problem over all 27 active sets, then check actual output.
                xx, ee = self.refine_box(y[hard], x[hard])
                old_sse = np.sum((self.cube.apply(x[hard])-y[hard])**2, axis=1)
                new_sse = np.sum((self.cube.apply(xx)-y[hard])**2, axis=1)
                use = new_sse < old_sse
                x[hard[use]], residual[hard[use]] = xx[use], ee[use]
        return x.reshape(shape), residual.reshape(shape[:-1])

    def refine_box(self, target, start, iterations=32):
        x = np.asarray(start).copy()
        error = np.max(abs(self.cube.apply(x)-target), axis=1)
        stalled = np.zeros(len(x), int)
        for _ in range(iterations):
            active = np.flatnonzero((error > 1e-7) & (stalled < 3))
            if not len(active):
                break
            a = x[active]
            val, J = self.value_jacobian(a)
            r = val-target[active]
            H = J.swapaxes(1, 2)@J + 1e-10*np.eye(3)
            lo, hi = np.maximum(-a, -.3), np.minimum(1-a, .3)
            best_step = np.zeros_like(a)
            best_cost = np.sum(r*r, axis=1)
            for state in product((-1, 0, 1), repeat=3):
                st = np.asarray(state)
                free = st == 0
                d = np.where(st[None] == -1, lo, np.where(st[None] == 1, hi, 0.))
                if free.any():
                    adjusted = r + (J@d[..., None])[..., 0]
                    jf = J[:, :, free]
                    rhs = -(jf.swapaxes(1, 2)@adjusted[..., None])
                    hf = H[:, free][:, :, free]
                    d[:, free] = np.linalg.solve(hf, rhs)[..., 0]
                valid = np.all((d >= lo-1e-10) & (d <= hi+1e-10), axis=1)
                rr = r+(J@d[..., None])[..., 0]
                cost = np.sum(rr*rr, axis=1)
                use = valid & (cost < best_cost)
                best_step[use], best_cost[use] = d[use], cost[use]
            original_cost = np.sum(r*r, axis=1)
            best, actual = a.copy(), original_cost.copy()
            for scale in (1., .5, .125, .03125):
                trial = np.clip(a+scale*best_step, 0, 1)
                rr = self.cube.apply(trial)-target[active]
                cost = np.sum(rr*rr, axis=1)
                use = cost < actual-1e-18
                best[use], actual[use] = trial[use], cost[use]
            stalled[active] = np.where(original_cost-actual < 1e-15, stalled[active]+1, 0)
            x[active] = best
            error[active] = np.max(abs(self.cube.apply(best)-target[active]), axis=1)
        return x, error

    def diagnostic(self, fs):
        from scipy.optimize import least_squares
        rng = np.random.default_rng(20261024)
        x = rng.uniform(.001, .999, (4096, 3))
        y, J = self.value_jacobian(x)
        xx, e = self.invert(y)
        s = np.linalg.svd(J, compute_uv=False)
        det = np.linalg.det(J)
        reconstruction = fs.delta_e00(fs.lab_from_codes(x*255), fs.lab_from_codes(xx*255))
        # A second, distant initial value detects some multiple-preimage cases.
        alternate, ae = self.refine(y[:512], np.full((512, 3), .5), 48)
        both_exact = (e[:512] < 1e-5) & (ae < 1e-5)
        ambiguous = both_exact & (np.max(abs(alternate - xx[:512]), axis=1) > .02)
        checks = []
        for i in np.linspace(0, len(y)-1, 24).astype(int):
            opt = least_squares(lambda q: self.cube.apply(q[None])[0]-y[i],
                                np.clip(xx[i], 1e-10, 1-1e-10), bounds=(0., 1.),
                                max_nfev=120, ftol=1e-12, xtol=1e-12, gtol=1e-12)
            checks.append(float(np.max(abs(opt.fun))))
        eps = 1e-7
        jf = np.stack([(self.cube.apply(x[:128]+np.eye(3)[j]*eps)-
                        self.cube.apply(x[:128]-np.eye(3)[j]*eps))/(2*eps)
                       for j in range(3)], axis=-1)
        return {'test_seed': 20261024, 'standard_test_n': len(x),
                'analytic_jacobian_max_error': float(abs(jf-J[:128]).max()),
                'negative_determinant_share': float(np.mean(det < -1e-9)),
                'near_singular_share_smin_lt_1e_4': float(np.mean(s[:, -1] < 1e-4)),
                'jacobian_condition': summary(s[:, 0]/np.maximum(s[:, -1], 1e-20)),
                'roundtrip_vlog_linf': summary(e),
                'roundtrip_standard_de00': summary(reconstruction),
                'roundtrip_exact_share_linf_lt_1e_5': float(np.mean(e < 1e-5)),
                'multiple_preimages_detected_n_of_512': int(ambiguous.sum()),
                'multiple_preimages_tested': 512,
                'scipy_independent_check_linf_24': summary(checks),
                'vlog_output_bbox_min': self.values.min(axis=0),
                'vlog_output_bbox_max': self.values.max(axis=0),
                'interpretation': 'bounded numerical estimate; local tests do not prove global injectivity'}

    def boundary(self, vlog, standard, residual):
        y = np.asarray(vlog).reshape(-1, 3)
        x = np.asarray(standard).reshape(-1, 3)
        e = np.asarray(residual).ravel()
        return {'n': len(y), 'vlog_input_linf_residual': summary(e),
                'exact_preimage_share_linf_lt_1e_5': float(np.mean(e < 1e-5)),
                'no_close_preimage_found_share_linf_gt_1e_3': float(np.mean(e > 1e-3)),
                'outside_output_bbox_share': float(np.mean(np.any(
                    (y < self.values.min(axis=0)) | (y > self.values.max(axis=0)), axis=1))),
                'standard_boundary_share_1e_3': float(np.mean(np.any((x < .001) | (x > .999), axis=1))),
                'vlog_outside_0_1_share': float(np.mean(np.any((y < 0) | (y > 1), axis=1))),
                'scope': 'no close preimage found is an algorithm result, not a proof of outside-gamut membership'}
