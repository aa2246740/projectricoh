"""Standard-only calibration with an inner split inside training pages."""
from pathlib import Path
from dataclasses import replace
import copy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import simulator as sim
from scipy.optimize import least_squares

OFF = [(i, j) for i in range(3) for j in range(3) if i != j]
RADII = np.array([0., .25, .5, .75, 1.])
COARSE = [4096, 6144, 8192, 11222, 14336, 18432, 24576]


def training_data(a):
    use = (a['band'] < 4) & a['standard_valid']
    return {k: a[k][use].copy() for k in ('raw_wb', 'radius', 'xy', 'standard', 'role', 'id', 'band')}


def metadata():
    audit = rt.read('research/gr4_analytic_target_r1/local/dense_audit.json')
    return dict(raw_wb_to_scene=audit[0]['raw_wb_to_scene'],
        template_baseline_exposure=audit[0]['geometry']['baseline_exposure'],
        chart_sources=[r['dng_sha256'] for r in audit])


def initial(kind):
    prior = np.asarray(sim.parameters()['modes']['standard']['sensor']).reshape(3, 3) / 8192
    head = np.r_[[prior[i, j] for i, j in OFF], 0., 0., -.5]
    radial = np.array([.2, .45, .75, 1.1])
    if kind != 'knots':
        radial = np.linalg.lstsq(np.stack([RADII[1:] ** k for k in (2, 4, 6)], axis=1), radial, rcond=None)[0]
    if kind == 'poly_center': radial = np.r_[radial, 0., 0.]
    return np.r_[head, radial], prior


def common_of(p, gain, kind):
    base = np.eye(3)
    for v, (i, j) in zip(p[:6], OFF): base[i, j] = v
    for i in range(3): base[i, i] = 1 - sum(base[i, j] for j in range(3) if i != j)
    wb = 2 ** np.array([p[6], 0., p[7]])
    common = dict(matrix_base=base, wb_correction=wb, matrix=base @ np.diag(wb),
        exposure_ev=float(p[8]), gain=int(gain), radial_kind=kind)
    if kind == 'knots': common.update(radius=RADII, radial_ev=np.r_[0., p[9:13]])
    else:
        common['radial_coeff'] = p[9:12]
        if kind == 'poly_center': common['radial_center'] = p[12:14]
    return common


def params_of(common):
    base = np.asarray(common['matrix_base'])
    head = np.r_[[base[i, j] for i, j in OFF], np.log2(common['wb_correction'])[0],
                 np.log2(common['wb_correction'])[2], common['exposure_ev']]
    if common['radial_kind'] == 'knots': tail = np.asarray(common['radial_ev'])[1:]
    else:
        tail = np.asarray(common['radial_coeff'])
        if common['radial_kind'] == 'poly_center': tail = np.r_[tail, common['radial_center']]
    return np.r_[head, tail]


def predict(a, common, options, mode='standard'):
    factor = sim.radial_gain(a['radius'], common, a.get('xy'))
    return sim.render(a['raw_wb'] * factor[:, None], mode, common, options)


def objective_data(pred, observed, weights, loss_kind):
    if loss_kind == 'rgb': return ((pred - observed) * weights[:, None]).ravel()
    return ((rt.lab(pred) - rt.lab(observed)) * weights[:, None]).ravel()


def robust_cost(residual, scale):
    return float(scale ** 2 * np.sum(np.sqrt(1 + (residual / scale) ** 2) - 1))


