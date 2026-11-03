"""Dense measured GR IV functions, whole-band/hue holdouts and real photographs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import cKDTree
from scipy.optimize import minimize_scalar
import argparse

PAIRS = {'positive': 'research/gr4_dense_returns_r1', 'negative': 'research/gr4_nega_returns_r1'}


def feature(raw):
    raw = np.maximum(np.asarray(raw), 1e-7)
    return np.stack([np.log2(raw @ np.array([.25, .5, .25])),
                     np.log2(raw[..., 0]/raw[..., 1]),
                     np.log2(raw[..., 2]/raw[..., 1])], axis=-1)


def relative(base, standard, styled):
    cs, cm, cb = [np.hypot(v[..., 1], v[..., 2]) for v in (standard, styled, base)]
    active = (cs >= 8) & (cm >= 8) & (cb >= 8)
    q = np.ones_like(cs, complex)
    np.divide(styled[..., 1]+1j*styled[..., 2], standard[..., 1]+1j*standard[..., 2], out=q, where=active)
    ab = (base[..., 1]+1j*base[..., 2])*q
    return np.stack([base[..., 0]+styled[..., 0]-standard[..., 0], ab.real, ab.imag], axis=-1)


def grouped(x, y):
    xx, inv = np.unique(np.round(x, 9), axis=0, return_inverse=True)
    count = np.bincount(inv)
    yy = np.column_stack([np.bincount(inv, weights=y[:, k])/count for k in range(y.shape[1])])
    return xx, yy


class Function:
    def __init__(self, x, y):
        self.x, self.y = grouped(x, y)
        self.function = LinearNDInterpolator(self.x, self.y)
        self.tree = cKDTree(self.x)

    def __call__(self, x):
        y = self.function(x)
        distance = self.tree.query(x)[0]
        valid = np.isfinite(y).all(axis=1) & (distance <= 1.)
        return y, valid, distance


class Dense:
    def __init__(self, style='positive'):
        self.a = rt.arrays(PAIRS[style]+'/local/target/paired_measurements.npz')
        self.info = rt.read(PAIRS[style]+'/local/target/manifest.json')
        self.style = style
        self.raw_function = Function(self.a['feature'], np.c_[self.a['standard'], self.a[style]])
        self.std_function = Function(self.a['standard']/[20., 30., 30.], self.a[style])
        self.T = np.array(self.info['bridge']['T_white_balanced_neutral_normalized'])
        self.anchor = self.info['u118_raw_wb_without_BE']

    def labs(self, x):
        raw = x @ self.T.T * (self.anchor/320.)
        y, valid, distance = self.raw_function(feature(raw))
        valid &= (raw > 0).all(axis=1)
        return y[:, :3], y[:, 3:], valid, distance

    def target(self, x, baseline):
        std, styled, valid, distance = self.labs(x)
        return relative(baseline, std, styled), valid, distance


def cross_validate():
    allrows = []
    for style in PAIRS:
        d = Dense(style)
        a = d.a
        hue = (np.degrees(np.arctan2(a['standard'][:, 2], a['standard'][:, 1])) % 360 // 15).astype(int) % 3
        for domain in ('raw', 'standard'):
            x = a['feature'] if domain == 'raw' else a['standard']/[20., 30., 30.]
            y = np.c_[a['standard'], a[style]] if domain == 'raw' else a[style]
            for scheme, groups in [('page', a['band']), ('hue', hue)]:
                pooled = []
                for group in np.unique(groups):
                    held = groups == group
                    held_keys = {tuple(v) for v in np.round(a['feature'][held], 9)}
                    train = np.array([not h and tuple(v) not in held_keys for h, v in zip(held, np.round(a['feature'], 9))])
                    function = Function(x[train], y[train])
                    pred, valid, distance = function(x[held])
                    observed = y[held]
                    errors = rt.cm.delta_e00(pred[valid, -3:], observed[valid, -3:])
                    standard_error = rt.cm.delta_e00(pred[valid, :3], observed[valid, :3]) if domain == 'raw' else []
                    row = dict(style=style, input_space=domain, scheme=scheme, fold=int(group),
                               train=int(train.sum()), held=int(held.sum()), supported=int(valid.sum()),
                               unsupported=int((~valid).sum()), style_error=rt.stats(errors),
                               standard_error=rt.stats(standard_error), duplicate_RAW_leakage=False)
                    allrows.append(row)
                    pooled.extend(errors)
                    np.savez_compressed(rt.LOCAL/f'style/{style}_{domain}_{scheme}{group}.npz',
                                        index=np.flatnonzero(held), valid=valid, prediction=pred,
                                        observed=observed, nearest_distance=distance)
                print(style, domain, scheme, rt.stats(pooled), flush=True)
        np.savez_compressed(rt.LOCAL/f'style/{style}_functions.npz',
                            raw_feature=d.raw_function.x, raw_values=d.raw_function.y,
                            standard_feature=d.std_function.x, styled_values=d.std_function.y,
                            raw_tetrahedra=d.raw_function.function.tri.simplices,
                            standard_tetrahedra=d.std_function.function.tri.simplices)
    rt.dump('style/holdouts.json', allrows)


def coverage():
    result = []
    for style in PAIRS:
        d = Dense(style)
        for n in (17, 33):
            codes = np.stack(np.meshgrid(*([np.linspace(0, 255, n)]*3), indexing='ij'), axis=-1).reshape(-1, 3)
            values, valid, distance = d.std_function(rt.lab(codes)/[20., 30., 30.])
            np.savez_compressed(rt.LOCAL/f'style/std_to_{style}_{n}.npz',
                                nodes_rgb_q8_8=np.rint(np.clip(rt.rgb(values), 0, 255)*256),
                                valid=valid, nearest_distance=distance)
            result.append(dict(style=style, cube=n, nodes=len(codes), supported=int(valid.sum()),
                               unsupported=int((~valid).sum()), support_fraction=float(valid.mean())))
        raw_range=np.percentile(d.a['feature'], [0, 100], axis=0)
        rt.dump(f'style/{style}_space.json', dict(feature='log2(.25R+.5G+.25B), log2(R/G), log2(B/G); black-subtracted white-normalized WB RAW, no BaselineExposure',
                      input_range=raw_range, lab_white='D65', no_extrapolation=True, nearest_distance_max=1.,
                      paired_points=len(d.a['feature']), unique_points=len(d.raw_function.x)))
    rt.dump('style/coverage.json', result)


def natural_other():
    d = Dense('positive')
    rows = []
    quality = rt.read('research/gr4_dense_returns_r1/local/target/quality.json')
    gains = np.median([v['modes']['standard']['radial']['gain_ev'] for v in quality.values()], axis=0)
    radius = next(iter(quality.values()))['modes']['standard']['radial']['radius']
    alloriginal=[]
    alladjusted=[]
    for path in sorted((rt.ROOT/'research/gr4_dense_returns_r1/local/natural').glob('*.json')):
        doc = rt.read(path)
        points = doc['points']
        raw = np.array([p['raw_wb'] for p in points])
        actual = np.array([p['observed_lab'] for p in points])
        xy = np.array([[p['x'], p['y']] for p in points])
        pred, valid, dist = d.raw_function(feature(raw))
        original = rt.cm.delta_e00(pred[valid,:3], actual[valid])
        old = doc['new_dense_standard_de00']
        assert len(original) == old['n'] and abs(np.median(original)-old['median']) < 1e-8
        # Split spatial blocks before the diagnostic fit. This offset is never
        # used to redefine the anchor or a reported route ceiling.
        train = ((xy[:,0]//400+xy[:,1]//400)%2 == 0) & valid
        test = ~train & valid
        def loss(ev):
            pp, vv, _ = d.raw_function(feature(raw[train]*2**ev))
            e = np.full(int(train.sum()), 50.)
            e[vv] = rt.cm.delta_e00(pp[vv,:3], actual[train][vv])
            return float(np.mean(e))
        opt = minimize_scalar(loss, bounds=(-1.5, 1.5), method='bounded', options={'xatol':1e-5}) if train.sum() >= 4 else None
        p2,v2,_ = d.raw_function(feature(raw[test]*2**opt.x)) if opt is not None else (np.empty((0,6)),np.zeros(0,bool),None)
        adjusted = rt.cm.delta_e00(p2[v2,:3], actual[test][v2]) if opt is not None else []
        before_test=rt.cm.delta_e00(pred[test,:3],actual[test])
        row = dict(id=path.stem,n=len(points),supported=int(valid.sum()), original=rt.stats(original),
                   L_bias=float(np.median(pred[valid,0]-actual[valid,0])) if valid.any() else None,
                   diagnostic_ev=float(opt.x) if opt is not None else None, diagnostic_train=int(train.sum()),
                   diagnostic_test=int(test.sum()), diagnostic_supported=int(v2.sum()),
                   diagnostic_before_test=rt.stats(before_test),diagnostic_after_test=rt.stats(adjusted),
                   insufficient=int(valid.sum())<8, target_anchor_changed=False)
        # Record the residual chromaticity after replacing only L with observed L.
        corrected=pred[valid,:3].copy();corrected[:,0]=actual[valid,0]
        row['remove_L_diagnostic']=rt.stats(rt.cm.delta_e00(corrected,actual[valid]))
        alloriginal.extend(original)
        alladjusted.extend(adjusted)
        rows.append(row)
        print(path.stem, int(valid.sum()), round(row['original']['median'],3),
              round(row['diagnostic_ev'],3) if opt is not None else None,
              row['diagnostic_after_test'].get('median'), flush=True)
    rt.dump('natural/other_standard.json',dict(images=rows, pooled=rt.stats(alloriginal),
                    exposure_diagnostic_pooled=rt.stats(alladjusted), interpretation='same GR IV; not a GXR-to-GR-IV bridge measurement'))


def photographs():
    dense = {s:Dense(s) for s in PAIRS}
    q = rt.read('research/gr4_dense_returns_r1/local/target/quality.json')
    newgain = np.median([v['modes']['standard']['radial']['gain_ev'] for v in q.values()],axis=0)
    radii = next(iter(q.values()))['modes']['standard']['radial']['radius']
    radial = rt.read('research/gr4_modes/local/tone_curves.json')['radial']
    rows=[]
    for folder in ('research/gr_webpairs/local', 'research/gr_pairs/local'):
        inv=rt.read(folder+'/inventory.json')
        for item in inv:
            if item['family'] != 'gr4' or item['mode'] not in ('standard','positive','negative'):
                continue
            ident=item['id'];stem=rt.ROOT/folder/'samples'/ident
            if not stem.with_suffix('.npz').exists():
                continue
            a=rt.arrays(stem.with_suffix('.npz'));md=rt.read(stem.with_suffix('.json'))
            # A fixed feature-cell sample prevents large uniform regions from
            # dominating and is independent of the observed prediction error.
            key=np.floor(a['features']/[.12,.04,.04]).astype(int)
            _, invkey=np.unique(key,axis=0,return_inverse=True)
            order=np.lexsort((-a['weight'],invkey));_,first=np.unique(invkey[order],return_index=True)
            take=order[first]
            if len(take)>1600: take=take[np.linspace(0,len(take)-1,1600,dtype=int)]
            rr=a['r2'][take]
            oldcoef=radial['gr4_coef_natural_log']
            oldgain=np.exp(-sum(c*rr**(i+1) for i,c in enumerate(oldcoef)))
            raw=a['uc'][take]/(2**md['baseline_exposure'])/oldgain[:,None]
            observed=rt.lab(a['jpeg'][take])
            style=item['mode'];d=dense['negative' if style=='negative' else 'positive']
            profiles=[]
            template_be=np.log2(d.info['u118_with_template_BE']/d.anchor)
            for profile in ('old_radial','new_radial','none','metadata_BE_new_radial','metadata_BE_no_radial'):
                gain=oldgain if profile=='old_radial' else 2**np.interp(np.sqrt(rr),radii,newgain) if profile in ('new_radial','metadata_BE_new_radial') else np.ones(len(rr))
                if profile in ('metadata_BE_new_radial','metadata_BE_no_radial'):
                    gain=gain*2**(md['baseline_exposure']-template_be)
                value,valid,distance=d.raw_function(feature(raw*gain[:,None]))
                pred=value[:,:3] if style=='standard' else value[:,3:]
                error=rt.cm.delta_e00(pred[valid],observed[valid])
                profiles.append(dict(profile=profile,supported=int(valid.sum()),error=rt.stats(error),
                                     L_bias=float(np.median(pred[valid,0]-observed[valid,0])) if valid.any() else None))
                np.savez_compressed(rt.LOCAL/f'natural/{ident}_{profile}.npz',raw_wb=raw*gain[:,None],
                                    observed=observed,predicted=pred,supported=valid,source_index=take)
            default=item.get('default_parameters',not item.get('nondefault',False))
            decoded=md.get('metadata',{}).get('decoded',{})
            rows.append(dict(id=ident,mode=style,source=folder,default_parameters=default,
                             points=len(take),baseline_exposure=md['baseline_exposure'],template_baseline_exposure=template_be,
                             iso=md.get('metadata',{}).get('iso'),firmware=md.get('metadata',{}).get('firmware'),
                             dynamic_range=decoded.get('dynamic_range_0x0069'),profiles=profiles,
                             actual_same_raw_standard=style=='standard', camera_bridge_used=False))
            print(ident,style,len(take),[(p['profile'],p['supported'],round(p['error'].get('median',-1),3)) for p in profiles],flush=True)
    rt.dump('natural/gr4_photographs.json',rows)


def main():
    for name in ('style','natural'):(rt.LOCAL/name).mkdir(exist_ok=True)
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['cv','coverage','other','photographs','all'])
    action=ap.parse_args().action
    for key,fn in [('cv',cross_validate),('coverage',coverage),('other',natural_other),('photographs',photographs)]:
        if action in (key,'all'):fn()


if __name__=='__main__':main()
