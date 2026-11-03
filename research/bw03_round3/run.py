#!/usr/bin/env python3
"""Bounded, offline BW03 research. Run with python3 -I -B.

Source inputs are read-only. Derived arrays and all fitted tables stay in local/.
No firmware writer, device access, background process, or network operation.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess

import numpy as np
from scipy import optimize, sparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
TMP = Path('/tmp/bw03_r3')
FRAMES = ('hdf_hc', 'hc_bw')
STOCK = np.array([306, 601, 117], dtype=int)
V2 = ROOT / 'research/hue_ring/local/calibration_20261020/followup_v2/code'
_MODULES = {}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def models():
    if not _MODULES:
        _MODULES['bw'] = load('r3_bw', ROOT / 'research/color_table_fit/bw_mix.py')
        _MODULES['fv'] = load('r3_v2', V2 / 'fitting_v2.py')
    return _MODULES['bw'], _MODULES['fv']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def jsonable(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    raise TypeError(type(x).__name__)


def dump(path, x):
    path = Path(path).resolve()
    assert path.is_relative_to(LOCAL) or path.is_relative_to(TMP.resolve()), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(x, indent=2, default=jsonable, allow_nan=False) + '\n')


def guard():
    i = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert i['MountPoint'] == '/Volumes/Workspace' and i['FilesystemType'] == 'apfs'
    assert i['VolumeUUID'].upper() == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert all(i[k] for k in ('Writable', 'WritableMedia', 'WritableVolume'))
    assert HERE == ROOT / 'research/bw03_round3'
    assert not LOCAL.is_symlink() and not TMP.is_symlink()
    assert 'local/' in (HERE / '.gitignore').read_text().splitlines()
    subprocess.run(['git', 'check-ignore', '-q', str(LOCAL / 'privacy_probe')], cwd=ROOT, check=True)


def stats(e, ref=None):
    e = np.asarray(e, float)
    if not len(e):
        return {'n': 0}
    a = abs(e)
    out = {'n': len(e), 'median_abs': float(np.median(a)), 'p90_abs': float(np.percentile(a, 90)),
           'rms': float(np.sqrt(np.mean(e * e))), 'mean_signed': float(np.mean(e)),
           'within_2': float(np.mean(a <= 2)), 'within_5': float(np.mean(a <= 5)),
           'within_10': float(np.mean(a <= 10))}
    if ref is not None:
        den = float(np.median(abs(np.asarray(ref))))
        out['stock_median_abs'] = den
        out['effect_reproduced'] = 1 - out['median_abs'] / den if den > 0 else None
    return out


def groups(lab):
    C = np.hypot(lab[:, 1], lab[:, 2])
    h = np.rad2deg(np.arctan2(lab[:, 2], lab[:, 1])) % 360
    ch = C >= 15
    return {'all': np.ones(len(lab), bool), 'chromatic': ch, 'neutral': C < 5,
            'warm': ch & (h >= 30) & (h < 90), 'green': ch & (h >= 90) & (h < 180),
            'blue_cyan': ch & (h >= 180) & (h < 300), 'red': ch & ((h >= 330) | (h < 30)),
            'magenta': ch & (h >= 300) & (h < 330)}


def bins(lab):
    C = np.hypot(lab[:, 1], lab[:, 2])
    h = np.rad2deg(np.arctan2(lab[:, 2], lab[:, 1])) % 360
    key = (np.clip(lab[:, 0] // 10, 0, 10).astype(int) * 1000 +
           np.digitize(C, [5, 10, 20, 40]) * 100 + np.where(C < 5, 0, (h // 15).astype(int) + 1))
    _, idx, cnt = np.unique(key, return_inverse=True, return_counts=True)
    return idx, cnt


def real_weights(D, sel):
    key, idx, ct = np.unique(D['bin'][sel], return_inverse=True, return_counts=True)
    w = 1. / ct[idx]
    return w / w.sum()


def curve_from_rows(rows, core, u118):
    f = core.curve_fn(rows)
    return {'q': np.exp(f.x) / u118, 'j': f.y}


def tone(curve, q):
    # Empirical log-intensity interpolation; linear endpoint tails are labelled unsupported.
    q = np.asarray(q, float)
    x, y = np.asarray(curve['q']), np.asarray(curve['j'])
    flat = q.ravel()
    val = np.interp(np.log(np.maximum(flat, 1e-15)), np.log(x), y)
    low, high = flat < x[0], flat > x[-1]
    val[low] = y[0] * np.maximum(flat[low], 0) / x[0]
    endpoint = max(4095. / 320, x[-1] * 1.01)
    val[high] = np.interp(flat[high], [x[-1], endpoint], [y[-1], 255.])
    return np.clip(val.reshape(q.shape), 0, 255)


def target_definition(hc, cand, core, train=None):
    anchors = [cand['gr4_standard_118_u_c']['B_hdf'], cand['gr4_standard_118_u_c']['pooled_gruser_dr_off']]
    if train is not None:
        name = FRAMES[train]
        return {'mix': np.asarray(hc['mix'][name]['w_linear_srgb']),
                'tone': curve_from_rows(hc['frames'][name]['curve_mix'], core, anchors[train]),
                'source_frames': [name], 'tail_policy': 'linear to zero and unity sensor ceiling'}
    curves = [curve_from_rows(hc['frames'][f]['curve_mix'], core, a) for f, a in zip(FRAMES, anchors)]
    grid = np.unique(np.concatenate([c['q'] for c in curves]))
    vals = []
    for c in curves:
        p = tone(c, grid)
        p[(grid < c['q'][0]) | (grid > c['q'][-1])] = np.nan
        vals.append(p)
    val = np.nanmean(vals, axis=0)
    assert np.isfinite(val).all()
    val = core.monotone(val)
    return {'mix': np.asarray(hc['mix_used']['w_linear_srgb']),
            'tone': {'q': grid, 'j': val}, 'source_frames': list(FRAMES),
            'tail_policy': 'linear to zero and unity sensor ceiling'}


def target(T, lin18):
    q = np.asarray(lin18) @ np.asarray(T['mix']) / .18
    c = T['tone']
    support = (q >= np.asarray(c['q'])[0]) & (q <= np.asarray(c['q'])[-1])
    return tone(c, q), support


def record_inputs(extra):
    paths = {Path(p).resolve() for p in extra}
    for mod in list(sys.modules.values()):
        f = getattr(mod, '__file__', None)
        if f and Path(f).resolve().is_relative_to(ROOT) and Path(f).suffix == '.py':
            paths.add(Path(f).resolve())
    snap = {str(p.relative_to(ROOT)): {'sha256': sha(p), 'size': p.stat().st_size}
            for p in sorted(paths) if not p.is_relative_to(HERE)}
    dump(LOCAL / 'input_snapshot.json', snap)


def prepare():
    LOCAL.mkdir(exist_ok=True)
    TMP.mkdir(exist_ok=True)
    bw, fv = models()
    gr = ROOT / 'research/gr4_modes/local'
    hc, cand, tc = [read(gr / n) for n in ('hcbw.json', 'candidates.json', 'tone_curves.json')]
    row = cand['modes']['hc_bw']['row_jpeg_domain']
    K = bw.mm.Curve.from_rows(row['input31_u16'], row['output33_u8'])
    to_c = np.asarray(hc['gxr_mix']['gxr_to_c_from_linsrgb'])
    anchors = [cand['gr4_standard_118_u_c'][bw.FRAMES[f]] for f in FRAMES]
    ds = [bw.gr4_blocks(f, a, to_c, np.asarray(tc['radial']['gr4_coef_natural_log']))
          for f, a in zip(FRAMES, anchors)]
    D = {k: np.concatenate([d[k] for d in ds]) for k in ('x', 'j', 'lab', 'lin')}
    D['lin18'] = np.concatenate([d['lin'] * (.18 / a) for d, a in zip(ds, anchors)])
    D['frame'] = np.concatenate([np.full(len(d['j']), i, dtype=np.int8) for i, d in enumerate(ds)])
    D['bin'], cnt = bins(D['lab'])
    D['nodes'], D['curve'] = K.xs, K.ys
    D['F'] = K(D['x'])
    assert len(D['j']) == 601340 and groups(D['lab'])['chromatic'].sum() == 190116
    pred = D['F'] @ (STOCK / 1024)
    ref = read(ROOT / 'research/bw03_round2/local/baseline.json')['references']['stock']
    assert abs(stats((pred - D['j'])[groups(D['lab'])['chromatic']])['median_abs'] - ref['chromatic']['median_abs']) < 1e-8
    assert abs(np.sqrt(np.sum(real_weights(D, np.ones(len(pred), bool)) * (pred-D['j'])**2)) - ref['bin_weighted_rms']) < 1e-8
    Ts = {'pooled': target_definition(hc, cand, bw.core)}
    Ts.update({f'train_{i}': target_definition(hc, cand, bw.core, i) for i in range(2)})
    # Full raw-cache data, not a reused round-2 scratch cache.
    np.savez_compressed(LOCAL / 'real_blocks.npz', **D)
    dump(LOCAL / 'target_definitions.json', Ts)
    # Nominal04-style colour synthesis, v2 inverse. Fixed chart calibration, never GR IV holdouts.
    S = fv.SetupV2(scene='published', model_path=ROOT / 'research/hue_ring/local/ring_model_v2.json')
    nominal = fv.fm.fs.Nominal04(S.ctx)
    raw_nominal_M = nominal.M.copy()
    # The calibration chart was exposed below the selected 03 mid-grey anchor.
    # Define scene colours at a common exposure: neutral 18% -> sensor 320 -> stock JPEG 118.
    # This adjustment is fixed by a neutral stimulus, not a GR IV colour target.
    nominal.M *= (320. / .18 / (nominal.M @ np.ones(3)))[:, None]
    neutral_inv = S.chain.invert(nominal.render(np.full((1, 3), .18)))['x'][0]
    assert np.max(abs(neutral_inv - 320)) < 1e-6, neutral_inv
    fs = fv.fm.fs
    inv709 = np.linalg.inv(fs.M709)
    def design(levels, hues, fractions):
        lin, lab, spec = [], [], []
        for L in levels:
            for h in hues:
                lo, hi = 0., 200.
                for _ in range(25):
                    C = (lo + hi) / 2
                    l = np.array([L, C*np.cos(np.deg2rad(h)), C*np.sin(np.deg2rad(h))])
                    rgb = fs.lab_to_xyz(l, fs.D65) @ inv709.T
                    if rgb.min() >= 0 and rgb.max() <= 1:
                        lo = C
                    else:
                        hi = C
                for f in fractions:
                    l = np.array([L, f*lo*np.cos(np.deg2rad(h)), f*lo*np.sin(np.deg2rad(h))])
                    lin.append(fs.lab_to_xyz(l, fs.D65) @ inv709.T)
                    lab.append(l)
                    spec.append([L, h, f])
        lin = np.asarray(lin)
        inv = S.chain.invert(nominal.render(lin))
        out = {'lin18': lin, 'lab': np.asarray(lab), 'design': np.asarray(spec), 'x': inv['x']}
        out['F'] = K(out['x'])
        out['out_of_curve'] = inv['rgb_pre_out_of_curve_range']
        for name, T in Ts.items():
            out[f'target_{name}'], out[f'support_{name}'] = target(T, lin)
        return out
    train = design((25., 40., 55., 70., 82.), np.arange(7.5, 360., 15.), (.25, .55, .85))
    held = design((32., 48., 63., 76.), np.arange(0., 360., 15.), (.4, .7))
    np.savez_compressed(LOCAL / 'synthetic_train.npz', **train)
    np.savez_compressed(LOCAL / 'synthetic_held.npz', **held)
    # Same authored points as round 2, through both the old mapping and v2 mapping.
    point_names = ('sky_blue', 'foliage_green', 'skin_warm', 'red')
    lin = np.array([[.08, .25, .65], [.08, .30, .04], [.45, .25, .16], [.65, .04, .025]])
    inv = S.chain.invert(nominal.render(lin))
    points = {'names': point_names, 'lin18': lin, 'x': inv['x'], 'old_x': lin @ to_c.T * (320/.18),
              'target': target(Ts['pooled'], lin)[0], 'target_support': target(Ts['pooled'], lin)[1]}
    for name, T in Ts.items():
        points['target_' + name] = target(T, lin)[0]
    dump(LOCAL / 'authored_points.json', points)
    dump(LOCAL / 'calibration.json', {'nominal04_M': nominal.M, 'raw_nominal04_M': raw_nominal_M,
         'raw_nominal04_fit_de00': nominal.fit_de00,
         'neutral_exposure_normalisation': 'each Nominal04 row sum = 320/0.18; 18 percent neutral maps to sensor code 320',
         'normalised_neutral_sensor_max_error': float(abs(neutral_inv-320).max()),
         'v2_model_sha256': sha(S.model_path), 'v2_invert_max_residual': S.table.last_inverse_residual,
         'v2_invert_ambiguity_count': S.table.last_ambiguity_count, 'vivid_pct': S.vivid_pct,
         'train_n': len(train['x']), 'held_n': len(held['x']),
         'train_out_of_curve_n': int(train['out_of_curve'].sum()),
         'held_out_of_curve_n': int(held['out_of_curve'].sum()),
         'train_held_nearest_lin_distance': float(np.linalg.norm(train['lin18'][:,None] - held['lin18'][None,:],axis=-1).min()),
         'neutral_M_response': nominal.M @ np.ones(3), 'chart_calibration_frozen_in_LOPO': True})
    extra = [gr/n for n in ('hcbw.json','candidates.json','tone_curves.json','hdf_hc.npz','hc_bw.npz')]
    extra += [ROOT/'research/bw03_round2/local/baseline.json', S.model_path,
              V2.parent/'absolute_rows.json', ROOT/'research/gr_complete_pipeline/REPORT.md']
    extra += [ROOT/p for p in S.inputs if (ROOT/p).is_file() and str((ROOT/p).resolve()).startswith(str(ROOT))]
    record_inputs(extra)
    print(json.dumps({'real_n': len(D['j']), 'chromatic_n': int(groups(D['lab'])['chromatic'].sum()),
                      'bins': len(cnt), 'stock_reproduced': True, 'synthetic_train': len(train['x']),
                      'synthetic_held': len(held['x']), 'out_of_curve': int(train['out_of_curve'].sum()+held['out_of_curve'].sum())}))


def data(name):
    with np.load(LOCAL / (name + '.npz'), allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def validate_targets():
    D = data('real_blocks')
    Ts = read(LOCAL / 'target_definitions.json')
    bw, fv = models()
    masks = groups(D['lab'])
    stock = D['F'] @ (STOCK / 1024)
    pred = {}
    for name, T in Ts.items():
        pred['empirical_' + name] = target(T, D['lin18'])[0]
    hc = read(ROOT/'research/gr4_modes/local/hcbw.json')
    v = np.asarray(Ts['pooled']['mix']) @ np.linalg.inv(np.asarray(hc['gxr_mix']['gxr_to_c_from_linsrgb']))
    v /= v.sum()
    pred['inherited_K03_pre_mix'] = np.interp(D['x'] @ v, D['nodes'], D['curve'])
    # Wrong-domain controls are diagnostic only; never used in fit or gates.
    enc = fv.fm.fs.linear_to_srgb(D['lin18'])
    qwrong = fv.fm.fs.srgb_to_linear(enc @ np.asarray(Ts['pooled']['mix'])) / .18
    pred['wrong_encoded_srgb_mix'] = tone(Ts['pooled']['tone'], qwrong)
    pred['wrong_equal_linear_srgb'] = tone(Ts['pooled']['tone'], D['lin18'].mean(axis=1)/.18)
    report = {'units': '8-bit codes, predicted minus observed GR IV HC JPEG',
              'pooled_curve_is_in_sample_diagnostic': True, 'frames': {}, 'groups': {}, 'holdout_target': {}}
    for g, s in masks.items():
        report['groups'][g] = {'stock': stats((stock-D['j'])[s]),
             **{k: stats((p-D['j'])[s], (stock-D['j'])[s]) for k,p in pred.items()}}
    for i, frame in enumerate(FRAMES):
        s = D['frame'] == i
        report['frames'][frame] = {g: {k: stats((p-D['j'])[s&m]) for k,p in pred.items()}
                                   for g,m in masks.items() if (s&m).any()}
        p, sup = target(Ts[f'train_{1-i}'], D['lin18'])
        report['holdout_target'][frame] = {g: stats((p-D['j'])[s&m]) for g,m in masks.items()}
        report['holdout_target'][frame]['support_fraction'] = float(sup[s].mean())
    p, sup = target(Ts['pooled'], D['lin18'])
    report['support_fraction'] = float(sup.mean())
    report['per_hue_support_fraction'] = {g: float(sup[m].mean()) if m.any() else None for g,m in masks.items()}
    dump(LOCAL/'target_validation.json', report)
    print(json.dumps({'pooled': {g: report['groups'][g]['empirical_pooled'] for g in ('warm','green','blue_cyan','red')},
                      'holdout': {f: r['chromatic'] for f,r in report['holdout_target'].items()},
                      'support': report['support_fraction']}))


def role_data(role):
    D, S = data('real_blocks'), data('synthetic_train')
    sel = np.ones(len(D['j']), bool) if role == 'full' else D['frame'] != int(role)
    tag = 'pooled' if role == 'full' else f'train_{1-int(role)}'
    ss = S['support_'+tag] & ~S['out_of_curve']
    return D, S, sel, ss, tag


def quantiles_jac(A, b, u):
    e = A @ u + b
    a = abs(e)
    pos = (len(a)-1) * np.array([.5,.9])
    lo, hi = np.floor(pos).astype(int), np.ceil(pos).astype(int)
    ix = np.argpartition(a, np.r_[lo,hi]); il, ih = ix[lo], ix[hi]
    t = pos-lo
    val = a[il]*(1-t)+a[ih]*t
    jac = np.sign(e[il])[:,None]*A[il]*(1-t[:,None])+np.sign(e[ih])[:,None]*A[ih]*t[:,None]
    return val, jac


def colour_gate(p, y, ch, stock, tol=1e-9):
    return bool(np.all(np.percentile(abs(p[ch]-y[ch]), [50,90]) <=
                       np.percentile(abs(stock[ch]-y[ch]), [50,90])+tol))


def synth_gate(p, target_, stock):
    a, b = abs(p-target_), abs(stock-target_)
    return bool(np.median(a) < np.median(b)-1e-5 and
                np.percentile(a,90) <= np.percentile(b,90)+1e-9 and
                np.mean(a*a) < np.mean(b*b)-1e-5)


def summary_metrics(D, p, select=None):
    sel = np.ones(len(D['j']), bool) if select is None else select
    stock = D['F'] @ (STOCK/1024)
    e, er = p-D['j'], stock-D['j']
    out = {g: stats(e[sel&m], er[sel&m]) for g,m in groups(D['lab']).items()}
    out['bin_weighted_rms'] = float(np.sqrt(np.sum(real_weights(D,sel)*e[sel]**2)))
    out['real_gate'] = colour_gate(p[sel],D['j'][sel],groups(D['lab'][sel])['chromatic'],stock[sel])
    return out


def sky_interval(tag,D=None):
    P = read(LOCAL/'authored_points.json')
    D = data('real_blocks') if D is None else D
    x = np.asarray(P['x'])[0]
    f = np.interp(x,D['nodes'],D['curve'])
    old = float(f@(STOCK/1024)); tgt = P['target_'+tag][0]
    return x, old, tgt, min(old,2*tgt-old), max(old,2*tgt-old)


def fit_y(role):
    D,S,sel,ss,tag = role_data(role)
    F, y, rw = D['F'][sel], D['j'][sel], real_weights(D,sel)
    A, b = F[:,:2]-F[:,2:3], F[:,2]-y
    X, sy = S['F'][ss], S['target_'+tag][ss]
    As, bs = X[:,:2]-X[:,2:3], X[:,2]-sy
    alpha=float(rw@((F@(STOCK/1024)-y)**2)/np.mean((X@(STOCK/1024)-sy)**2))
    H = A.T@(rw[:,None]*A)+alpha*As.T@As/len(As)
    g = A.T@(rw*b)+alpha*As.T@bs/len(As)
    c = float(rw@(b*b)+alpha*np.mean(bs*bs))
    ch = groups(D['lab'][sel])['chromatic']
    gates = [ch]
    gate_arrays = [(A[m],b[m]) for m in gates]
    caps = [quantiles_jac(a,bb,STOCK[:2]/1024)[0] for a,bb in gate_arrays]
    xsky, oldsky, targetsky, lo, hi = sky_interval(tag,D)
    fsky = np.interp(xsky,D['nodes'],D['curve'])
    asky, bsky = fsky[:2]-fsky[2], fsky[2]
    def constraint(u):
        vals = [cap-quantiles_jac(a,bb,u)[0] for (a,bb),cap in zip(gate_arrays,caps)]
        return np.r_[np.concatenate(vals)/10, (asky@u+bsky-lo)/10, (hi-asky@u-bsky)/10,
                     1.125-u.sum(),u.sum()+.25]
    def jac(u):
        return np.vstack([-quantiles_jac(a,bb,u)[1]/10 for a,bb in gate_arrays]+[
            asky[None,:]/10,-asky[None,:]/10,-np.ones((1,2)),np.ones((1,2))])
    sols=[]
    seeds=[STOCK[:2]/1024,-np.linalg.solve(H,g),[.25,.5],[.2,.4],[.4,.3]]
    for seed in seeds:
        sol=optimize.minimize(lambda u:(u@H@u+2*g@u+c)/100,seed,
             jac=lambda u:2*(H@u+g)/100,method='SLSQP',bounds=[(-.125,1.25)]*2,
             constraints=[{'type':'ineq','fun':constraint,'jac':jac}],
             options={'maxiter':100,'ftol':1e-10})
        sols.append({'u':sol.x,'success':bool(sol.success),'iterations':sol.nit,
                     'message':str(sol.message),'objective':float(sol.fun),
                     'min_constraint':float(constraint(sol.x).min())})
    pairs = set()
    for rec in sols:
        for amount in (1.,.9,.75,.5,.25,.1,0.):
            mid = (STOCK[:2]/1024)*(1-amount)+rec['u']*amount
            r,g0 = np.rint(mid*1024).astype(int)
            pairs.update((int(r+i),int(g0+j)) for i in range(-3,4) for j in range(-3,4))
    # Bounded broad search as a check against local percentile-constraint minima.
    pairs.update((r,g0) for r in range(-128,1281,32) for g0 in range(-128,1281,32)
                 if -128<=1024-r-g0<=1280)
    rows=[]
    for r,g0 in sorted(pairs):
        q=np.array([r,g0,1024-r-g0]);u=q[:2]/1024
        if q.min() < -128 or q.max() > 1280:
            continue
        cv=constraint(u)
        if cv.min() < -1e-10:
            continue
        ps = X@(q/1024); sky=float(fsky@(q/1024))
        passed = synth_gate(ps,sy,X@(STOCK/1024)) and abs(sky-targetsky) < abs(oldsky-targetsky)-.1
        rows.append({'q':q,'objective':float(u@H@u+2*g@u+c),'synthetic_and_sky_gate':passed,
                     'sky_change':sky-oldsky,'sky_abs_error':abs(sky-targetsky)})
    good=[r for r in rows if r['synthetic_and_sky_gate']]
    changed=[r for r in rows if abs(r['sky_change'])>=.1]
    chosen=min(good or changed or rows,key=lambda r:r['objective']) if rows else {
        'q':STOCK.copy(),'objective':float(alpha*np.mean((X@(STOCK/1024)-sy)**2)+rw@((F@(STOCK/1024)-y)**2)),
        'synthetic_and_sky_gate':False,'fallback':True}
    p=D['F']@(np.asarray(chosen['q'])/1024)
    out={'role':role,'family':'Y-row','Y_q10':chosen['q'],'shared_curve_u8':D['curve'],
         'A5_nodes_u12':D['nodes'],'synthetic_weight':alpha,
         'objective_definition':'real equal-bin MSE plus synthetic MSE weighted to equalise their stock baseline losses',
         'chosen':chosen,'training':summary_metrics(D,p,sel),'evaluated_integer_n':len(pairs),
         'training_feasible_integer_n':len(rows),'joint_gate_integer_n':len(good),'solvers':sols,
         'accepted':False,'firmware_ready':False}
    if role!='full':
        out['heldout']=summary_metrics(D,p,~sel)
    dump(LOCAL/f'y_integer_search_{role}.json',rows)
    dump(LOCAL/f'y_{role}.json',out)
    print(json.dumps({'role':role,'Y_q10':chosen['q'].tolist(),'training_gate':out['training']['real_gate'],
                     'synthetic_gate':chosen['synthetic_and_sky_gate'],
                     'heldout_gate':out.get('heldout',{}).get('real_gate'),
                     'training_chromatic_median':out['training']['chromatic']['median_abs'],
                     'feasible_integer_n':len(rows)}))


def interpolation(x,nodes):
    k=np.clip(np.searchsorted(nodes,x,side='right')-1,0,len(nodes)-2)
    t=(np.clip(x,nodes[0],nodes[-1])-nodes[k])/(nodes[k+1]-nodes[k])
    return sparse.csr_matrix((np.stack([1-t,t],axis=1).ravel(),
        (np.repeat(np.arange(len(x)),2),np.stack([k,k+1],axis=1).ravel())),shape=(len(x),len(nodes)))


def t1_cache(role):
    D,S,sel,ss,tag=role_data(role)
    nodes,K=D['nodes'],D['curve'];dk=np.diff(K);active=np.flatnonzero(dk>0);dk=dk[active]
    T=(np.arange(33)[:,None]>active[None,:])*dk[None,:]
    J=sparse.block_diag([T,T]).toarray();nf=len(active)
    W=[interpolation(D['x'][sel,c],nodes) for c in range(3)]
    Z=sparse.hstack([W[0]-W[2],W[1]-W[2]],format='csr')
    b=D['F'][sel,2]-D['j'][sel];rw=real_weights(D,sel)
    H0=(Z.T@Z.multiply(rw[:,None])).toarray();g0=np.asarray(Z.T@(rw*b)).ravel()
    H=J.T@H0@J;g=J.T@g0;c=float(rw@(b*b))
    ch=groups(D['lab'][sel])['chromatic'];Ac=np.asarray(Z[ch]@J);bc=b[ch]
    cf=D['frame'][sel][ch]
    X=S['x'][ss];Ws=[interpolation(X[:,c],nodes) for c in range(3)]
    As=np.asarray(sparse.hstack([Ws[0]-Ws[2],Ws[1]-Ws[2]])@J)
    bs=S['F'][ss,2]-S['target_'+tag][ss]
    alpha=float(rw@((D['F'][sel]@(STOCK/1024)-D['j'][sel])**2)/np.mean((S['F'][ss]@(STOCK/1024)-S['target_'+tag][ss])**2))
    H+=alpha*As.T@As/len(As);g+=alpha*As.T@bs/len(As);c+=alpha*float(np.mean(bs*bs))
    xsky,oldsky,targetsky,lo,hi=sky_interval(tag,D)
    skyW=[interpolation(np.array([xsky[c]]),nodes) for c in range(3)]
    skyA=np.asarray(sparse.hstack([skyW[0]-skyW[2],skyW[1]-skyW[2]])@J).ravel()
    skyb=float(np.interp(xsky[2],nodes,K))
    np.savez(TMP/f't1_{role}.npz',H=H,g=g,c=c,Ac=Ac,bc=bc,cf=cf,As=As,bs=bs,T=T,dk=dk,J=J,nf=nf,
             skyA=skyA,skyb=skyb,skylo=lo,skyhi=hi,oldsky=oldsky,targetsky=targetsky,
             synth_stock=S['F'][ss]@(STOCK/1024)-S['target_'+tag][ss],K=K,nodes=nodes,alpha=alpha)
    print(json.dumps({'cached_role':role,'variables':2*nf,'colour_gate_n':len(bc),'synthetic_n':len(bs)}))


def integer_curves(curves,q,K,radius=10):
    # Adapted from round 2: integer, monotone, exact grey axis at every original node.
    q=np.asarray(q,int);levels=[]
    for target_,row in zip(K,curves):
        choices=[];center=np.rint(row).astype(int)
        for r in range(max(0,center[0]-radius),min(255,center[0]+radius)+1):
            for g in range(max(0,center[1]-radius),min(255,center[1]+radius)+1):
                rem=int(1024*target_)-int(q[0]*r+q[1]*g)
                if rem%q[2]:
                    continue
                b=rem//q[2]
                if 0<=b<=255 and abs(b-row[2])<=2*radius+1:
                    choices.append((r,g,b))
        choices.append((int(target_),)*3)
        levels.append(np.unique(choices,axis=0))
    costs=np.sum((levels[0]-curves[0])**2,axis=1);back=[]
    for prev,curr in zip(levels[:-1],levels[1:]):
        valid=np.all(prev[:,None,:]<=curr[None,:,:],axis=2)
        trans=np.where(valid,costs[:,None],np.inf);ix=np.argmin(trans,axis=0)
        costs=trans[ix,np.arange(len(curr))]+np.sum((curr-curves[len(back)+1])**2,axis=1)
        back.append(ix)
    k=int(np.argmin(costs));assert np.isfinite(costs[k]);out=[levels[-1][k]]
    for n in range(31,-1,-1):
        k=int(back[n][k]);out.append(levels[n][k])
    out=np.asarray(out[::-1],int)
    assert np.all(np.diff(out,axis=0)>=0) and np.array_equal(out@q,K.astype(int)*1024)
    return out


def t1_mixes():
    return [(r,g,1024-r-g) for r in range(128,769,128) for g in range(128,769,128)
            if 128<=1024-r-g<=768]


def predict(D,curves,q):
    return sum(np.interp(D['x'][:,c],D['nodes'],np.asarray(curves)[:,c])*(q[c]/1024) for c in range(3))


def fit_t1(role,index):
    q=np.asarray(t1_mixes()[index]);w=q/1024
    with np.load(TMP/f't1_{role}.npz') as z:
        C={k:z[k] for k in z.files}
    nf=int(C['nf']);T=C['T'];J=C['J'];K=C['K'];H=C['H'];g=C['g'];c=float(C['c'])
    Ac,bc=C['Ac'],C['bc'];D,S,sel,ss,tag=role_data(role)
    masks=[np.ones(len(bc),bool)]
    # Baseline is the inherited stock mix, independent of the searched endpoint weights.
    ustock=np.r_[np.full(nf,STOCK[0]/1024),np.full(nf,STOCK[1]/1024)]
    ga=[(Ac[m],bc[m]) for m in masks]
    caps=[quantiles_jac(a,b,ustock)[0]-np.array([.4,.8]) for a,b in ga]
    synth_cap=np.percentile(abs(C['synth_stock']),[50,90])-np.array([.1,.3])
    tri=np.hstack([np.eye(nf),np.eye(nf)])
    end=np.block([[C['dk'][None,:]/255,np.zeros((1,nf))],[np.zeros((1,nf)),C['dk'][None,:]/255]])
    # A small contribution-curve penalty discourages unsupported extreme tails.
    baseline=np.r_[w[0]*K,w[1]*K];ridge=.01/len(K)
    Hreg=H+ridge*(J.T@J);greg=g-ridge*(J.T@baseline);creg=c+ridge*float(baseline@baseline)
    def fun(u):
        return (u@Hreg@u+2*greg@u+creg)/100
    def jac(u):
        return 2*(Hreg@u+greg)/100
    def cv(u):
        return np.r_[np.concatenate([cap-quantiles_jac(a,b,u)[0] for (a,b),cap in zip(ga,caps)]),
                     synth_cap-quantiles_jac(C['As'],C['bs'],u)[0]]/10
    def cj(u):
        return np.vstack([-quantiles_jac(a,b,u)[1] for a,b in ga]+[
                         -quantiles_jac(C['As'],C['bs'],u)[1]])/10
    skylo,skyhi=float(C['skylo']),float(C['skyhi'])
    if C['targetsky']>C['oldsky']:
        skylo+=1.
    else:
        skyhi-=1.
    cons=[optimize.LinearConstraint(tri,-np.inf,1),optimize.LinearConstraint(end,w[:2],w[:2]),
          optimize.LinearConstraint(C['skyA'],skylo-float(C['skyb']),skyhi-float(C['skyb'])),
          {'type':'ineq','fun':cv,'jac':cj}]
    start=np.r_[np.full(nf,w[0]),np.full(nf,w[1])]
    sol=optimize.minimize(fun,start,jac=jac,method='SLSQP',bounds=[(0.,1.)]*(2*nf),
                           constraints=cons,options={'maxiter':220,'ftol':1e-9})
    P=np.zeros((33,3));P[:,0]=T@sol.x[:nf];P[:,1]=T@sol.x[nf:];P[:,2]=K-P[:,0]-P[:,1]
    curves=P/w
    alternatives=[];stock=D['F']@(STOCK/1024);cs=groups(D['lab'][sel])['chromatic']
    gate_masks=[sel]
    xsky,oldsky,targetsky,lo,hi=sky_interval(tag,D)
    rw=real_weights(D,sel)
    for strength in (1.,.85,.65,.45,.25,.1,0.):
        cc=integer_curves(np.clip(K[:,None]*(1-strength)+curves*strength,0,255),q,K)
        ps=sum(np.asarray(interpolation(S['x'][ss,c0],D['nodes'])@cc[:,c0]).ravel()*w[c0] for c0 in range(3))
        p=predict(D,cc,q)
        passes=all(colour_gate(p[m],D['j'][m],groups(D['lab'][m])['chromatic'],stock[m]) for m in gate_masks)
        sky=sum(float(np.interp(xsky[k],D['nodes'],cc[:,k]))*w[k] for k in range(3))
        sg=synth_gate(ps,S['target_'+tag][ss],S['F'][ss]@(STOCK/1024))
        skyg=abs(sky-targetsky)<abs(oldsky-targetsky)-.1
        objective=float(rw@((p[sel]-D['j'][sel])**2)+float(C['alpha'])*np.mean((ps-S['target_'+tag][ss])**2))
        alternatives.append({'strength':strength,'curves_u8':cc,'training_real_gate':passes,
             'training_synthetic_gate':sg,'sky_gate':skyg,'sky_change':sky-oldsky,
             'objective':objective,'joint_gate':bool(passes and sg and skyg)})
    good=[x for x in alternatives if x['joint_gate']]
    chosen=min(good or alternatives,key=lambda r:r['objective'])
    p=predict(D,np.asarray(chosen['curves_u8']),q)
    out={'role':role,'index':index,'family':'conditional T1','Y_q10':q,'chosen':chosen,'synthetic_weight':float(C['alpha']),
         'A5_nodes_u12':D['nodes'],'training':summary_metrics(D,p,sel),'alternatives':alternatives,
         'solver':{'success':bool(sol.success),'message':str(sol.message),'iterations':sol.nit,
                   'min_real_constraint':float(cv(sol.x).min()),'endpoint_violation':float(abs(end@sol.x-w[:2]).max())},
         'accepted':False,'firmware_ready':False}
    if role!='full':
        out['heldout']=summary_metrics(D,p,~sel)
    dump(LOCAL/f't1_{role}_{index:02d}.json',out)
    print(json.dumps({'role':role,'index':index,'q':q.tolist(),'joint_gate':chosen['joint_gate'],
         'training_real_gate':chosen['training_real_gate'],'train_median':out['training']['chromatic']['median_abs'],
         'heldout_gate':out.get('heldout',{}).get('real_gate'),'iterations':sol.nit,'success':bool(sol.success)}))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['prepare', 'validate-targets', 'fit-y', 't1-cache', 'fit-t1'])
    p.add_argument('--role',choices=['full','0','1'],default='full')
    p.add_argument('--index',type=int,default=0)
    a = p.parse_args()
    guard()
    if a.command == 'prepare':
        prepare()
    elif a.command == 'validate-targets':
        validate_targets()
    elif a.command == 'fit-y':
        fit_y(a.role)
    elif a.command == 't1-cache':
        t1_cache(a.role)
    elif a.command == 'fit-t1':
        fit_t1(a.role,a.index)


if __name__ == '__main__':
    main()