def fit_data(a, kind, loss_kind, options, gains=None, refine_gain=True, start=None, tag='fit', limit=140):
    assert set(a).issubset({'raw_wb', 'radius', 'xy', 'standard', 'role', 'id', 'band'})
    assert np.all(a['band'] < 4)
    initial_p, prior = initial(kind)
    lower = np.r_[np.repeat(-1.5, 6), -.5, -.5, -3., np.repeat(-.5, 4)] if kind == 'knots' else np.r_[np.repeat(-1.5, 6), -.5, -.5, -3., -10., -10., -10.]
    upper = np.r_[np.repeat(1.5, 6), .5, .5, 3., np.repeat(2.5, 4)] if kind == 'knots' else np.r_[np.repeat(1.5, 6), .5, .5, 3., 10., 10., 10.]
    if kind == 'poly_center':
        lower, upper = np.r_[lower, -.03, -.03], np.r_[upper, .03, .03]
    p0 = params_of(start) if start is not None else initial_p
    weights = np.where(np.isin(a['role'], ['reference', 'radial', 'tone']), 2., 1.)
    scale = .02 if loss_kind == 'rgb' else 1.
    attempts, best = [], None
    gains = COARSE if gains is None else list(gains)
    def residual(p, gain):
        predicted = predict(a, common_of(p, gain, kind), options)
        reg = np.r_[(p[:6] - initial_p[:6]) * .004, p[6:8] * .005]
        if kind == 'knots': reg = np.r_[reg, np.diff(p[9:13], n=2) * .01]
        else: reg = np.r_[reg, p[9:12] * .0005]
        if kind == 'poly_center': reg = np.r_[reg, p[12:14] * .02]
        if loss_kind == 'lab': reg = reg * 50
        return np.r_[objective_data(predicted, a['standard'], weights, loss_kind), reg]
    def solve(gain):
        nonlocal best
        solved = least_squares(lambda p: residual(p, gain), p0, bounds=(lower, upper),
            loss='soft_l1', f_scale=scale, max_nfev=limit, diff_step=2e-4,
            ftol=2e-7, xtol=2e-7, gtol=2e-7)
        common = common_of(solved.x, gain, kind)
        metric = rt.stats(rt.de(predict(a, common, options), a['standard']))
        row = dict(gain=gain, cost=float(solved.cost), success=bool(solved.success),
            nfev=solved.nfev, parameters=solved.x, training_standard=metric)
        attempts.append(row)
        if best is None or solved.cost < best[0]: best = (float(solved.cost), common, solved.x)
        print(tag, 'gain', gain, 'training Standard median', round(metric['median'], 6),
              'cost', round(float(solved.cost), 6), 'nfev', solved.nfev, flush=True)
    for gain in gains: solve(gain)
    if refine_gain:
        gain0 = best[1]['gain']
        for gain in range(max(1024, gain0 - 2048), min(65535, gain0 + 2048) + 1, 256):
            if gain not in gains: solve(gain)
    common = best[1]
    common.update(metadata())
    return dict(common=common, options=sim.options_dict(options), kind=kind, loss=loss_kind,
        attempts=attempts, training_keys=np.c_[a['band'].astype(str), a['id']],
        used_style=False, used_outer_holdout=False, evidence='对真实 GR IV 照片的验证')


def p0():
    a = training_data(rt.arrays(rt.LOCAL / 'dense.npz'))
    inner_train = {k: v[a['band'] < 3] for k, v in a.items()}
    inner_test = {k: v[a['band'] == 3] for k, v in a.items()}
    rows = []
    for kind in ('knots', 'poly3', 'poly_center'):
        for loss in ('rgb', 'lab'):
            tag = 'inner_' + kind + '_' + loss
            state = fit_data(inner_train, kind, loss, sim.Options(), refine_gain=False, tag=tag)
            pred = predict(inner_test, state['common'], sim.Options())
            result = dict(kind=kind, loss=loss, gain=state['common']['gain'],
                inner_page3_standard=rt.stats(rt.de(pred, inner_test['standard'])))
            rows.append(result)
            rt.dump('calibration/' + tag + '.json', state)
    # All selection samples are part of the three-page training pool.
    selected = min(rows, key=lambda r: (r['inner_page3_standard']['median'], r['inner_page3_standard']['p90']))
    rt.dump('p0_selection.json', dict(evidence='对真实 GR IV 照片的验证', inner_candidates=rows,
        selected=selected, selection_rule='inner page3 Standard median, then p90; outer page4 and all natural frames unavailable'))
    state = fit_data(a, selected['kind'], selected['loss'], sim.Options(), tag='P0')
    state['selection'] = selected
    rt.dump('calibration/P0.json', state)
    print('P0 frozen', selected, flush=True)
    return state


def integer_refine(a, state, options, tag):
    common = copy.deepcopy(state['common'])
    kind, loss = common['radial_kind'], state['loss']
    p = params_of(common)
    weights = np.where(np.isin(a['role'], ['reference', 'radial', 'tone']), 2., 1.)
    scale = .02 if loss == 'rgb' else 1.
    trace = []
    def residual(v):
        return objective_data(predict(a, common_of(v, common['gain'], kind), options), a['standard'], weights, loss)
    def cost(v): return robust_cost(residual(v), scale)
    # The shared off-diagonal CCM remains Q13. Each change preserves row sum.
    p[:6] = np.floor(p[:6] * 8192 + .5) / 8192
    current = cost(p)
    for step in (64, 32, 16, 8, 4, 2, 1):
        for sweep in range(3):
            changed = False
            for index in range(6):
                candidates = []
                for sign in (-1, 1):
                    trial = p.copy()
                    trial[index] += sign * step / 8192
                    if abs(trial[index]) > 1.5: continue
                    candidates.append((cost(trial), trial))
                if candidates:
                    value, candidate = min(candidates, key=lambda c: c[0])
                    if value < current - 1e-12:
                        p, current, changed = candidate, value, True
            # Photometric variables have useful derivatives with fixed CCM.
            base = p.copy()
            def reduced(v):
                trial = base.copy(); trial[6:] = v
                return residual(trial)
            lower = np.r_[-.5, -.5, -3., np.repeat(-.5, 4)] if kind == 'knots' else np.r_[-.5, -.5, -3., -10., -10., -10.]
            upper = np.r_[.5, .5, 3., np.repeat(2.5, 4)] if kind == 'knots' else np.r_[.5, .5, 3., 10., 10., 10.]
            if kind == 'poly_center': lower, upper = np.r_[lower, -.03, -.03], np.r_[upper, .03, .03]
            solved = least_squares(reduced, p[6:], bounds=(lower, upper), loss='soft_l1',
                f_scale=scale, max_nfev=60, diff_step=2e-4, ftol=2e-7, xtol=2e-7, gtol=2e-7)
            trial = p.copy(); trial[6:] = solved.x
            value = cost(trial)
            if value < current: p, current = trial, value
            trace.append(dict(step_q13=step, sweep=sweep, cost=current, photo_nfev=solved.nfev))
            if not changed: break
    common = common_of(p, common['gain'], kind)
    common.update(metadata())
    result = {**state, 'common': common, 'options': sim.options_dict(options), 'integer_trace': trace,
        'training_final': rt.stats(rt.de(predict(a, common, options), a['standard']))}
    print(tag, 'integer training Standard', result['training_final'], flush=True)
    return result


def p1():
    old = rt.read(rt.LOCAL / 'calibration/P0.json')
    a = training_data(rt.arrays(rt.LOCAL / 'dense.npz'))
    # Calibrate gamma with a continuous front, then refine the complete integer chain.
    options = sim.Options(gamma='increments')
    warm = fit_data(a, old['kind'], old['loss'], options, start=old['common'], tag='P1')
    final = integer_refine(a, warm, replace(options, front='integer'), 'P1')
    rt.dump('calibration/P1.json', final)
    return final


def p2():
    old = rt.read(rt.LOCAL / 'calibration/P1.json')
    a = training_data(rt.arrays(rt.LOCAL / 'dense.npz'))
    rows, states = [], []
    # The level coordinate and selector-zero semantics are the only finite hypotheses.
    for level in ('first', 'luminance', 'chroma'):
        for zero in ('matrix0', 'identity'):
            options = sim.Options(front='integer', gamma='increments', regions='native', level=level, zero_selector=zero)
            state = integer_refine(a, old, options, 'P2_' + level + '_' + zero)
            weights = np.where(np.isin(a['role'], ['reference', 'radial', 'tone']), 2., 1.)
            residual = objective_data(predict(a, state['common'], options), a['standard'], weights, old['loss'])
            value = robust_cost(residual, .02 if old['loss'] == 'rgb' else 1.)
            row = dict(level=level, zero_selector=zero, cost=value, standard=state['training_final'])
            rows.append(row); states.append(state)
            rt.dump('calibration/P2_' + level + '_' + zero + '.json', state)
    index = min(range(len(rows)), key=lambda i: rows[i]['cost'])
    final = states[index]
    final['selection'] = dict(candidates=rows, selected=rows[index], rule='minimum training Standard robust RGB/Lab cost')
    rt.dump('calibration/P2.json', final)
    print('P2 frozen', rows[index], flush=True)
    return final


if __name__ == '__main__':
    stage = sys.argv[1] if len(sys.argv) > 1 else 'P0'
    {'P0': p0, 'P1': p1, 'P2': p2}[stage]()
